"""Compare NIO snapshot/change calls without saving credentials or telemetry.

VIN and a temporary access token are requested using hidden terminal input.
Never refresh Home Assistant's token independently: a rotating refresh token
could invalidate the running integration's stored credentials.
"""

from __future__ import annotations

import argparse
import getpass
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

BASE_URL = "https://open-api-eu.nio.com/api/1/telematics/vehicles/"


class _NoRedirect(HTTPRedirectHandler):
    """Keep a bearer credential bound to the requested API endpoint."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe(
    vin: str, token: str, resource: str, window: int | None, milliseconds: bool = False
) -> None:
    """Print only response structure, record age, and zero/nonzero indicators."""
    end = int(time.time())
    params = {}
    if window is not None:
        multiplier = 1000 if milliseconds else 1
        params = {
            "start_time": (end - window) * multiplier,
            "end_time": end * multiplier,
        }
    path = "latest" if resource == "latest" else "changes"
    name = "vehicle_status" if resource == "latest" else resource
    url = f"{BASE_URL}{vin}/{name}/{path}"
    if params:
        url += "?" + urlencode(params)
    summary = {
        "resource": resource,
        "window_seconds": window,
        "time_unit": "milliseconds" if milliseconds else "seconds",
    }
    request = Request(
        url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
    )
    try:
        try:
            response = build_opener(_NoRedirect).open(request, timeout=20)
        except HTTPError as error:
            response = error
        with response:
            summary["http_status"] = response.code
            payload = json.load(response)
        # Only allow a short identifier, never arbitrary server error text.
        result = payload.get("result_code")
        summary["result_code"] = (
            result
            if isinstance(result, str)
            and len(result) < 50
            and all(c.isalnum() or c == "_" for c in result)
            else "unknown"
        )
        data = payload.get("data")
        records = data if isinstance(data, list) else [data]
        records = [record for record in records if isinstance(record, dict)]
        summary["record_count"] = len(records)
        if records:
            newest = max(records, key=lambda r: r.get("sample_timestamp") or 0)
            summary["field_names"] = sorted(newest)
            summary["soc_present"] = newest.get("soc") is not None
            summary["soc_is_zero"] = newest.get("soc") == 0
            timestamp = newest.get("sample_timestamp")
            if isinstance(timestamp, (int, float)):
                summary["record_age_seconds"] = round(end - timestamp / 1000)
    except (URLError, ValueError, TypeError) as error:
        summary["error_type"] = type(error).__name__
    print(json.dumps(summary), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource", default="soc_status")
    args = parser.parse_args()
    vin = getpass.getpass("VIN (hidden): ").strip()
    token = getpass.getpass("Access token (hidden): ").strip()
    probe(vin, token, "latest", None)
    for window in (None, 600, 3600, 43200):
        probe(vin, token, args.resource, window)
    probe(vin, token, args.resource, 600, milliseconds=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, KeyError, ValueError):
        raise SystemExit(
            "Credential access failed; no credentials were printed."
        ) from None
