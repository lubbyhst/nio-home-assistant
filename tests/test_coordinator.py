"""Coordinator authentication-failure regression tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2TokenRequestReauthError
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.nio_telematics.api import (
    NioApiError,
    NioPermissionError,
    NioResourceNotFoundError,
)
from custom_components.nio_telematics.const import CONF_VIN, DOMAIN
from custom_components.nio_telematics.coordinator import NioDataUpdateCoordinator


async def test_rejected_refresh_becomes_config_entry_auth_failure(
    hass: HomeAssistant,
) -> None:
    """Coordinator must surface a rejected grant to HA's reauth machinery."""
    entry = MagicMock()
    entry.data = {CONF_VIN: "LJNABC12345678901"}
    client = MagicMock()
    client.async_get_latest_vehicle_record = AsyncMock(
        side_effect=OAuth2TokenRequestReauthError(
            request_info=MagicMock(), domain="nio_telematics"
        )
    )
    coordinator = NioDataUpdateCoordinator(hass, entry, client)

    with pytest.raises(ConfigEntryAuthFailed, match="reauthentication is required"):
        await coordinator._async_update_data()


async def test_temporary_refresh_failure_remains_retryable(hass: HomeAssistant) -> None:
    """Temporary token-service errors must not become auth failures."""
    entry = MagicMock()
    entry.data = {CONF_VIN: "LJNABC12345678901"}
    client = MagicMock()
    client.async_get_latest_vehicle_record = AsyncMock(
        side_effect=NioApiError("NIO OAuth token service is temporarily unavailable")
    )
    coordinator = NioDataUpdateCoordinator(hass, entry, client)

    with pytest.raises(UpdateFailed, match="temporarily unavailable"):
        await coordinator._async_update_data()


async def test_vehicle_status_changes_is_polled_without_breaking_optional_feeds(
    hass: HomeAssistant,
) -> None:
    """A denied optional feed must not stop vehicle-status change polling."""
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


@pytest.mark.parametrize("energy_soc", [57.5, 0])
async def test_energy_soc_takes_priority_over_latest_snapshot(
    hass: HomeAssistant, energy_soc: float
) -> None:
    """The dedicated energy source is authoritative, including real zero."""
    entry = MagicMock(data={CONF_VIN: "LJNABC12345678901"})
    client = MagicMock()
    client.async_get_latest_vehicle_record = AsyncMock(
        return_value={"soc": 0 if energy_soc else 50, "sample_timestamp": 3000}
    )
    client.async_get_change_record = AsyncMock(
        return_value={
            "soc": energy_soc,
            "remaining_range": 240,
            "sample_timestamp": 2000,
        }
    )
    client.async_get_odometer_report = AsyncMock(return_value={})
    coordinator = NioDataUpdateCoordinator(hass, entry, client)
    coordinator._CHANGE_ENDPOINTS = ("soc_status",)

    data = await coordinator._async_update_data()

    assert data.soc_status.soc == energy_soc
    assert data.soc_status.remaining_range == 240
    assert data.soc_status.event_time == datetime.fromtimestamp(2000, UTC)

    coordinator.async_set_updated_data(data)
    client.async_get_change_record.side_effect = NioResourceNotFoundError()
    next_data = await coordinator._async_update_data()

    assert next_data.soc_status.soc == energy_soc
    assert next_data.soc_status.remaining_range == 240
    assert next_data.soc_status.event_time == datetime.fromtimestamp(2000, UTC)
    assert next_data.endpoint_status["soc_status"] == "no_recent_data"


async def test_sparse_energy_poll_preserves_known_fields(hass: HomeAssistant) -> None:
    entry = MagicMock(data={CONF_VIN: "LJNABC12345678901"})
    client = MagicMock()
    client.async_get_latest_vehicle_record = AsyncMock(return_value={"soc": 0})
    client.async_get_change_record = AsyncMock(
        side_effect=[
            {"soc": 57.5, "remaining_range": 240, "sample_timestamp": 1000},
            {"soc": None, "chrg_state": "CHARGE_PROCESSING", "sample_timestamp": 2000},
        ]
    )
    client.async_get_odometer_report = AsyncMock(return_value={})
    coordinator = NioDataUpdateCoordinator(hass, entry, client)
    coordinator._CHANGE_ENDPOINTS = ("soc_status",)

    first = await coordinator._async_update_data()
    coordinator.async_set_updated_data(first)
    data = await coordinator._async_update_data()

    assert data.soc_status.soc == 57.5
    assert data.soc_status.remaining_range == 240
    assert data.soc_status.charging_state == "CHARGE_PROCESSING"
    assert data.soc_status.event_time == datetime.fromtimestamp(1000, UTC)
    assert data.remaining_range_last_valid_at == datetime.fromtimestamp(1000, UTC)
    assert data.remaining_range_retained


async def test_range_survives_sparse_change_feed(hass: HomeAssistant) -> None:
    """A missing energy event and a vehicle placeholder must not erase range."""
    entry = MagicMock()
    entry.data = {CONF_VIN: "LJNABC12345678901"}
    client = MagicMock()
    client.async_get_latest_vehicle_record = AsyncMock(
        return_value={"soc": 0, "remaining_range": 0}
    )
    energy_records = iter([{"remaining_range": 213}, None])

    async def get_change_record(_vin: str, resource: str) -> dict:
        if resource == "soc_status":
            record = next(energy_records)
            if record is not None:
                return record
        raise NioResourceNotFoundError("No recent data")

    client.async_get_change_record = get_change_record
    client.async_get_odometer_report = AsyncMock(
        side_effect=NioResourceNotFoundError("No recent data")
    )
    coordinator = NioDataUpdateCoordinator(hass, entry, client)
    first = await coordinator._async_update_data()
    assert first.soc_status.remaining_range == 213
    assert not first.remaining_range_retained

    coordinator.async_set_updated_data(first)
    second = await coordinator._async_update_data()
    assert second.soc_status.remaining_range == 213
    assert second.remaining_range_retained


async def test_older_overlapping_energy_record_does_not_regress_state(
    hass: HomeAssistant,
) -> None:
    entry = MagicMock(data={CONF_VIN: "LJNABC12345678901"})
    client = MagicMock()
    client.async_get_latest_vehicle_record = AsyncMock(return_value={"soc": 0})
    client.async_get_change_record = AsyncMock(
        side_effect=[
            {"soc": 50, "remaining_range": 210, "sample_timestamp": 2000},
            {"soc": 40, "remaining_range": 180, "sample_timestamp": 1000},
        ]
    )
    client.async_get_odometer_report = AsyncMock(return_value={})
    coordinator = NioDataUpdateCoordinator(hass, entry, client)
    coordinator._CHANGE_ENDPOINTS = ("soc_status",)
    first = await coordinator._async_update_data()
    coordinator.async_set_updated_data(first)
    data = await coordinator._async_update_data()
    assert data.soc_status.soc == 50
    assert data.soc_status.remaining_range == 210
    assert data.remaining_range_last_valid_at == datetime.fromtimestamp(2000, UTC)
    assert data.remaining_range_retained


async def test_newer_positive_vehicle_range_replaces_cached_energy(hass) -> None:
    entry = MagicMock(data={CONF_VIN: "LJNABC12345678901"})
    client = MagicMock()
    client.async_get_latest_vehicle_record = AsyncMock(
        side_effect=[
            {"soc": 0, "remaining_range": 0, "sample_timestamp": 1000},
            {"soc": 0, "remaining_range": 220, "sample_timestamp": 2000},
            {"soc": 0, "remaining_range": 0, "sample_timestamp": 3000},
        ]
    )
    client.async_get_change_record = AsyncMock(
        side_effect=[
            {"soc": 50, "remaining_range": 210, "sample_timestamp": 1000},
            NioResourceNotFoundError(),
            NioResourceNotFoundError(),
        ]
    )
    client.async_get_odometer_report = AsyncMock(return_value={})
    coordinator = NioDataUpdateCoordinator(hass, entry, client)
    coordinator._CHANGE_ENDPOINTS = ("soc_status",)
    first = await coordinator._async_update_data()
    coordinator.async_set_updated_data(first)
    second = await coordinator._async_update_data()
    assert second.soc_status.soc == 50
    assert second.soc_status.remaining_range == 220
    assert second.remaining_range_last_valid_at == datetime.fromtimestamp(2000, UTC)
    assert not second.remaining_range_retained
    coordinator.async_set_updated_data(second)
    third = await coordinator._async_update_data()
    assert third.soc_status.remaining_range == 220
    assert third.remaining_range_retained
    assert third.remaining_range_last_valid_at == datetime.fromtimestamp(2000, UTC)


async def test_first_partial_energy_record_does_not_block_vehicle_range(hass) -> None:
    entry = MagicMock(data={CONF_VIN: "LJNABC12345678901"})
    client = MagicMock()
    client.async_get_latest_vehicle_record = AsyncMock(
        return_value={
            "remaining_range": 220,
            "sample_timestamp": 1000,
        }
    )
    client.async_get_change_record = AsyncMock(
        return_value={
            "chrg_state": "CHARGE_PROCESSING",
            "sample_timestamp": 2000,
        }
    )
    client.async_get_odometer_report = AsyncMock(return_value={})
    coordinator = NioDataUpdateCoordinator(hass, entry, client)
    coordinator._CHANGE_ENDPOINTS = ("soc_status",)
    data = await coordinator._async_update_data()
    assert data.soc_status.remaining_range == 220
    assert data.remaining_range_last_valid_at == datetime.fromtimestamp(1000, UTC)
    assert not data.remaining_range_retained
