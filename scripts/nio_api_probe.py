"""Compare NIO snapshot/change calls without saving credentials or telemetry.

Run with --ha-kubernetes to read only the current NIO access token and VIN
from Home Assistant in memory. Never refresh its token outside HA: a rotating
refresh token could invalidate the running integration's stored credentials.
Without that option, credentials are requested using hidden terminal input.
"""

from __future__ import annotations

import argparse
import getpass
import json
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://open-api-eu.nio.com/api/1/telematics/vehicles/"


def credentials(namespace: str, deployment: str) -> tuple[str, str]:
    """Capture the selected entry privately; never print subprocess output."""
    code = (
        "import json,time; from pathlib import Path; "
        "entries=json.loads(Path('/config/.storage/core.config_entries')"
        ".read_text())['data']['entries']; "
        "entries=[e for e in entries if e['domain']=='nio_telematics']; "
        "assert len(entries)==1; d=entries[0]['data']; "
        "assert d['token']['expires_at']>time.time(); "
        "print(json.dumps({'vin':d['vin'],"
        "'access_token':d['token']['access_token']}))"
    )
    result = subprocess.run(
        [
            "kubectl",
            "exec",
            "-n",
            namespace,
            f"deploy/{deployment}",
            "-c",
            "homeassist",
            "--",
            "python3",
            "-c",
            code,
        ],
        capture_output=True,
        timeout=20,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Unable to read a single unexpired NIO entry from HA")
    data = json.loads(result.stdout)
    return data["vin"], data["access_token"]


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
            response = urlopen(request, timeout=20)
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
    parser.add_argument("--ha-kubernetes", action="store_true")
    parser.add_argument("--namespace", default="homeassist")
    parser.add_argument("--deployment", default="homeassist")
    parser.add_argument("--resource", default="soc_status")
    args = parser.parse_args()
    if args.ha_kubernetes:
        vin, token = credentials(args.namespace, args.deployment)
    else:
        vin = getpass.getpass("VIN (hidden): ").strip()
        token = getpass.getpass("Access token (hidden): ").strip()
    probe(vin, token, "latest", None)
    for window in (None, 600, 3600, 43200):
        probe(vin, token, args.resource, window)
    probe(vin, token, args.resource, 600, milliseconds=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired, KeyError, ValueError):
        raise SystemExit(
            "Credential access failed; no credentials were printed."
        ) from None
