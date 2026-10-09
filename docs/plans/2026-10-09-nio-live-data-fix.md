# NIO live data fix implementation plan

**Goal:** Use the currently working energy change feed and handle its empty/error responses correctly.

**Evidence:** Local Python calls with HA's current access token reproduce HTTP 200 latest status with zero SoC, HTTP 404/resource_not_found empty changes, HTTP 400/invalid_param for second time bounds, and HTTP 200 position changes with millisecond bounds. The deployed files match this checkout. Ten- and thirty-minute millisecond bounds are accepted; hour and larger bounds fail.

**Design:** Poll every five minutes with an overlapping ten-minute SoC window. Retain the other endpoints' working unbounded requests. Reuse the SoC-specific parser to merge sparse records and cached energy data. Prefer the energy feed's SoC to the unreliable latest snapshot, including legitimate zero values. Keep last-known energy fields when there are no new changes and expose endpoint status and sample age. Map HTTP 400 invalid_param and 404 resource_not_found to their typed errors without overriding authentication, rate-limit, or server errors.

**Validation tasks:**

1. Add failing API regressions for millisecond SoC windows, empty HTTP 404 handling, and HTTP 400 parameter errors.
2. Add failing coordinator regressions for energy priority, sparse change records, and retained energy values after an empty poll.
3. Run focused tests to verify the failures, implement the focused fix, and rerun focused and complete tests plus Ruff.
4. Update the endpoint/time-unit documentation with live evidence, retaining caller-supplied on-demand parameters unchanged.
5. Run the patched client locally against current HA credentials, report only statuses/shape/age, and document limitations if the awakened car still supplies no energy data.

No independent OAuth refresh or persistent credential extraction is needed. Home Assistant owns refresh-token rotation.

Follow-up: distinguish per-cell volts from the complete pack voltage. Expose
the energy feed's verified single-pack voltage as an enabled sensor and use
three decimal places for individual cells. Do not infer multi-pack wiring.
