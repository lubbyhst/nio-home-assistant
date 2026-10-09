"""Tests for NIO telemetry value conversions."""

from collections.abc import Callable
from types import SimpleNamespace

import homeassistant.helpers.entity_platform as entity_platform

if not hasattr(entity_platform, "AddConfigEntryEntitiesCallback"):
    entity_platform.AddConfigEntryEntitiesCallback = Callable  # type: ignore[attr-defined]

from custom_components.nio_telematics.sensor import SENSORS


def test_vehicle_odometer_uses_tenths_of_a_kilometer() -> None:
    sensor = next(
        description for description in SENSORS if description.key == "odometer"
    )
    data = SimpleNamespace(telemetry={"vehicle_status": {"mileage": 123456}})

    assert sensor.value_fn(data) == 12345.6


def test_vehicle_odometer_omits_invalid_api_sentinel() -> None:
    sensor = next(
        description for description in SENSORS if description.key == "odometer"
    )
    data = SimpleNamespace(telemetry={"vehicle_status": {"mileage": 0xFFFFFFFF}})

    assert sensor.value_fn(data) is None
