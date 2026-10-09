"""API-client tests for NIO Open Telematics."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)

from custom_components.nio_telematics.api import (
    NioApiClient,
    NioApiError,
    NioAuthenticationError,
    NioPermissionError,
    NioRateLimitError,
    NioResourceNotFoundError,
)
from custom_components.nio_telematics.const import API_BASE_URL


def response(status: int, payload: dict, headers: dict | None = None) -> MagicMock:
    """Build a minimal aiohttp response double."""
    result = MagicMock(status=status, headers=headers or {})
    result.json = AsyncMock(return_value=payload)
    return result


async def test_soc_request_uses_largest_window_and_newest_record(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "custom_components.nio_telematics.api.time.time", lambda: 2_000_000
    )
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(
            200,
            {
                "result_code": "success",
                "data": [
                    {
                        "soc": 40,
                        "remaining_range": 204.5,
                        "chrg_final_soc": 80,
                        "sample_timestamp": 1_760_000_000_000,
                    },
                    {"soc": 41, "sample_timestamp": 1_760_000_100_000},
                ],
            },
        )
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    status = await client.async_get_soc_status("LJNABC12345678901")

    assert status.soc == 41
    assert status.remaining_range == 204.5
    assert status.charging_target == 80
    request = oauth_session.async_request.await_args
    assert request.args[0] == "GET"
    assert request.args[1].endswith("/vehicles/LJNABC12345678901/soc_status/changes")
    assert request.kwargs["params"] == {
        "start_time": 1_956_800_000,
        "end_time": 2_000_000_000,
    }
    assert "Authorization" not in request.kwargs["headers"]


async def test_soc_request_retries_and_caches_smaller_window(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "custom_components.nio_telematics.api.time.time", lambda: 2_000_000
    )
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        side_effect=[
            response(200, {"result_code": "invalid_param"}),
            response(
                200,
                {
                    "result_code": "success",
                    "data": [{"soc": 41, "sample_timestamp": 2_000_000_000}],
                },
            ),
        ]
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    status = await client.async_get_soc_status("LJNABC12345678901")

    assert status.soc == 41
    assert oauth_session.async_request.await_count == 2
    request = oauth_session.async_request.await_args
    assert request.kwargs["params"] == {
        "start_time": 1_978_400_000,
        "end_time": 2_000_000_000,
    }

    oauth_session.async_request.reset_mock()
    oauth_session.async_request.side_effect = None
    oauth_session.async_request.return_value = response(
        200,
        {
            "result_code": "success",
            "data": [{"soc": 42, "sample_timestamp": 2_000_001_000}],
        },
    )

    await client.async_get_soc_status("LJNABC12345678901")

    assert oauth_session.async_request.await_count == 1
    cached_request = oauth_session.async_request.await_args
    assert cached_request.kwargs["params"] == {
        "start_time": 1_978_400_000,
        "end_time": 2_000_000_000,
    }


async def test_latest_vehicle_status_uses_snapshot_endpoint() -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(
            200,
            {
                "result_code": "success",
                "data": {
                    "soc": 52,
                    "chrg_state": "3",
                    "sample_timestamp": 1_760_000_100_000,
                },
            },
        )
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    status = await client.async_get_latest_vehicle_status("LJNABC12345678901")

    assert status.soc == 52
    request = oauth_session.async_request.await_args
    assert request.args[1].endswith("/vehicles/LJNABC12345678901/vehicle_status/latest")


async def test_generic_change_endpoint_returns_newest_record() -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(
            200,
            {
                "result_code": "success",
                "data": [
                    {"vehicle_lock_status": "0", "sample_timestamp": 1000},
                    {"vehicle_lock_status": "1", "sample_timestamp": 2000},
                ],
            },
        )
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    record = await client.async_get_change_record("LJNABC12345678901", "door_status")

    assert record["vehicle_lock_status"] == "1"
    request = oauth_session.async_request.await_args
    assert request.args[1].endswith("/vehicles/LJNABC12345678901/door_status/changes")
    assert "params" not in request.kwargs


async def test_generic_change_endpoint_rejects_malformed_data() -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(200, {"result_code": "success", "data": {}})
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    with pytest.raises(NioApiError, match="invalid telemetry payload"):
        await client.async_get_change_record("LJNABC12345678901", "door_status")


async def test_generic_change_endpoint_maps_empty_data_to_no_recent_data() -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(200, {"result_code": "success", "data": []})
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    with pytest.raises(NioResourceNotFoundError):
        await client.async_get_change_record("LJNABC12345678901", "door_status")


@pytest.mark.parametrize(
    "resource",
    (
        "door_status",
        "fridge_status",
        "light_status",
        "window_status",
        "driving_data",
        "vehicle_status",
        "position_status",
        "trip_status",
        "cell_status",
        "extremum_data",
        "soc_status",
        "heating_status",
        "hvac_status",
        "driving_motor",
        "alarm_signal",
    ),
)
async def test_all_retained_change_endpoints_use_documented_paths(
    resource: str,
) -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(
            200,
            {"result_code": "success", "data": [{"sample_timestamp": 1000}]},
        )
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    await client.async_get_change_record("LJNABC12345678901", resource)

    request = oauth_session.async_request.await_args
    assert request.args[1].endswith(
        f"/vehicles/LJNABC12345678901/{resource}/changes"
    )


async def test_odometer_reports_use_documented_path() -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(
            200,
            {
                "result_code": "success",
                "data": [{"value": 123, "recorded_at": "2026-09-17"}],
            },
        )
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    report = await client.async_get_odometer_report("LJNABC12345678901")

    assert report["value"] == 123
    request = oauth_session.async_request.await_args
    assert request.args[1].endswith(
        "/aftersales/vehicles/LJNABC12345678901/odometer_reports"
    )


async def test_vehicle_status_changes_uses_change_endpoint() -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(
            200,
            {
                "result_code": "success",
                "data": [
                    {"vehl_state": "PARKED_VEHICLE", "sample_timestamp": 2000}
                ],
            },
        )
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    record = await client.async_get_change_record(
        "LJNABC12345678901", "vehicle_status"
    )

    assert record["vehl_state"] == "PARKED_VEHICLE"
    request = oauth_session.async_request.await_args
    assert request.args[1].endswith(
        "/vehicles/LJNABC12345678901/vehicle_status/changes"
    )


async def test_debug_trace_is_complete_but_redacts_sensitive_data(caplog) -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(
            200,
            {
                "request_id": "trace-123",
                "result_code": "success",
                "data": {
                    "vin": "LJNABC12345678901",
                    "soc": 52,
                    "chrg_state": 3,
                    "access_token": "must-not-leak",
                    "longitude": 4.123,
                },
            },
            {"Content-Type": "application/json", "Set-Cookie": "private"},
        )
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    with caplog.at_level(logging.DEBUG, logger="custom_components.nio_telematics.api"):
        await client.async_get_latest_vehicle_status("LJNABC12345678901")

    trace = caplog.text
    assert "/vehicles/{vin}/vehicle_status/latest" in trace
    assert "http_status=200" in trace
    assert "trace-123" in trace
    assert "'soc': 52" in trace
    assert "LJNABC12345678901" not in trace
    assert "must-not-leak" not in trace
    assert "4.123" not in trace
    assert "private" not in trace


async def test_resource_not_found_is_mapped() -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(200, {"result_code": "resource_not_found"})
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    with pytest.raises(NioResourceNotFoundError):
        await client.async_get_soc_status("LJNABC12345678901")


async def test_envelope_access_denied_is_mapped() -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(200, {"result_code": "access_denied"})
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    with pytest.raises(NioPermissionError):
        await client.async_get_latest_vehicle_status("LJNABC12345678901")


@pytest.mark.parametrize(
    ("status", "headers", "error"),
    [
        (401, {}, NioAuthenticationError),
        (403, {}, NioPermissionError),
        (429, {"Retry-After": "30"}, NioRateLimitError),
    ],
)
async def test_http_errors_are_mapped(status, headers, error) -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(return_value=response(status, {}, headers))
    client = NioApiClient(oauth_session, API_BASE_URL)
    with pytest.raises(error) as raised:
        await client.async_get_soc_status("LJNABC12345678901")
    if error is NioRateLimitError:
        assert raised.value.retry_after == 30


async def test_refresh_rejection_reaches_coordinator() -> None:
    """The API client must not misclassify HA's reauth error as a network error."""
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        side_effect=OAuth2TokenRequestReauthError(
            request_info=MagicMock(), domain="nio_telematics"
        )
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    with pytest.raises(OAuth2TokenRequestReauthError):
        await client.async_get_latest_vehicle_record("LJNABC12345678901")


async def test_transient_refresh_failure_is_retryable() -> None:
    """A temporary OAuth failure becomes an ordinary coordinator retry."""
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        side_effect=OAuth2TokenRequestTransientError(
            request_info=MagicMock(), domain="nio_telematics"
        )
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    with pytest.raises(NioApiError, match="temporarily unavailable") as error:
        await client.async_get_latest_vehicle_record("LJNABC12345678901")

    assert not isinstance(error.value, OAuth2TokenRequestReauthError)
