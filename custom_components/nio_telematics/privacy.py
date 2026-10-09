"""Privacy and size limits for NIO telemetry data."""

from __future__ import annotations

import json
import re
from typing import Any

MAX_DIAGNOSTIC_ATTRIBUTE_BYTES = 12_000
MAX_DIAGNOSTIC_LIST_ITEMS = 50
MAX_DIAGNOSTIC_NESTING = 8

_SENSITIVE_KEY_PARTS = (
    "access_token",
    "authorization",
    "client_id",
    "client_secret",
    "code_verifier",
    "latitude",
    "longitude",
    "refresh_token",
    "token",
    "url",
    "uuid",
    "vehicle_uuid",
    "vin",
)
_VIN_IN_TEXT = re.compile(
    r"(?<![A-Z0-9])[A-HJ-NPR-Z0-9]{17}(?![A-Z0-9])", re.IGNORECASE
)


def _is_sensitive_key(key: str, *, preserve_data_uuid: bool = False) -> bool:
    normalized_key = key.casefold()
    return any(
        part in normalized_key
        for part in _SENSITIVE_KEY_PARTS
        if not (preserve_data_uuid and part == "uuid")
    )


def _redact_value(
    value: Any,
    *,
    key: str = "",
    depth: int = 0,
    preserve_data_uuid: bool = False,
    bounded: bool = True,
) -> Any:
    if _is_sensitive_key(key, preserve_data_uuid=preserve_data_uuid):
        return "**REDACTED**"
    if isinstance(value, dict):
        return {
            str(item_key): _redact_value(
                item_value,
                key=str(item_key),
                depth=depth + 1,
                preserve_data_uuid=preserve_data_uuid,
                bounded=bounded,
            )
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        if bounded and depth >= MAX_DIAGNOSTIC_NESTING:
            return []
        items = value[:MAX_DIAGNOSTIC_LIST_ITEMS] if bounded else value
        return [
            _redact_value(
                item,
                depth=depth + 1,
                preserve_data_uuid=preserve_data_uuid,
                bounded=bounded,
            )
            for item in items
        ]
    if isinstance(value, tuple):
        items = value[:MAX_DIAGNOSTIC_LIST_ITEMS] if bounded else value
        return tuple(
            _redact_value(
                item,
                depth=depth + 1,
                preserve_data_uuid=preserve_data_uuid,
                bounded=bounded,
            )
            for item in items
        )
    if isinstance(value, str):
        return _VIN_IN_TEXT.sub("**REDACTED_VIN**", value)
    return value


def redact_debug_value(value: Any, *, key: str = "") -> Any:
    """Recursively redact credentials, vehicle IDs, and precise location data."""
    return _redact_value(value, key=key)


def redact_sensitive_data(value: Any, *, preserve_data_uuid: bool = False) -> Any:
    """Redact sensitive API fields, optionally retaining data UUIDs."""
    return _redact_value(value, preserve_data_uuid=preserve_data_uuid, bounded=False)


def safe_endpoint(path: str) -> str:
    """Return an endpoint path with any VIN removed."""
    path = _VIN_IN_TEXT.sub("{vin}", path)
    return re.sub(r"(/recall_campaigns/)[^/?]+", r"\1{campaign_no}", path)


def safe_diagnostic_attributes(value: Any) -> dict[str, Any]:
    """Return bounded, privacy-safe data suitable for entity attributes."""
    safe_value = _redact_value(value)
    attributes = safe_value if isinstance(safe_value, dict) else {"value": safe_value}
    try:
        encoded = json.dumps(attributes, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return {"payload_truncated": True}
    if len(encoded.encode()) > MAX_DIAGNOSTIC_ATTRIBUTE_BYTES:
        return {"payload_truncated": True}
    return attributes
