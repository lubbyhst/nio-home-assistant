# NIO EU Open Telematics API

This is the integration coverage reference for the read-only telemetry surface
used by this repository. The authoritative API documentation is published by
[NIO Open Platform](https://open-eu.nio.com/docs/vehicles).

## Supported endpoint inventory

All endpoints use the EU data host `https://open-api-eu.nio.com`, the path
prefix `/api/1/telematics`, and a Bearer token obtained through the existing
Home Assistant OAuth flow.

| Method | Path | Integration treatment |
| --- | --- | --- |
| GET | `/vehicles/{vin}/door_status/changes` | Polled change feed |
| GET | `/vehicles/{vin}/fridge_status/changes` | Polled change feed |
| GET | `/vehicles/{vin}/light_status/changes` | Polled change feed |
| GET | `/vehicles/{vin}/window_status/changes` | Polled change feed |
| GET | `/vehicles/{vin}/driving_data/changes` | Polled change feed |
| GET | `/vehicles/{vin}/vehicle_status/changes` | Polled change feed |
| GET | `/vehicles/{vin}/vehicle_status/latest` | Required core snapshot |
| GET | `/vehicles/{vin}/position_status/changes` | Polled change feed |
| GET | `/vehicles/{vin}/trip_status/changes` | Polled change feed |
| GET | `/vehicles/{vin}/cell_status/changes` | Polled change feed |
| GET | `/vehicles/{vin}/extremum_data/changes` | Polled change feed |
| GET | `/vehicles/{vin}/soc_status/changes` | Polled change feed |
| GET | `/vehicles/{vin}/heating_status/changes` | Polled change feed |
| GET | `/vehicles/{vin}/hvac_status/changes` | Polled change feed |
| GET | `/vehicles/{vin}/driving_motor/changes` | Polled change feed |
| GET | `/vehicles/{vin}/alarm_signal/changes` | Polled change feed |
| GET | `/aftersales/vehicles/{vin}/odometer_reports` | Polled aftersales feed |

The coordinator treats the latest vehicle snapshot as required. Other feeds
are optional: permission denial, empty data, rate limits, and endpoint errors
are recorded individually so useful telemetry remains available.

## Intentionally excluded endpoints

These public endpoints are not part of this integration's supported surface:

- `/vehicles/{vin}/adas/event`
- `/vehicles/{vin}/adas/event/download`
- `/vehicles/{vin}/adas/snapshot`
- `/vehicles/{vin}/adas/snapshot/extract`
- `/vehicles/{vin}/nomi/asr`
- `/aftersales/vehicles/{vin}/recalls`
- `/aftersales/recall_campaigns/{campaign_no}`

No client methods, polling, entities, services, or diagnostic promises should
be added for excluded endpoints unless the product scope is explicitly changed.

## Data and privacy rules

- Inspect both HTTP status and the NIO `result_code` response envelope.
- Preserve nested telemetry in disabled diagnostic entities, but cap list and
  payload sizes before exposing it as Home Assistant state attributes.
- Redact VINs, coordinates, credentials, sensitive headers, and pre-signed URL
  values from logs, entity attributes, and diagnostics.
- Keep the OAuth request's provider-default scope behavior; do not send an
  explicit combined scope list.
