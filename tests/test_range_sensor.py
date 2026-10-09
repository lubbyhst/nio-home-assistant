"""Range-retention migration regression tests."""

import math
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from custom_components.nio_telematics.sensor import (
    _last_recorded_range,
    _range_number,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("213.0", 213.0),
        (0, 0.0),
        ("unknown", None),
        ("unavailable", None),
        (None, None),
        (-1, None),
        (math.inf, None),
    ],
)
def test_only_real_recorded_range_is_restored(
    raw: object, expected: float | None
) -> None:
    assert _range_number(raw) == expected


def test_migration_skips_newer_unknown_recorder_state() -> None:
    sample_time = datetime(2026, 10, 9, 18, 58, tzinfo=UTC)
    states = [
        SimpleNamespace(state="213.0", last_changed=sample_time),
        SimpleNamespace(state="unknown", last_changed=sample_time),
    ]
    assert _last_recorded_range(states) == (213.0, sample_time.isoformat())
