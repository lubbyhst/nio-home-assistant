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
    NioInvalidParameterError,
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


async def test_soc_request_uses_ten_minute_millisecond_window_and_newest_record(
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
        "start_time": 1_999_400_000,
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
        "start_time": 1_999_700_000,
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
        "start_time": 1_999_700_000,
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
    assert request.args[1].endswith(f"/vehicles/LJNABC12345678901/{resource}/changes")


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
                "data": [{"vehl_state": "PARKED_VEHICLE", "sample_timestamp": 2000}],
            },
        )
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    record = await client.async_get_change_record("LJNABC12345678901", "vehicle_status")

    assert record["vehl_state"] == "PARKED_VEHICLE"
    request = oauth_session.async_request.await_args
    assert request.args[1].endswith(
        "/vehicles/LJNABC12345678901/vehicle_status/changes"
    )


@pytest.mark.parametrize(
    ("operation", "params", "method", "suffix", "expected_params", "headers"),
    [
        (
            "vehicle_status_history",
            {"start_time": 1_759_900_000, "end_time": 1_760_000_000},
            "GET",
            "/vehicles/{vin}/vehicle_status/changes",
            {"start_time": 1_759_900_000, "end_time": 1_760_000_000},
            {"Accept": "application/json"},
        ),
        (
            "adas_snapshots",
            {"start_ts": 1_759_900_000_000_000_000, "limit": 10, "offset": 0},
            "GET",
            "/vehicles/{vin}/adas/snapshot",
            {"startTs": 1_759_900_000_000_000_000, "limit": 10, "offset": 0},
            {"Accept": "application/json"},
        ),
        (
            "adas_events",
            {"end_ts": 1_760_000_000_000_000_000, "limit": 5},
            "GET",
            "/vehicles/{vin}/adas/event",
            {"endTs": 1_760_000_000_000_000_000, "limit": 5},
            {"Accept": "application/json"},
        ),
        (
            "extract_adas_snapshot",
            {"uuid": "snapshot-uuid"},
            "POST",
            "/vehicles/{vin}/adas/snapshot/extract",
            {"uuid": "snapshot-uuid"},
            {"Accept": "application/json"},
        ),
        (
            "download_adas_event",
            {"uuid": "event-uuid", "as_url": True},
            "POST",
            "/vehicles/{vin}/adas/event/download",
            {"uuid": "event-uuid", "asUrl": "true"},
            {"Accept": "application/json"},
        ),
        (
            "nomi_asr_files",
            {"limit": 20, "offset": 40},
            "GET",
            "/vehicles/{vin}/nomi/asr",
            {"limit": 20, "offset": 40},
            {"Accept": "application/json"},
        ),
        (
            "vehicle_recalls",
            {},
            "GET",
            "/aftersales/vehicles/{vin}/recalls",
            None,
            {"Accept": "application/json"},
        ),
        (
            "recall_campaign",
            {"campaign_no": "RC-2026-001", "accept_language": "de-DE"},
            "GET",
            "/aftersales/recall_campaigns/RC-2026-001",
            None,
            {"Accept": "application/json", "Accept-Language": "de-DE"},
        ),
    ],
)
async def test_on_demand_operations_match_official_paths_and_parameters(
    operation, params, method, suffix, expected_params, headers
) -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(200, {"result_code": "success", "data": {}})
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    await client.async_call_on_demand(operation, "LJNABC12345678901", **params)

    request = oauth_session.async_request.await_args
    assert request.args[0] == method
    path = request.args[1].removeprefix(API_BASE_URL)
    assert path == f"/api/1/telematics{suffix.replace('{vin}', 'LJNABC12345678901')}"
    if expected_params:
        assert request.kwargs["params"] == expected_params
    else:
        assert "params" not in request.kwargs
    assert request.kwargs["headers"] == headers


async def test_on_demand_operations_reject_unknown_operation() -> None:
    client = NioApiClient(MagicMock(), API_BASE_URL)

    with pytest.raises(ValueError, match="Unsupported NIO operation"):
        await client.async_call_on_demand("arbitrary_path", "LJNABC12345678901")


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
                    "url": "https://s3.example.test/report?signature=must-not-leak",
                    "uuid": "record-uuid-must-not-leak",
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
    assert "https://s3.example.test" not in trace
    assert "record-uuid-must-not-leak" not in trace
    assert "private" not in trace


@pytest.mark.parametrize("http_status", [200, 404])
async def test_resource_not_found_is_mapped(http_status) -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(http_status, {"result_code": "resource_not_found"})
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    with pytest.raises(NioResourceNotFoundError):
        await client.async_get_soc_status("LJNABC12345678901")


async def test_http_invalid_param_retains_typed_error() -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(400, {"result_code": "invalid_param"})
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    with pytest.raises(NioInvalidParameterError):
        await client.async_get_latest_vehicle_record("LJNABC12345678901")


async def test_generic_soc_poll_uses_bounded_energy_query(monkeypatch) -> None:
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
                    {"soc": 42, "sample_timestamp": 2000},
                ],
            },
        )
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    await client.async_get_change_record("LJNABC12345678901", "soc_status")

    assert oauth_session.async_request.await_args.kwargs["params"] == {
        "start_time": 1_999_400_000,
        "end_time": 2_000_000_000,
    }


async def test_sparse_invalid_energy_fields_preserve_older_valid_readings() -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(
            200,
            {
                "result_code": "success",
                "data": [
                    {"soc": 41, "remaining_range": 240, "sample_timestamp": 1000},
                    {
                        "soc": "unknown",
                        "remaining_range": 0xFFFFFFFE,
                        "sample_timestamp": 2000,
                    },
                ],
            },
        )
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    status = await client.async_get_soc_status("LJNABC12345678901")

    assert status.soc == 41
    assert status.remaining_range == 240


async def test_envelope_access_denied_is_mapped() -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(200, {"result_code": "access_denied"})
    )
    client = NioApiClient(oauth_session, API_BASE_URL)

    with pytest.raises(NioPermissionError):
        await client.async_get_latest_vehicle_status("LJNABC12345678901")


async def test_envelope_permission_denied_is_mapped() -> None:
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(
        return_value=response(200, {"result_code": "permission_denied"})
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


async def test_sparse_response_preserves_soc_and_range_sample_times() -> None:
    oauth = MagicMock()
    oauth.async_request = AsyncMock(
        return_value=response(
            200,
            {
                "result_code": "success",
                "data": [
                    {"soc": 50, "remaining_range": 210, "sample_timestamp": 1000},
                    {"chrg_state": "CHARGE_PROCESSING", "sample_timestamp": 2000},
                ],
            },
        )
    )
    status = await NioApiClient(oauth, API_BASE_URL).async_get_soc_status(
        "LJNABC12345678901"
    )
    from datetime import UTC, datetime

    assert status.event_time == datetime.fromtimestamp(1000, UTC)
    assert status.remaining_range_sample_time == datetime.fromtimestamp(1000, UTC)


@pytest.mark.parametrize("as_url", [True, False])
async def test_download_boolean_is_serialized_for_real_url_query(as_url) -> None:
    from yarl import URL

    async def request(method, url, **kwargs):
        query = URL(url).with_query(kwargs.get("params")).query
        assert query["asUrl"] == str(as_url).lower()
        return response(200, {"result_code": "success", "data": {}})

    oauth = MagicMock()
    oauth.async_request = AsyncMock(side_effect=request)
    await NioApiClient(oauth, API_BASE_URL).async_call_on_demand(
        "download_adas_event", "LJNABC12345678901", uuid="synthetic", as_url=as_url
    )
