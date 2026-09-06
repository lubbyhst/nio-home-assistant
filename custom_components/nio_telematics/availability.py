"""Summarize NIO endpoint availability without Home Assistant dependencies."""

from __future__ import annotations

from collections.abc import Mapping

_AVAILABLE_STATUSES = frozenset({"success", "no_recent_data", "no_data"})


def overall_availability(endpoint_status: Mapping[str, str]) -> str:
    """Return the aggregate endpoint availability state."""
    if not endpoint_status:
        return "unavailable"
    statuses = set(endpoint_status.values())
    if statuses <= _AVAILABLE_STATUSES:
        return "available"
    if statuses & _AVAILABLE_STATUSES:
        return "partial"
    return "unavailable"


def availability_attributes(
    endpoint_status: Mapping[str, str],
) -> dict[str, object]:
    """Group endpoint names by their latest result."""
    return {
        "working_endpoints": sorted(
            endpoint
            for endpoint, status in endpoint_status.items()
            if status == "success"
        ),
        "empty_endpoints": sorted(
            endpoint
            for endpoint, status in endpoint_status.items()
            if status in {"no_recent_data", "no_data"}
        ),
        "permission_denied_endpoints": sorted(
            endpoint
            for endpoint, status in endpoint_status.items()
            if status == "permission_denied"
        ),
        "error_endpoints": {
            endpoint: status
            for endpoint, status in sorted(endpoint_status.items())
            if status not in _AVAILABLE_STATUSES and status != "permission_denied"
        },
        "endpoint_status": dict(sorted(endpoint_status.items())),
    }
