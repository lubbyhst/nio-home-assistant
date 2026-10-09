"""On-demand NIO API services."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .api import ON_DEMAND_OPERATIONS
from .const import DOMAIN
from .privacy import redact_sensitive_data

SERVICE_QUERY = "query"

_NON_NEGATIVE_INTEGER = vol.All(vol.Coerce(int), vol.Range(min=0))
_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): cv.string,
        vol.Required("operation"): vol.In(ON_DEMAND_OPERATIONS),
        vol.Optional("start_time"): _NON_NEGATIVE_INTEGER,
        vol.Optional("end_time"): _NON_NEGATIVE_INTEGER,
        vol.Optional("start_ts"): _NON_NEGATIVE_INTEGER,
        vol.Optional("end_ts"): _NON_NEGATIVE_INTEGER,
        vol.Optional("limit"): _NON_NEGATIVE_INTEGER,
        vol.Optional("offset"): _NON_NEGATIVE_INTEGER,
        vol.Optional("uuid"): cv.string,
        vol.Optional("as_url"): bool,
        vol.Optional("campaign_no"): cv.string,
        vol.Optional("accept_language"): cv.string,
    }
)


async def _async_handle_query(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Dispatch one allowlisted query through the selected config entry."""
    entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
    if entry is None or entry.domain != DOMAIN:
        raise HomeAssistantError("The selected NIO configuration entry was not found")
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        raise HomeAssistantError("The selected NIO configuration entry is not loaded")

    operation = call.data["operation"]
    parameter_names = {
        "start_time",
        "end_time",
        "start_ts",
        "end_ts",
        "limit",
        "offset",
        "uuid",
        "as_url",
        "campaign_no",
        "accept_language",
    }
    parameters = {key: call.data[key] for key in parameter_names if key in call.data}
    payload = await coordinator.async_call_on_demand(operation, **parameters)
    # The data UUID is an input to the follow-up extraction/download operations.
    return redact_sensitive_data(payload, preserve_data_uuid=True)


def async_register_services(hass: HomeAssistant) -> None:
    """Register NIO's on-demand API query service once per Home Assistant."""
    if hass.services.has_service(DOMAIN, SERVICE_QUERY):
        return

    async def handle_query(call: ServiceCall) -> dict[str, Any]:
        return await _async_handle_query(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_QUERY,
        handle_query,
        schema=_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Remove NIO services after the final config entry unloads."""
    if hass.services.has_service(DOMAIN, SERVICE_QUERY):
        hass.services.async_remove(DOMAIN, SERVICE_QUERY)
