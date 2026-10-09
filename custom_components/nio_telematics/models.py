"""Typed NIO Open Telematics data models."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

_VIN_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
_INVALID_REMAINING_RANGE_VALUES = {0xFFFFFFFE, 0xFFFFFFFF}


def normalize_vin(value: str) -> str:
    """Normalize and validate a standard 17-character VIN."""
    vin = value.strip().upper()
    if not _VIN_PATTERN.fullmatch(vin):
        raise ValueError("VIN must contain 17 valid characters")
    return vin


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _event_datetime(value: Any) -> datetime | None:
    timestamp = _optional_float(value)
    if timestamp is None:
        return None
    # Accept seconds and milliseconds without guessing beyond those formats.
    if timestamp > 10_000_000_000:
        timestamp /= 1000
    try:
        return datetime.fromtimestamp(timestamp, tz=UTC)
    except (OSError, OverflowError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class NioSocStatus:
    """Latest verified fields from a NIO SoC status record."""

    soc: float | None
    remaining_range: float | None
    charging_state: str | None
    charging_target: float | None
    maximum_soc: float | None
    high_voltage_battery_current: float | None
    event_time: datetime | None
    remaining_range_sample_time: datetime | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> NioSocStatus:
        """Parse only fields verified in the official SoC schema."""
        return cls(
            soc=_optional_float(payload.get("soc")),
            remaining_range=_remaining_range(payload.get("remaining_range")),
            charging_state=_optional_str(payload.get("chrg_state")),
            charging_target=_optional_float(payload.get("chrg_final_soc")),
            maximum_soc=_optional_float(payload.get("max_soc")),
            high_voltage_battery_current=_optional_float(
                payload.get("hivolt_btry_curnt")
            ),
            event_time=_event_datetime(
                payload.get("_sample_timestamps", {}).get(
                    "soc", payload.get("sample_timestamp")
                )
                if _optional_float(payload.get("soc")) is not None
                else payload.get("sample_timestamp")
            ),
            remaining_range_sample_time=_event_datetime(
                payload.get("_sample_timestamps", {}).get(
                    "remaining_range", payload.get("sample_timestamp")
                )
            )
            if _remaining_range(payload.get("remaining_range")) is not None
            else None,
        )

    @classmethod
    def merge(cls, *statuses: NioSocStatus) -> NioSocStatus:
        """Merge snapshots in priority order, keeping the newest timestamp."""

        def first(attribute: str) -> Any:
            return next(
                (
                    value
                    for status in statuses
                    if (value := getattr(status, attribute)) is not None
                ),
                None,
            )

        event_times = [status.event_time for status in statuses if status.event_time]
        return cls(
            soc=first("soc"),
            remaining_range=first("remaining_range"),
            charging_state=first("charging_state"),
            charging_target=first("charging_target"),
            maximum_soc=first("maximum_soc"),
            high_voltage_battery_current=first("high_voltage_battery_current"),
            event_time=max(event_times) if event_times else None,
            remaining_range_sample_time=first("remaining_range_sample_time"),
        )


@dataclass(frozen=True, slots=True)
class NioVehicleData:
    """Coordinator snapshot for one vehicle."""

    vin: str
    soc_status: NioSocStatus
    fetched_at: datetime
    telemetry: dict[str, dict[str, Any]]
    endpoint_status: dict[str, str]
    remaining_range_last_valid_at: datetime | None = None
    remaining_range_retained: bool = False


def _remaining_range(value: Any) -> float | None:
    """The live JSON API returns kilometers; omit invalid protocol sentinels."""
    number = _optional_float(value)
    if number is None or number < 0 or number in _INVALID_REMAINING_RANGE_VALUES:
        return None
    return number


_SOC_FIELD_ATTRIBUTES = {
    "soc": "soc",
    "remaining_range": "remaining_range",
    "chrg_state": "charging_state",
    "chrg_final_soc": "charging_target",
    "max_soc": "maximum_soc",
    "hivolt_btry_curnt": "high_voltage_battery_current",
}


def merge_energy_records(*records: dict[str, Any]) -> dict[str, Any]:
    """Merge valid fields by their own sample time, including across polls.

    `_sample_timestamps` is integration metadata, not a provider field. Keeping
    it alongside the raw fields preserves provenance through sparse merges.
    """
    merged: dict[str, Any] = {}
    timestamps: dict[str, Any] = {}
    for record in records:
        parsed = NioSocStatus.from_payload(record)
        record_times = record.get("_sample_timestamps", {})
        for key, value in record.items():
            if key in {"sample_timestamp", "_sample_timestamps"} or value is None:
                continue
            if (
                key in _SOC_FIELD_ATTRIBUTES
                and getattr(parsed, _SOC_FIELD_ATTRIBUTES[key]) is None
            ):
                continue
            timestamp = record_times.get(key, record.get("sample_timestamp"))
            candidate_time = _event_datetime(timestamp)
            previous_time = _event_datetime(timestamps.get(key))
            if previous_time is not None and (
                candidate_time is None or candidate_time < previous_time
            ):
                continue
            merged[key] = value
            timestamps[key] = timestamp
    valid_timestamps = [
        value for value in timestamps.values() if _event_datetime(value) is not None
    ]
    merged["sample_timestamp"] = max(
        valid_timestamps, key=_event_datetime, default=None
    )
    merged["_sample_timestamps"] = timestamps
    return merged
