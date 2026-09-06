# NIO Open Telematics for Home Assistant

Early development foundation for a read-only Home Assistant integration using
NIO's official EU Open Telematics API.

## Project status and disclosure

This is an independent, unofficial personal project created to meet the
author's own Home Assistant needs and shared in case it is useful to others.
Its design, code, tests, and documentation have been produced with substantial
assistance from AI and reviewed through automated validation and hands-on
testing. It does not claim to be an official NIO product, a professionally
supported integration, or affiliated with NIO, Home Assistant, or OpenAI.

It is experimental software. Review it, protect your credentials and vehicle
data, and use it at your own risk.

Current development milestone (`0.1.0-dev7`):

- polls every documented read-only telemetry category that can provide useful
  Home Assistant state: body, dynamics, location, trip, energy, cabin,
  powertrain, diagnostics, and aftersales odometer data;
- creates 64 stable scalar sensors and 16 disabled diagnostic endpoint sensors;
- preserves variable-length/nested data such as battery cells, motor lists,
  window faults, door structures, and alarm signals as attributes on the
  corresponding disabled diagnostic sensor;
- uses one coordinator and one Home Assistant device per VIN;
- redacts credentials and vehicle identifiers from diagnostics;
- handles authentication, permission, rate-limit, envelope, and transport
  errors separately, and keeps unavailable optional feeds from breaking feeds
  that do work.

Most detailed entities are disabled by default to avoid flooding a new Home
Assistant installation. Enable the ones you need on the NIO device page. The
existing battery/range/charging entities keep their original IDs; odometer is
the only newly enabled-by-default entity.

## Live API status

The table below is based on hands-on testing against one EU NIO ET5 Touring,
not on what the API merely promises. Other vehicle models or accounts may
behave differently.

| Data | Implemented | Observed result |
|---|---:|---|
| OAuth authorization, refresh and user info | Yes | Working |
| Latest vehicle timestamp/state/mileage | Yes | Working; timestamp and mileage advanced after driving |
| Battery SoC in latest vehicle status | Yes | Returned `0` instead of the vehicle's real SoC |
| Charging state, battery current/voltage | Yes | Missing, null, or zero in the latest-status response |
| SoC/range/charging-target change feed | Yes | `resource_not_found`, including after driving and an observed 2% discharge |
| Body, lights, windows, driving, position, trips, cell/extremum, cabin, motor, alarms | Yes in dev5 | Depends on granted scopes; unavailable scopes are now marked as `permission_denied` |
| Aftersales odometer reports | Yes in dev5 | Depends on granted scopes; unavailable without `aftersales:read` |

The VIN was independently verified because vehicle state and mileage were
correct. If a granted scope is missing, the integration keeps setup active and
flags the affected feed as `permission_denied`, so you can continue with available
data while granting any missing permissions. A detailed case has been sent to
NIO and feedback is still pending. If you have faster access to NIO's Open
Telematics API support or can test another eligible EU vehicle, please open a
GitHub issue and help move the investigation forward. Never post credentials,
tokens, a full VIN, or precise location data.

The config flow now uses locally supplied NIO application credentials, OAuth
Authorization Code + PKCE, NIO's HTTP Basic token exchange, wrapped token
response, and automatic refresh through Home Assistant's OAuth session. The
official reference exposes vehicle telemetry by VIN and does not document a
vehicle-list endpoint, so setup validates a manually entered VIN after consent.
If API scopes or permissions are changed, Home Assistant will now request a
clean reauthorization flow automatically.
Automated tests, hassfest, and HACS repository validation run on every push.

Never commit a Client ID, Client Secret, VIN, access token, refresh token, or
diagnostic payload containing personal vehicle data.

## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for public release notes and version history.
