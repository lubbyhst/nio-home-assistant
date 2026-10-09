"""Tests for NIO telemetry value conversions."""

from collections.abc import Callable
from types import SimpleNamespace

import homeassistant.helpers.entity_platform as entity_platform

if not hasattr(entity_platform, "AddConfigEntryEntitiesCallback"):
    entity_platform.AddConfigEntryEntitiesCallback = Callable  # type: ignore[attr-defined]

from custom_components.nio_telematics.sensor import SENSORS


def test_pack_voltage_is_distinct_from_individual_cell_voltage() -> None:
    pack_sensor = next(
        description
        for description in SENSORS
        if description.key == "battery_pack_voltage"
    )
    data = SimpleNamespace(
        telemetry={
            "soc_status": {
                "btry_paks": [
                    {"btry_pak_voltage": 384.5},
                ]
            }
        }
    )

    assert pack_sensor.value_fn(data) == 384.5
    assert pack_sensor.entity_registry_enabled_default is True
    assert pack_sensor.suggested_display_precision == 1

    data.telemetry["soc_status"]["btry_paks"] = [
        {"btry_pak_voltage": 384.5},
        {"btry_pak_voltage": 386.0},
    ]
    assert pack_sensor.value_fn(data) is None


def test_cell_voltage_display_keeps_three_decimal_places() -> None:
    for key in ("highest_cell_voltage", "lowest_cell_voltage"):
        sensor = next(description for description in SENSORS if description.key == key)
        assert sensor.suggested_display_precision == 3


def test_live_cell_voltages_are_already_in_volts() -> None:
    data = SimpleNamespace(
        telemetry={
            "extremum_data": {
                "sin_btry_hist_volt": 3.75,
                "sin_btry_lwst_volt": 3.65,
            }
        }
    )
    for key, expected in (
        ("highest_cell_voltage", 3.75),
        ("lowest_cell_voltage", 3.65),
    ):
        sensor = next(description for description in SENSORS if description.key == key)
        assert sensor.value_fn(data) == expected


def test_live_vehicle_odometer_is_already_in_kilometers() -> None:
    sensor = next(
        description for description in SENSORS if description.key == "odometer"
    )
    data = SimpleNamespace(telemetry={"vehicle_status": {"mileage": 32145}})

    assert sensor.value_fn(data) == 32145


def test_vehicle_odometer_omits_invalid_api_sentinel() -> None:
    sensor = next(
        description for description in SENSORS if description.key == "odometer"
    )
    data = SimpleNamespace(telemetry={"vehicle_status": {"mileage": 0xFFFFFFFF}})

    assert sensor.value_fn(data) is None
