# Offline Cache (Internal)

This reference documents the firmware's offline session caching, storage limits, and sync-on-reconnect behavior. For the end-user "works offline" explanation, see the [user Offline Mode guide](https://docs.researchanddesire.com/dtt/technical/offline-mode/).

## Caching mechanism

When settings are fetched while online:

1. The session is downloaded from the dashboard.
2. A copy is saved to local storage (**SPIFFS**).
3. This cached copy is available for offline use.

The cached session is always the **last downloaded** session.

## Storage limits

### Single-session storage
The trainer stores **one** cached session at a time. Downloading a new session overwrites the previous cache (SPIFFS).

### Segment limits
Offline playback uses the same segment limits as online mode (up to 100 effective segments with Ultra).

### Results persistence
Results from offline training are calculated on-device but **not persisted**. They're shown during the session but may be lost if:

- The device loses power before reconnecting.
- A new session is downloaded before syncing (overwrites the cache).

!!! warning
    Offline sessions are not saved to the dashboard until reconnect. If the device loses power before syncing, that session's results may be lost.

## Sync on reconnect

When the device reconnects to Wi-Fi:

1. Power on the trainer.
2. The device syncs pending results automatically.
3. The dashboard reflects the synced session.

!!! info
    Currently, offline sessions sync on the next online session start. Background sync (storing multiple sessions for later upload) is planned for a future firmware release. See the [Software 2.0 Preview](https://docs.researchanddesire.com/dtt/software-2.0-preview/) for upcoming features.

## Related references

- [Device States](/dtt/firmware/device-states/) — the "Load Settings" offline screen.
- [Error Catalog](/dtt/firmware/error-catalog/) — "Error sending results" internal codes.
