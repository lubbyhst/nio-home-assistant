"""Asynchronous client for the official NIO Open Telematics API."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError, ClientResponse
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)

from .const import TELEMATICS_PATH
from .models import NioSocStatus
from .privacy import redact_debug_value as _redact_debug_value
from .privacy import safe_endpoint as _safe_endpoint

_LOGGER = logging.getLogger(__name__)

_SAFE_RESPONSE_HEADERS = {
    "content-type",
    "retry-after",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
}
_SOC_WINDOW_CANDIDATES_SECONDS = (
    10 * 60,
    5 * 60,
)
_SOC_FIELD_ATTRIBUTES = {
    "soc": "soc",
    "remaining_range": "remaining_range",
    "chrg_state": "charging_state",
    "chrg_final_soc": "charging_target",
    "max_soc": "maximum_soc",
    "hivolt_btry_curnt": "high_voltage_battery_current",
    "sample_timestamp": "event_time",
}
ON_DEMAND_OPERATION_IDS = {
    "vehicle_status_history": "getVehicleStatusChanges",
    "adas_snapshots": "getDlbSnapshot",
    "adas_events": "getDlbEvent",
    "extract_adas_snapshot": "extractDlbSnapshot",
    "download_adas_event": "downloadDlbEvent",
    "nomi_asr_files": "getASRFileList",
    "vehicle_recalls": "getVehicleRecallHistory",
    "recall_campaign": "getRecallCampaigns",
}
ON_DEMAND_OPERATIONS = tuple(ON_DEMAND_OPERATION_IDS)


class NioApiError(Exception):
    """Base NIO API error."""


class NioAuthenticationError(NioApiError):
    """NIO rejected or expired the access token."""


class NioPermissionError(NioApiError):
    """The OAuth grant lacks a required scope."""


class NioInvalidParameterError(NioApiError):
    """NIO rejected a documented request parameter."""


class NioResourceNotFoundError(NioApiError):
    """NIO has no accessible record for the requested resource."""


class NioRateLimitError(NioApiError):
    """NIO rate limited the request."""

    def __init__(self, retry_after: int | None) -> None:
        super().__init__("NIO API rate limit exceeded")
        self.retry_after = retry_after


class NioApiClient:
    """Minimal read-only NIO API client."""

    def __init__(
        self,
        oauth_session: OAuth2Session,
        base_url: str,
    ) -> None:
        self._oauth_session = oauth_session
        self._base_url = base_url.rstrip("/")
        self._soc_window_seconds: int | None = None

    async def async_get_soc_status(
        self,
        vin: str,
    ) -> NioSocStatus:
        """Return energy fields merged from newest to oldest change records."""
        data = await self.async_get_change_record(vin, "soc_status")
        return NioSocStatus.from_payload(data)

    async def _async_get_soc_payload(self, vin: str) -> dict[str, Any]:
        """Use the short millisecond window accepted by the live energy API."""
        end_milliseconds = int(time.time()) * 1000
        path = f"{TELEMATICS_PATH}/vehicles/{vin}/soc_status/changes"
        windows = (
            (self._soc_window_seconds,)
            if self._soc_window_seconds is not None
            else _SOC_WINDOW_CANDIDATES_SECONDS
        )
        last_error: NioInvalidParameterError | None = None
        for window_seconds in windows:
            try:
                payload = await self._async_get(
                    path,
                    params={
                        "start_time": end_milliseconds - window_seconds * 1000,
                        "end_time": end_milliseconds,
                    },
                )
            except NioInvalidParameterError as err:
                last_error = err
                continue
            except NioResourceNotFoundError:
                self._soc_window_seconds = window_seconds
                raise
            self._soc_window_seconds = window_seconds
            break
        else:
            if last_error is not None:
                raise last_error
            raise NioApiError("NIO did not accept a SoC query window")
        return payload

    async def async_get_change_record(self, vin: str, resource: str) -> dict[str, Any]:
        """Return the newest record from a documented change endpoint."""
        if resource == "soc_status":
            payload = await self._async_get_soc_payload(vin)
        else:
            payload = await self._async_get(
                f"{TELEMATICS_PATH}/vehicles/{vin}/{resource}/changes"
            )
        data = payload.get("data")
        if not isinstance(data, list):
            raise NioApiError("NIO returned an invalid telemetry payload")
        if not data:
            raise NioResourceNotFoundError("NIO returned no telemetry records")
        records = [item for item in data if isinstance(item, dict)]
        if not records:
            raise NioApiError("NIO returned an invalid telemetry payload")
        if resource == "soc_status":
            # Changes can contain only some fields. Keep the newest non-null
            # value for each field, including a legitimate zero SoC.
            merged: dict[str, Any] = {}
            for record in sorted(
                records, key=lambda item: item.get("sample_timestamp") or 0
            ):
                values = {
                    key: value for key, value in record.items() if value is not None
                }
                parsed = NioSocStatus.from_payload(record)
                for field, attribute in _SOC_FIELD_ATTRIBUTES.items():
                    if getattr(parsed, attribute) is None:
                        values.pop(field, None)
                merged.update(values)
            return merged
        return max(records, key=lambda item: item.get("sample_timestamp", 0))

    async def async_get_latest_vehicle_record(self, vin: str) -> dict[str, Any]:
        """Return the unmodified latest vehicle-status record."""
        payload = await self._async_get(
            f"{TELEMATICS_PATH}/vehicles/{vin}/vehicle_status/latest"
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise NioApiError("NIO returned an invalid vehicle status payload")
        return data

    async def async_get_odometer_report(self, vin: str) -> dict[str, Any]:
        """Return the newest documented aftersales odometer report."""
        payload = await self._async_get(
            f"{TELEMATICS_PATH}/aftersales/vehicles/{vin}/odometer_reports"
        )
        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise NioResourceNotFoundError("NIO returned no odometer reports")
        records = [item for item in data if isinstance(item, dict)]
        if not records:
            raise NioApiError("NIO returned an invalid odometer payload")
        return max(records, key=lambda item: str(item.get("recorded_at", "")))

    async def async_get_latest_vehicle_status(self, vin: str) -> NioSocStatus:
        """Return the latest overall vehicle status snapshot."""
        data = await self.async_get_latest_vehicle_record(vin)
        _LOGGER.debug("NIO latest vehicle response fields: %s", sorted(data))
        return NioSocStatus.from_payload(data)

    async def async_call_on_demand(
        self, operation: str, vin: str, **values: Any
    ) -> dict[str, Any]:
        """Call one allowlisted API operation without changing coordinator polling."""
        operation_specs: dict[str, tuple[str, str, dict[str, str], tuple[str, ...]]] = {
            "vehicle_status_history": (
                "GET",
                f"{TELEMATICS_PATH}/vehicles/{vin}/vehicle_status/changes",
                {"start_time": "start_time", "end_time": "end_time"},
                (),
            ),
            "adas_snapshots": (
                "GET",
                f"{TELEMATICS_PATH}/vehicles/{vin}/adas/snapshot",
                {
                    "start_ts": "startTs",
                    "end_ts": "endTs",
                    "limit": "limit",
                    "offset": "offset",
                },
                (),
            ),
            "adas_events": (
                "GET",
                f"{TELEMATICS_PATH}/vehicles/{vin}/adas/event",
                {
                    "start_ts": "startTs",
                    "end_ts": "endTs",
                    "limit": "limit",
                    "offset": "offset",
                },
                (),
            ),
            "extract_adas_snapshot": (
                "POST",
                f"{TELEMATICS_PATH}/vehicles/{vin}/adas/snapshot/extract",
                {"uuid": "uuid"},
                ("uuid",),
            ),
            "download_adas_event": (
                "POST",
                f"{TELEMATICS_PATH}/vehicles/{vin}/adas/event/download",
                {"uuid": "uuid", "as_url": "asUrl"},
                ("uuid",),
            ),
            "nomi_asr_files": (
                "GET",
                f"{TELEMATICS_PATH}/vehicles/{vin}/nomi/asr",
                {"offset": "offset", "limit": "limit"},
                (),
            ),
            "vehicle_recalls": (
                "GET",
                f"{TELEMATICS_PATH}/aftersales/vehicles/{vin}/recalls",
                {},
                (),
            ),
            "recall_campaign": ("GET", "", {}, ("campaign_no",)),
        }
        if operation not in operation_specs:
            raise ValueError(f"Unsupported NIO operation: {operation}")
        method, path, query_names, required = operation_specs[operation]
        allowed = set(query_names) | set(required)
        if operation == "recall_campaign":
            allowed.add("accept_language")
        if set(values) - allowed:
            raise ValueError(f"Unsupported parameters for {operation}")
        if any(values.get(name) is None for name in required):
            raise ValueError(f"Missing required parameters for {operation}")

        headers = {}
        if language := values.get("accept_language"):
            headers["Accept-Language"] = str(language)
        if operation == "recall_campaign":
            path = (
                f"{TELEMATICS_PATH}/aftersales/recall_campaigns/"
                f"{quote(str(values['campaign_no']), safe='')}"
            )
        params = {
            api_name: values[service_name]
            for service_name, api_name in query_names.items()
            if service_name in values
        }
        return await self._async_request(
            method, path, params=params or None, headers=headers
        )

    async def _async_get(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self._async_request("GET", path, params=params)

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_kwargs: dict[str, Any] = {
            "headers": {"Accept": "application/json", **(headers or {})}
        }
        if params is not None:
            request_kwargs["params"] = params
        try:
            response = await self._oauth_session.async_request(
                method,
                f"{self._base_url}{path}",
                **request_kwargs,
            )
        except OAuth2TokenRequestReauthError:
            # HA's OAuth2Session starts the native reauth flow for this error.
            raise
        except OAuth2TokenRequestTransientError as err:
            raise NioApiError(
                "NIO OAuth token service is temporarily unavailable"
            ) from err
        except OAuth2TokenRequestError as err:
            raise NioApiError("NIO OAuth token request failed") from err
        except ClientError as err:
            _LOGGER.debug(
                "NIO API trace: endpoint=%s stage=transport error_type=%s",
                _safe_endpoint(path),
                type(err).__name__,
            )
            raise NioApiError("Unable to reach the NIO API") from err
        payload: Any = None
        json_error: Exception | None = None
        try:
            payload = await response.json()
        except (ClientError, ValueError) as err:
            json_error = err

        safe_headers = {
            key: value
            for key, value in response.headers.items()
            if key.casefold() in _SAFE_RESPONSE_HEADERS
        }
        _LOGGER.debug(
            "NIO API trace: endpoint=%s params=%s http_status=%s headers=%s "
            "payload=%s json_error=%s",
            _safe_endpoint(path),
            _redact_debug_value(params),
            response.status,
            safe_headers,
            _redact_debug_value(payload),
            type(json_error).__name__ if json_error else None,
        )

        # Authentication, throttling, and server failures take precedence.
        # NIO also sends typed business errors with HTTP 400/404, so inspect
        # those envelopes before falling back to the generic HTTP error.
        if response.status not in {400, 404}:
            await self._raise_for_status(response)
        if json_error is not None:
            await self._raise_for_status(response)
            raise NioApiError("NIO returned a non-JSON response") from json_error
        if not isinstance(payload, dict):
            await self._raise_for_status(response)
            raise NioApiError("NIO returned an invalid response envelope")
        result_code = payload.get("result_code")
        if result_code in {"access_denied", "permission_denied", "forbidden"}:
            raise NioPermissionError("NIO OAuth grant lacks the required scope")
        if result_code == "resource_not_found":
            raise NioResourceNotFoundError("NIO resource was not found")
        if result_code == "invalid_param":
            raise NioInvalidParameterError("NIO rejected request parameters")
        await self._raise_for_status(response)
        if result_code != "success":
            raise NioApiError(
                f"NIO request failed: {payload.get('result_code', 'unknown')}"
            )
        return payload

    @staticmethod
    async def _raise_for_status(response: ClientResponse) -> None:
        if response.status == 401:
            raise NioAuthenticationError("NIO access token is invalid or expired")
        if response.status == 403:
            raise NioPermissionError("NIO OAuth grant lacks the required scope")
        if response.status == 429:
            raw_retry_after = response.headers.get("Retry-After")
            retry_after = (
                int(raw_retry_after)
                if raw_retry_after and raw_retry_after.isdigit()
                else None
            )
            raise NioRateLimitError(retry_after)
        if response.status >= 400:
            raise NioApiError(f"NIO API returned HTTP {response.status}")
