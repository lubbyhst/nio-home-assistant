# NIO API Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align the integration with NIO's current 24-operation EU Open Telematics specification and correct documented time/value conversions.

**Architecture:** Keep the current ten-minute coordinator for the latest snapshot, 15 standard change feeds, and odometer reports. Add one explicit, allowlisted, response-only Home Assistant service for time-filtered vehicle-status history and the seven non-polled ADAS, NOMI ASR, and recall operations. Preserve upstream OAuth retry/reauth behavior and sanitize service and diagnostic payloads so credentials, precise coordinates, VINs, vehicle UUIDs, and signed URLs are not exposed.

**Tech Stack:** Python 3.14, Home Assistant custom integration, aiohttp OAuth session, pytest, Ruff.

## Source Contract

- Vehicle API OpenAPI: `https://open-eu.nio.com/portal-api/spec/vehicles` (`servers[0].url` is `https://open-api-eu.nio.com`).
- Portal reference: `https://open-eu.nio.com/docs/vehicles`.
- OAuth reference is embedded in the portal's current JavaScript bundle. The current implementation's authorization/token paths, Basic client authentication, PKCE, form encoding, and response envelope match it; `scope` is optional.
- The portal's getting-started example uses Unix seconds for `start_time` and `end_time`; `sample_timestamp` response fields are milliseconds. `vehicle_status.mileage` uses 0.1 km increments. `soc_status.remaining_range` is encoded as range × 10.

## Tasks

### Task 1: Correct request and telemetry units

**Files:** `custom_components/nio_telematics/api.py`, `custom_components/nio_telematics/models.py`, `custom_components/nio_telematics/sensor.py`, `tests/test_api.py`, `tests/test_models.py`.

1. Add failing assertions that SoC query bounds are Unix seconds, that range values are divided by ten (including invalid sentinel handling), and that vehicle mileage is divided by ten.
2. Run the focused tests and confirm they fail for the current behavior.
3. Implement only those conversions while retaining millisecond parsing for `sample_timestamp` and existing sensor scales.
4. Run the focused tests and then the complete test suite.

### Task 2: Add parameterized and non-polled operations

**Files:** `custom_components/nio_telematics/api.py`, `tests/test_api.py`.

The current implementation covers latest status, 15 change feeds, and odometer reports. Keep vehicle-status history polling intact, and expose its optional time bounds alongside the seven non-polled operations:

- `GET /vehicles/{vin}/adas/snapshot`
- `GET /vehicles/{vin}/adas/event`
- `POST /vehicles/{vin}/adas/snapshot/extract`
- `POST /vehicles/{vin}/adas/event/download`
- `GET /vehicles/{vin}/nomi/asr`
- `GET /aftersales/vehicles/{vin}/recalls`
- `GET /aftersales/recall_campaigns/{campaign_no}`

1. Write failing tests for each HTTP method, path, required/query parameter spelling, envelope handling, and redaction of URL fields. Verify history parameters remain Unix seconds and ADAS timestamps use nanoseconds.
2. Confirm the focused tests fail for the missing methods.
3. Add a shared authenticated request path for GET/POST and implement the allowlisted query dispatch. Keep all query values caller-supplied and do not poll expensive endpoints.
4. Run focused and complete tests.

### Task 3: Expose on-demand operations to Home Assistant

**Files:** `custom_components/nio_telematics/__init__.py`, `custom_components/nio_telematics/services.py` (new), `custom_components/nio_telematics/services.yaml` (new), `tests/test_services.py` (new).

1. Add failing tests for operation dispatch, config-entry selection, parameter validation, service response support, and unload cleanup.
2. Confirm the tests fail before implementation.
3. Register one response-only service with an explicit operation allowlist, service parameters for each spec operation, and config-entry selection. Return sanitized API envelopes; omit sensitive URL/location/token values.
4. Run focused and complete tests and validate the service YAML.

### Task 4: Refresh the API reference and compliance inventory

**Files:** `docs/nio-open-platform-api.md` (new), `README.md`, `tests/test_endpoints.py`.

1. Add a failing inventory assertion for the exact set of 24 documented vehicle/aftersales operation IDs.
2. Confirm the assertion fails before the API reference is refreshed.
3. Document the current operation catalog, parameters, units, hosts, OAuth contract, response envelope, supported polling versus on-demand behavior, and redaction rules. Link the official portal source.
4. Run focused and complete tests, Ruff, and verify the final diff against the fetched OpenAPI operation inventory.
