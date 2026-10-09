# NIO EU Open Telematics API

This working contract summary was checked against NIO's portal on 2026-10-09.
The live [vehicle OpenAPI document](https://open-eu.nio.com/portal-api/spec/vehicles)
reports OpenAPI `3.0.1`, document version `v0`, and API server
`https://open-api-eu.nio.com`. NIO renders the same catalog under the
[Vehicles & Telemetry API reference](https://open-eu.nio.com/docs/vehicles).

## Hosts and authentication

| Purpose | URL |
|---|---|
| OAuth authorization | `https://open-eu.nio.com/oauth2/authorize` |
| OAuth token | `https://open-eu.nio.com/api/2/oauth/token` |
| Vehicle and aftersales APIs | `https://open-api-eu.nio.com/api/1/telematics` |

The integration uses Authorization Code with PKCE. It exchanges the code and
verifier as `application/x-www-form-urlencoded` with HTTP Basic client
authentication. The OAuth authorization reference lists `scope` as optional;
the integration omits it so NIO applies the scopes configured for the
application. Vehicle calls use a Bearer token. The token endpoint and API
hostnames are separate by design.

## Vehicle and aftersales operation catalog

The live vehicle specification lists 24 operations. The integration polls the
latest snapshot, 15 change feeds, and odometer reports every five minutes. The
response-only `nio_telematics.query` service exposes parameterized vehicle
status history and the seven non-polled ADAS, NOMI, and recall operations.

| Operation ID | Method and path | Integration access |
|---|---|---|
| `extractDlbSnapshot` | `POST /vehicles/{vin}/adas/snapshot/extract?uuid=…` | Service: `extract_adas_snapshot` |
| `downloadDlbEvent` | `POST /vehicles/{vin}/adas/event/download?uuid=…&asUrl=…` | Service: `download_adas_event` |
| `getWindowStatusChanges` | `GET /vehicles/{vin}/window_status/changes` | Polled |
| `getLatestVehicleStatus` | `GET /vehicles/{vin}/vehicle_status/latest` | Polled |
| `getVehicleStatusChanges` | `GET /vehicles/{vin}/vehicle_status/changes` | Polled; service supports time filters |
| `getTripStatusChanges` | `GET /vehicles/{vin}/trip_status/changes` | Polled |
| `getSOCStatusChanges` | `GET /vehicles/{vin}/soc_status/changes` | Polled |
| `getPositionStatusChanges` | `GET /vehicles/{vin}/position_status/changes` | Polled |
| `getASRFileList` | `GET /vehicles/{vin}/nomi/asr` | Service: `nomi_asr_files` |
| `getLightStatusChanges` | `GET /vehicles/{vin}/light_status/changes` | Polled |
| `getHVACStatusChanges` | `GET /vehicles/{vin}/hvac_status/changes` | Polled |
| `getHeatingStatusChanges` | `GET /vehicles/{vin}/heating_status/changes` | Polled |
| `getFridgeStatusChanges` | `GET /vehicles/{vin}/fridge_status/changes` | Polled |
| `getExtremumDataChanges` | `GET /vehicles/{vin}/extremum_data/changes` | Polled |
| `getDrivingMotorChanges` | `GET /vehicles/{vin}/driving_motor/changes` | Polled |
| `getDrivingDataChanges` | `GET /vehicles/{vin}/driving_data/changes` | Polled |
| `getDoorStatusChanges` | `GET /vehicles/{vin}/door_status/changes` | Polled |
| `getCellStatusChanges` | `GET /vehicles/{vin}/cell_status/changes` | Polled |
| `getAlarmSignalChanges` | `GET /vehicles/{vin}/alarm_signal/changes` | Polled |
| `getDlbSnapshot` | `GET /vehicles/{vin}/adas/snapshot` | Service: `adas_snapshots` |
| `getDlbEvent` | `GET /vehicles/{vin}/adas/event` | Service: `adas_events` |
| `getVehicleRecallHistory` | `GET /aftersales/vehicles/{vin}/recalls` | Service: `vehicle_recalls` |
| `getOdometerReports` | `GET /aftersales/vehicles/{vin}/odometer_reports` | Polled |
| `getRecallCampaigns` | `GET /aftersales/recall_campaigns/{campaign_no}` | Service: `recall_campaign` |

All paths above are relative to `/api/1/telematics`. Change-feed `start_time`
and `end_time` are optional Unix milliseconds in the live API tested on
2026-10-09. The portal's quick-start example uses seconds, but those requests
returned HTTP 400 `invalid_param`; otherwise identical millisecond requests
succeeded. SoC polling uses an overlapping ten-minute window, with a
five-minute fallback if the longer window is rejected. ADAS scan filters
are `startTs` and `endTs` (nanoseconds since
epoch), plus optional `limit` and `offset`. The NOMI listing uses `limit` and
`offset`. Extraction and download require the `uuid` query parameter; `asUrl`
is optional. Recall campaign details accept an optional `Accept-Language`
header.

## Response values and units

Successful telemetry responses use a JSON envelope with `request_id`,
`result_code`, `server_time`, optional message fields, and `data`. A successful
HTTP status alone is insufficient: business errors can be returned in
`result_code`. Change feeds return arrays; latest vehicle status and many
specialized operations return objects. Preserve nested records in bounded
diagnostic attributes or service responses instead of flattening them into
scalar sensors.

| Field | Contract conversion |
|---|---|
| `sample_timestamp` | Milliseconds since epoch; convert to a UTC timestamp. |
| `server_time` | Unix seconds. |
| `vehicle_status.speed` | Value × 0.1 km/h. |
| `vehicle_status.mileage` | Kilometres directly in the live JSON response. Confirmed against the car's odometer; do not apply the protocol-level × 0.1 conversion. |
| `vehicle_status.vehl_totl_volt` | Value × 0.1 V. |
| `vehicle_status.vehl_totl_curnt` | Value × 0.1 − 1000 A. |
| `soc_status.remaining_range` | Kilometres directly in the live JSON response, confirmed against the NIO app. `0xFFFFFFFE` and `0xFFFFFFFF` are invalid/malfunction sentinels. |
| `extremum_data.sin_btry_hist_volt`, `sin_btry_lwst_volt` | Volts directly in the live JSON response. Do not apply the protocol-level × 0.001 conversion again. |
| `soc_status.btry_paks[].btry_pak_voltage` | Volts directly in the live JSON response. The enabled pack-voltage sensor uses a single pack; multi-pack topology is not inferred. |
| `extremum_data.highest_temp`, `lowest_temp` | Value − 40 °C. |
| `odometer_reports[].value` | Kilometres directly; `recorded_at` is ISO 8601. |

Documented sentinel values for converted speed, mileage, voltage, current,
cell-voltage, battery-temperature, and range values are exposed as unknown
rather than converted into physical measurements.

## On-demand service

Call `nio_telematics.query` with a NIO config entry and one operation key from
the service selector. Supply only that operation's parameters. The service
returns the NIO envelope immediately without changing the coordinator's
periodic polling schedule.
`start_time` and `end_time` use milliseconds; `start_ts` and `end_ts` use
nanoseconds. API response URLs, VINs, vehicle UUIDs, access tokens, and precise
coordinates are redacted before returning service responses or writing entity
attributes/debug logs. Data UUIDs remain in service responses because NIO
requires them as inputs to ADAS extraction and download operations; API debug
logs still redact them. NIO's NOMI and ADAS response schemas can contain
pre-signed object URLs; treat them as credentials.

Diagnostic attributes are limited to 50 list items, nesting depth 8, and
12,000 encoded bytes. Oversized diagnostic payloads are represented as
truncated rather than persisted in Home Assistant state.

## Activity and energy-data priority

Fresh change records appeared immediately after charging began in the tested
ET7. Before that, several feeds returned HTTP 404 `resource_not_found`, while
latest status and position still returned older samples. An empty feed means
no new measurement, not an integration failure. HTTP 400/404 business errors
are interpreted from the envelope without overriding authentication,
rate-limit, or server errors.

The dedicated `soc_status/changes` feed provides authoritative SoC; the latest
vehicle snapshot continued returning zero even while the energy feed had
correct nonzero readings. Sparse energy records are merged by newest valid
field. The coordinator retains its last-known energy values during empty
polls, preserving the energy sample timestamp instead of replacing it with a
new vehicle snapshot timestamp. This cache lasts for the running coordinator;
after a Home Assistant restart, fresh energy data is needed again.

These live findings concern the tested application and vehicle. The schema's
protocol conversion descriptions are not reliable evidence of JSON units.
Other scalar conversions remain unchanged unless independently verified.

The portal's generated specification does not document every backend
entitlement or every possible `result_code`. Access and returned telemetry can
vary by application, scope grant, vehicle, and account. This summary is a
contract snapshot, not proof that every API is enabled for a particular NIO
application.
