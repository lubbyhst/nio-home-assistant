"""Coordinator authentication-failure regression tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2TokenRequestReauthError
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.nio_telematics.api import NioApiError, NioPermissionError
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
