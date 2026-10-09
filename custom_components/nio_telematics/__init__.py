"""NIO Open Telematics integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_entry_oauth2_flow

from .api import NioApiClient
from .const import (
    API_BASE_URL,
    CONF_SCOPE_REVISION,
    DOMAIN,
    OAUTH_SCOPE_REVISION,
    PLATFORMS,
)
from .coordinator import NioDataUpdateCoordinator
from .services import async_register_services, async_unregister_services

type NioConfigEntry = ConfigEntry[NioDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NioConfigEntry) -> bool:
    """Set up NIO Open Telematics from a config entry."""
    if entry.data.get(CONF_SCOPE_REVISION) != OAUTH_SCOPE_REVISION:
        raise ConfigEntryAuthFailed(
            "NIO telemetry permissions have changed; reauthentication is required"
        )
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    client = NioApiClient(
        oauth_session,
        API_BASE_URL,
    )
    coordinator = NioDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NioConfigEntry) -> bool:
    """Unload a NIO config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and not any(
        candidate.entry_id != entry.entry_id
        and candidate.state is ConfigEntryState.LOADED
        for candidate in hass.config_entries.async_entries(DOMAIN)
    ):
        async_unregister_services(hass)
    return unloaded
