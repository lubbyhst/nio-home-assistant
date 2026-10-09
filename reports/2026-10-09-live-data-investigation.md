# NIO integration live data investigation — 2026-10-09

Local Python calls reused the running Home Assistant integration's unexpired
access token. No credentials were requested, saved, printed, or independently
refreshed. The installed integration sources matched this checkout before
changes.

## Confirmed findings

- Starting charging produced fresh, successful SoC, range, body, cell, and
  battery-extremum responses. Before charging, most of these change feeds had
  no records. This supports activity-dependent telemetry for this vehicle;
  it does not establish every condition under which NIO sends data.
- `vehicle_status/latest` continued returning zero SoC while
  `soc_status/changes` returned nonzero SoC matching the app. The coordinator
  preferred the snapshot zero and hid the working energy reading.
- Direct change requests with second time bounds returned HTTP 400
  `invalid_param`. Ten- and thirty-minute millisecond bounds were accepted;
  hour and longer bounds were rejected. A millisecond position-data request
  returned HTTP 200 `success`, providing an independent successful call.
- Empty feeds returned HTTP 404 `resource_not_found`. The integration checked
  generic HTTP errors first, causing the displayed `NioApiError`.
- Range and mileage matched the app/car before dividing by ten. Cell voltage
  already used volts; another multiplication by 0.001 caused the graph's
  very small values.
- NIO still supplied no charging-state value while the car was charging.
  This remains upstream missing data; the fix does not invent a value.

## Implemented behavior

Use energy-feed SoC first, preserve valid sparse fields and last-known energy
through empty polls, retain the energy sample timestamp, poll every five
minutes with a ten-minute SoC window, and map business errors on HTTP 400/404.
Remove the verified duplicate range/mileage/cell-voltage conversions.
Other unit conversions and the OAuth lifecycle remain unchanged.

Tests cover energy priority including legitimate zero, empty and sparse
updates, invalid-field fallback, timestamp retention, millisecond bounds,
smaller-window retry, HTTP errors, and the corrected JSON units. The local
probe is `scripts/nio_api_probe.py`; run with `--ha-kubernetes` to use HA's
single unexpired NIO entry or omit it for hidden VIN/token prompts.

Validation including the pack-voltage addition: 97 tests and 6 subtests passed; Ruff checks,
formatting checks, and `git diff --check` passed. A final real coordinator
request confirmed SoC and range equal the energy API fields, odometer equals
the car's stated mileage, cell-voltage sensors equal the API's volt values,
and the energy sample timestamp is preserved. Code review's invalid-field
and stale-timestamp findings were fixed and regression-tested.

## Limits

Findings are application/vehicle-specific. No long-duration OAuth refresh
claim is made from these tests. The in-memory cache does not survive a
Home Assistant restart. Fresh energy data is then needed again.

## Installation and running-entity verification

With user approval, the six changed component files were installed into
Home Assistant and restarted after backing up the old component. File hashes
match the tested source, its HTTP endpoint returned 200, and NIO startup logs
had no detected errors.

A read-only recorder query confirmed new nonzero SoC, range in kilometres,
the correct car odometer, plausible cell voltages, and `success` for both SoC
and latest vehicle API diagnostic entities. This verifies the installed
integration, in addition to the independent local API reproduction.

The live install is a source patch; HACS still displays the unchanged base
manifest version. A HACS redownload can replace it until these changes are
merged into the installed release. Test fixture measurements are synthetic;
no private vehicle payloads or credentials are included in source control.

The complete battery-pack voltage is also available within the energy feed's
single battery-pack record. It is exposed separately from cell voltages, which
are individually only a few volts. Cell sensors display three decimal places.
