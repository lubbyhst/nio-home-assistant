"""Tests for NIO coordinator endpoint isolation."""

from unittest.mock import AsyncMock, MagicMock

from custom_components.nio_telematics.api import NioPermissionError
from custom_components.nio_telematics.const import CONF_VIN, DOMAIN
from custom_components.nio_telematics.coordinator import NioDataUpdateCoordinator


async def test_vehicle_status_changes_is_polled_without_breaking_optional_feeds(
    hass,
) -> None:
    entry = MagicMock(
        data={CONF_VIN: "LJNABC12345678901"},
        domain=DOMAIN,
        entry_id="test-entry",
        title="NIO",
    )
    client = MagicMock()
    client.async_get_latest_vehicle_record = AsyncMock(
        return_value={
            "soc": 50,
            "vehl_state": "PARKED_VEHICLE",
            "sample_timestamp": 2000,
        }
    )
    client.async_get_change_record = AsyncMock()

    async def change_record(vin: str, resource: str) -> dict:
        if resource == "door_status":
            raise NioPermissionError("denied")
        return {"sample_timestamp": 2000, "resource": resource}

    client.async_get_change_record.side_effect = change_record
    client.async_get_odometer_report = AsyncMock(
        return_value={"value": 123, "recorded_at": "2026-09-17"}
    )
    coordinator = NioDataUpdateCoordinator(hass, entry, client)

    data = await coordinator._async_update_data()

    client.async_get_change_record.assert_any_await(
        "LJNABC12345678901", "vehicle_status"
    )
    assert data.endpoint_status["vehicle_status_changes"] == "success"
    assert data.endpoint_status["door_status"] == "permission_denied"
    assert data.telemetry["vehicle_status_changes"]["resource"] == "vehicle_status"
