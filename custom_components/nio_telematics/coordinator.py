"""Data coordinator for NIO Open Telematics."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2TokenRequestReauthError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    NioApiClient,
    NioApiError,
    NioAuthenticationError,
    NioPermissionError,
    NioResourceNotFoundError,
)
from .const import (
    CHANGE_ENDPOINT_RESOURCES,
    CHANGE_ENDPOINTS,
    CONF_VIN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .models import NioSocStatus, NioVehicleData


class NioDataUpdateCoordinator(DataUpdateCoordinator[NioVehicleData]):
    """Fetch a coherent snapshot for one NIO vehicle."""

    _LOGGER = logging.getLogger(__name__)

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: NioApiClient,
    ) -> None:
        super().__init__(
            hass,
            logger=self._LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_entry=entry,
        )
        self._client = client
        self._vin = entry.data[CONF_VIN]
        self._telemetry: dict[str, dict] = {}

    _CHANGE_ENDPOINTS = CHANGE_ENDPOINTS

    async def _async_update_data(self) -> NioVehicleData:
        try:
            latest_record = await self._client.async_get_latest_vehicle_record(
                self._vin
            )
            vehicle_status = NioSocStatus.from_payload(latest_record)
            self._telemetry["vehicle_status"] = latest_record
            endpoint_status = {"vehicle_status": "success"}
            for endpoint in self._CHANGE_ENDPOINTS:
                resource = CHANGE_ENDPOINT_RESOURCES.get(endpoint, endpoint)
                try:
                    record = await self._client.async_get_change_record(
                        self._vin, resource
                    )
                except NioResourceNotFoundError:
                    endpoint_status[endpoint] = "no_recent_data"
                    continue
                except NioPermissionError:
                    endpoint_status[endpoint] = "permission_denied"
                    self._LOGGER.debug(
                        "NIO change endpoint %s lacks granted permission; skipping",
                        endpoint,
                    )
                    continue
                except NioApiError as err:
                    endpoint_status[endpoint] = type(err).__name__
                    self._LOGGER.debug(
                        "Optional NIO endpoint %s unavailable: %s", resource, err
                    )
                    continue
                if endpoint == "soc_status":
                    self._telemetry[endpoint] = {
                        **self._telemetry.get(endpoint, {}),
                        **{
                            key: value
                            for key, value in record.items()
                            if value is not None
                        },
                    }
                else:
                    self._telemetry[endpoint] = record
                endpoint_status[endpoint] = "success"
            try:
                self._telemetry[
                    "odometer_report"
                ] = await self._client.async_get_odometer_report(self._vin)
                endpoint_status["odometer_report"] = "success"
            except NioResourceNotFoundError:
                endpoint_status["odometer_report"] = "no_data"
            except NioPermissionError:
                endpoint_status["odometer_report"] = "permission_denied"
                self._LOGGER.debug(
                    "NIO odometer endpoint lacks granted permission; skipping"
                )
            except NioApiError as err:
                endpoint_status["odometer_report"] = type(err).__name__
        except OAuth2TokenRequestReauthError as err:
            raise ConfigEntryAuthFailed(
                "NIO OAuth authorization expired; reauthentication is required"
            ) from err
        except (NioAuthenticationError, NioPermissionError) as err:
            if isinstance(err, NioPermissionError):
                raise ConfigEntryAuthFailed(
                    "The NIO token is not authorized for all requested scopes. "
                    "Please reauthenticate this integration to refresh permissions."
                ) from err
            raise ConfigEntryAuthFailed(str(err)) from err
        except NioApiError as err:
            raise UpdateFailed(str(err)) from err
        energy_status = NioSocStatus.from_payload(self._telemetry.get("soc_status", {}))
        # The dedicated energy feed is authoritative. The latest vehicle
        # snapshot currently reports placeholder SoC/charging values even
        # when energy data is correct. An empty change feed means no update.
        soc_status = NioSocStatus.merge(energy_status, vehicle_status)
        if energy_status.soc is not None:
            # A new vehicle snapshot must not make cached energy look fresh.
            soc_status = replace(soc_status, event_time=energy_status.event_time)
        return NioVehicleData(
            vin=self._vin,
            soc_status=soc_status,
            fetched_at=datetime.now(UTC),
            telemetry=dict(self._telemetry),
            endpoint_status=endpoint_status,
        )

    async def async_call_on_demand(
        self, operation: str, **params: Any
    ) -> dict[str, Any]:
        """Call a catalog operation without adding it to periodic polling."""
        return await self._client.async_call_on_demand(operation, self._vin, **params)
