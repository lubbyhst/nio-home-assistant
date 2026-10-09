"""Tests for NIO on-demand Home Assistant services."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.nio_telematics.const import DOMAIN
from custom_components.nio_telematics.services import (
    SERVICE_QUERY,
    async_register_services,
    async_unregister_services,
)


@pytest.mark.asyncio
async def test_query_service_dispatches_and_redacts_sensitive_response(hass) -> None:
    coordinator = MagicMock()
    coordinator.async_call_on_demand = AsyncMock(
        return_value={
            "result_code": "success",
            "data": {
                "name": "asr.wav",
                "url": "https://s3.example.test/asr?signature=secret",
                "uuid": "record-uuid",
                "vehicle_uuid": "vehicle-uuid",
                "vin": "LJNABC12345678901",
                "longitude": 13.4,
                "access_token": "token-secret",
                "records": [{"index": index} for index in range(55)],
            },
        }
    )
    entry = MagicMock(
        entry_id="nio-entry",
        domain=DOMAIN,
        runtime_data=coordinator,
    )
    hass.config_entries.async_get_entry = MagicMock(return_value=entry)
    async_register_services(hass)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_QUERY,
        {
            "config_entry_id": "nio-entry",
            "operation": "nomi_asr_files",
            "limit": 5,
            "offset": 10,
        },
        blocking=True,
        return_response=True,
    )

    coordinator.async_call_on_demand.assert_awaited_once_with(
        "nomi_asr_files", limit=5, offset=10
    )
    assert response["data"]["name"] == "asr.wav"
    assert response["data"]["url"] == "**REDACTED**"
    assert response["data"]["uuid"] == "record-uuid"
    assert response["data"]["vehicle_uuid"] == "**REDACTED**"
    assert response["data"]["vin"] == "**REDACTED**"
    assert response["data"]["longitude"] == "**REDACTED**"
    assert response["data"]["access_token"] == "**REDACTED**"
    assert len(response["data"]["records"]) == 55


@pytest.mark.asyncio
async def test_query_service_rejects_missing_config_entry(hass) -> None:
    hass.config_entries.async_get_entry = MagicMock(return_value=None)
    async_register_services(hass)

    with pytest.raises(HomeAssistantError, match="configuration entry"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_QUERY,
            {
                "config_entry_id": "missing-entry",
                "operation": "vehicle_recalls",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.asyncio
async def test_unregister_removes_query_service(hass) -> None:
    async_register_services(hass)
    assert hass.services.has_service(DOMAIN, SERVICE_QUERY)

    async_unregister_services(hass)

    assert not hass.services.has_service(DOMAIN, SERVICE_QUERY)
