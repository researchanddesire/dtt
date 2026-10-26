# Error Catalog (Internal)

This reference documents internal, engineering, and validation error codes emitted by the firmware. For user-facing error explanations and recovery steps, see the [user Error Codes guide](https://docs.researchanddesire.com/dtt/technical/error-codes/).

## Internal status codes

### "69 0" (and similar numeric codes)

Internal status codes surfaced when the device attempts to upload calibration or session data but can't reach the server. Codes like **"69 0"** are internal status codes — when offline, they don't prevent training; they simply indicate that data couldn't be uploaded at that moment.

## Settings-fetch diagnostics over BLE

Ordinary BLE-enabled firmware exposes the read-only `connectivity.settings`
resource through `sensor.read` or `setting.read`. It reports the most recent
dashboard settings fetch without enabling verbose logs. Reading it does not
retry the request, change the session or write storage.

Schema 2 returns a compact `summary` by default. Set `args.view` to `transport`,
`parse`, `storage` or `memory` for the corresponding details. Each fixed view
fits the complete 509-byte RadBLE reply, including request ID and both state
names. Compare `generation` across reads to ensure they describe the same fetch.
There is no combined `all` view.

The snapshot contains only fixed categories, counters and memory telemetry:

| View | Fields and meaning |
| --- | --- |
| All views | `v=2`, `view`, `generation` since boot and last fetch `stage`. |
| `summary` | `error`, `httpStatus`, `clientStatus`, `parseCode`, `persistenceError`, `cacheSource`. |
| `transport` | `attempt` (up to three), `httpStatus` (zero if none), `clientStatus`, `responseBytes`, `retainedBodyBytes`. A server `200` can accompany a negative client result if body reading failed. Byte counts distinguish the bounded sink's accepted bytes from the body retained for parsing. |
| `parse` | `error`, `parseCode`, `overflow`, `callbackInvoked`, `eventAccepted`. Parse codes: `255` not run, `0` success, `1` empty input, `2` incomplete input, `3` invalid input, `4` no memory, `5` too deep. |
| `storage` | `persistenceError`, `cacheSource`, `cacheMounted`, `callbackInvoked`, `eventAccepted`, `persisted`, `installed`. Persistence errors: `none`, `limit`, `mount`, `write`, `rotate`, `recover`, `stage`, `commit`. Cache source: `not_loaded`, `primary`, `backup`, `recovery`. Fallback preserves the original fetch failure. |
| `memory` | `startedAtMs`, `updatedAtMs`, `freeHeap`, `largestBlock` at the last diagnostic update. |

A completed fetch summary reports `stage=installed` and `parseCode=0`; its
storage view reports `persisted=true` and `installed=true`.
`cacheMounted` describes a fallback cache load only;
it remains false when no fallback was attempted, including successful fetches.
Diagnostics reset for a new fetch and after reboot.
Snapshots contain no request/response text, identifiers, network addresses or
credentials. Existing validation, transport, cache and formatting policies
remain in effect.

## Segment validation errors

### "Invalid Range"

**Cause:** The segment parameters resolve to an invalid training range.

**Notes:**
- Typically indicates a configuration issue in the template.
- Verify start and end positions are valid and within the sensor's clamped range.

### "Small window"

**Cause:** The target window is too small for reliable tracking.

**Notes:**
- The minimum effective window depends on sensor resolution.
- Increase the target window size in the template.

## System errors

### "Segment is nullptr" / "ERROR"

**Cause:** Internal error — the firmware couldn't load segment data (null segment pointer).

**Recovery:**
1. Press the button to reset.
2. Power cycle the device.
3. Verify the template has valid segments.
4. Re-download settings from the dashboard.

!!! warning
    If this error persists, capture the Trainer ID and reproduction steps for support.

## Provisioning errors

These only appear during initial device setup (factory/repair):

### "Failed to get trainer ID"

**Cause:** Provisioning server communication failed.

**Notes:**
- Requires a working internet connection to the provisioning server.
- Re-provisioning is also required after a flash with "Erase device" enabled — see [Firmware Flashing](/dtt/firmware/flashing/).

## Related references

- [Firmware Flashing](/dtt/firmware/flashing/) — erase/re-provisioning behavior.
- [Device States](/dtt/firmware/device-states/) — error state screens.
