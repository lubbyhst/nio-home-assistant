# Changelog

The changelog is the authoritative release history for this integration.
Use this before releases and when opening PRs.

## Unreleased

- Prepare and maintain this public changelog file for HACS users.

## 0.1.0-dev6

- Improve OAuth permission-handling so scope/permission changes surface as a clear
  reauthentication requirement instead of generic failures.
- Keep OAuth reauthorization integrated with Home Assistant’s native flow (including
  token refresh into the existing config entry via reauth).
- Add a changelog file and public link from README for release transparency.
- Bump integration version to `0.1.0-dev6`.

## 0.1.0-dev5

- Expand telemetry coverage to all documented read-only endpoint families.
- Add richer endpoint-status tracking and preserve last-seen optional feed values.
- Add first batch of non-critical optional diagnostic sensor entities.
- Improve token refresh robustness and wrapped OAuth token parsing.

## 0.1.0-dev4

- Refine SoC-window probing and retain previous snapshots when change endpoints are
  temporarily empty.
- Keep vehicle status as a required feed and merge energy fields when available.

## 0.1.0-dev3

- Introduce OAuth2 Authorization Code + PKCE and application-credential setup.
- Add initial sensor coverage for SoC/range/charging state and basic diagnostics.

## 0.1.0-dev2

- Initial API client and integration skeleton for official NIO Open Telematics endpoints.
