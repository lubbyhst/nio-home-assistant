"""Tests for bounded, privacy-safe telemetry attributes."""

import json

from custom_components.nio_telematics.diagnostics import TO_REDACT
from custom_components.nio_telematics.privacy import (
    MAX_DIAGNOSTIC_ATTRIBUTE_BYTES,
    MAX_DIAGNOSTIC_LIST_ITEMS,
    safe_diagnostic_attributes,
)


def test_diagnostic_attributes_redact_sensitive_values_and_bound_lists() -> None:
    payload = {
        "vin": "LJNABC12345678901",
        "latitude": 52.5,
        "longitude": 13.4,
        "access_token": "secret",
        "download_url": "https://example.invalid/private",
        "records": [
            {"value": index} for index in range(MAX_DIAGNOSTIC_LIST_ITEMS + 5)
        ],
    }

    attributes = safe_diagnostic_attributes(payload)

    assert attributes["vin"] == "**REDACTED**"
    assert attributes["latitude"] == "**REDACTED**"
    assert attributes["longitude"] == "**REDACTED**"
    assert attributes["access_token"] == "**REDACTED**"
    assert attributes["download_url"] == "**REDACTED**"
    assert len(attributes["records"]) == MAX_DIAGNOSTIC_LIST_ITEMS
    assert len(json.dumps(attributes)) <= MAX_DIAGNOSTIC_ATTRIBUTE_BYTES


def test_diagnostic_attributes_truncate_oversized_payloads() -> None:
    attributes = safe_diagnostic_attributes({"payload": "x" * 20_000})

    assert attributes == {"payload_truncated": True}


def test_diagnostics_redact_sensitive_telemetry_keys() -> None:
    assert {
        "latitude",
        "longitude",
        "lat",
        "lon",
        "lng",
        "url",
        "vehicle_uuid",
    } <= TO_REDACT
