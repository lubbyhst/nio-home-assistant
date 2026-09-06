"""Data coordinator for NIO Open Telematics."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    NioApiClient,
    NioApiError,
    NioAuthenticationError,
    NioPermissionError,
    NioResourceNotFoundError,
)
from .const import CONF_VIN, DEFAULT_SCAN_INTERVAL, DOMAIN
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

    _CHANGE_ENDPOINTS = (
        "door_status",
        "fridge_status",
        "light_status",
        "window_status",
        "driving_data",
        "position_status",
        "trip_status",
        "cell_status",
        "extremum_data",
        "soc_status",
        "heating_status",
        "hvac_status",
        "driving_motor",
        "alarm_signal",
    )

    async def _async_update_data(self) -> NioVehicleData:
        try:
            latest_record = await self._client.async_get_latest_vehicle_record(
                self._vin
            )
            vehicle_status = NioSocStatus.from_payload(latest_record)
            self._telemetry["vehicle_status"] = latest_record
            endpoint_status = {"vehicle_status": "success"}
            energy_status = None
            for resource in self._CHANGE_ENDPOINTS:
                try:
                    record = await self._client.async_get_change_record(
                        self._vin, resource
                    )
                except NioResourceNotFoundError:
                    endpoint_status[resource] = "no_recent_data"
                    continue
                except NioPermissionError:
                    raise
                except NioApiError as err:
                    endpoint_status[resource] = type(err).__name__
                    self._LOGGER.debug(
                        "Optional NIO endpoint %s unavailable: %s", resource, err
                    )
                    continue
                self._telemetry[resource] = record
                endpoint_status[resource] = "success"
                if resource == "soc_status":
                    energy_status = NioSocStatus.from_payload(record)
            try:
                self._telemetry[
                    "odometer_report"
                ] = await self._client.async_get_odometer_report(self._vin)
                endpoint_status["odometer_report"] = "success"
            except NioResourceNotFoundError:
                endpoint_status["odometer_report"] = "no_data"
            except NioPermissionError:
                raise
            except NioApiError as err:
                endpoint_status["odometer_report"] = type(err).__name__
        except (NioAuthenticationError, NioPermissionError) as err:
            if isinstance(err, NioPermissionError):
                raise ConfigEntryAuthFailed(
                    "The NIO token is not authorized for all requested scopes. "
                    "Please reauthenticate this integration to refresh permissions."
                ) from err
            raise ConfigEntryAuthFailed(str(err)) from err
        except NioApiError as err:
            raise UpdateFailed(str(err)) from err
        if energy_status is None:
            soc_status = vehicle_status
        else:
            soc_status = type(vehicle_status)(
                soc=vehicle_status.soc
                if vehicle_status.soc is not None
                else energy_status.soc,
                remaining_range=energy_status.remaining_range,
                charging_state=energy_status.charging_state
                if energy_status.charging_state is not None
                else vehicle_status.charging_state,
                charging_target=energy_status.charging_target,
                maximum_soc=energy_status.maximum_soc,
                high_voltage_battery_current=(
                    energy_status.high_voltage_battery_current
                ),
                event_time=max(
                    filter(
                        None,
                        [vehicle_status.event_time, energy_status.event_time],
                    ),
                    default=None,
                ),
            )
        return NioVehicleData(
            vin=self._vin,
            soc_status=soc_status,
            fetched_at=datetime.now(UTC),
            telemetry=dict(self._telemetry),
            endpoint_status=endpoint_status,
        )
