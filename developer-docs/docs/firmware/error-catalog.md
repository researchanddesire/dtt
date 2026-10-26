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

The snapshot contains only fixed categories, counters and memory telemetry:

| Fields | Meaning |
| --- | --- |
| `generation`, `attempt` | Fetch generation since boot and request attempt (up to three). |
| `httpStatus`, `clientStatus` | Server HTTP status (zero if none) and the effective transport result. A server `200` can accompany a negative client result if reading the body failed. |
| `responseBytes`, `retainedBodyBytes` | Body bytes accepted by the bounded sink before a failure discards the payload, and bytes retained for parsing. |
| `parseCode`, `overflow` | ArduinoJson result: `255` not run, `0` success, `1` empty input, `2` incomplete input, `3` invalid input, `4` no memory, `5` too deep; document allocation overflow flag. |
| `stage`, `error` | Last fetch phase and fixed error category. Request-page and live-page mismatches are distinct. |
| `persistenceError` | `none`, `limit`, `mount`, `write`, `rotate`, `recover`, `stage` or `commit`. |
| `callbackInvoked`, `eventAccepted`, `persisted`, `installed` | Whether the state machine accepted the load callback, storage was committed and live settings were installed. |
| `cacheSource`, `cacheMounted` | Subsequent fallback outcome: `not_loaded`, `primary`, `backup` or `recovery`, and mount result. Fallback preserves the fetch's original failure category. |
| `startedAtMs`, `updatedAtMs`, `freeHeap`, `largestBlock` | Uptime and heap observations at the last diagnostic update. |

A completed fetch reports `stage=installed`, `parseCode=0`, `persisted=true`
and `installed=true`. `cacheMounted` describes a fallback cache load only;
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
