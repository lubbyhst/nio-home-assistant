"""Coordinator authentication-failure regression tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2TokenRequestReauthError
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.nio_telematics.api import NioApiError
from custom_components.nio_telematics.const import CONF_VIN
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
