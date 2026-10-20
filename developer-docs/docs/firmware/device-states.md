# Device States and Screens

This reference documents the Deepthroat Trainer firmware state flow, screen timeouts, and button action matrix. For the end-user "what each screen means" explanation, see the [user Device States guide](https://docs.researchanddesire.com/dtt/technical/device-states/).

## State diagram overview

```
Power On → Welcome → Preflight → [Update if available]
                              → [Pairing if needed]
                              → Play Preflight → Fetch/Load Settings
                                              → Calibration (if needed)
                                              → Session Details
                                              → Countdown → Training
                                              → Grade → [Next Segment or Final]
```

## Screen timeouts

| State / Screen | Timeout | Behavior on timeout |
|----------------|---------|---------------------|
| **Welcome** | 15 s | Auto-advances to preflight |
| **Wi-Fi Setup portal** | 400 s | Device restarts if portal expires |
| **Session Details** | 10 s | Advances to next screen |
| **Toy Details** | 10 s | Advances to next screen |
| **Segment Details** | 10 s | Advances to next screen |
| **Grade** | 30 s | Advances to next segment / final |
| **Three Strikes** | 5 s | Session restarts |
| **Final Page** | 10 s | Returns to idle |

## Play flow screens

### Pre-session screens

| Screen | Description |
|--------|-------------|
| **Preflight** | "Getting ready..." — checks connectivity and settings |
| **Fetch Settings** | "I'm getting your settings from the dashboard." |
| **Load Settings** | "You're offline, your grades may not be saved." (offline mode) |
| **Bad Health Check** | Error E-DTT-1 — see the [E-DTT-1 user guide](https://docs.researchanddesire.com/dtt/errors/e-dtt-1/) |

### Calibration screens

| Screen | Description |
|--------|-------------|
| **Calibration Min** | Capture minimum (closest) position — press button when ready |
| **Calibration Max** | Capture maximum (rest) position — press button when ready |

!!! note
    Calibration captures 100 samples at each position for accuracy.

### Session detail screens

| Screen | Content | Timeout |
|--------|---------|---------|
| **Session Details** | Session name, total segments | 10 s |
| **Toy Details** | Assigned toy name and settings | 10 s |
| **Segment Details** | Current segment name and parameters | 10 s |

!!! tip
    In Hands-Free Mode (Ultra), these screens advance automatically. Otherwise, a button press continues.

### Training screens

| Screen | Description |
|--------|-------------|
| **Countdown** | "Starting in 3... 2... 1... Good Luck!" |
| **Active Training** | Real-time display showing position, target, and progress |
| **Grade** | Score and performance feedback (timeout: 30 s) |

### Pass/Fail screens (if enabled)

| Screen | Description | Timeout |
|--------|-------------|---------|
| **Failed** | Shows "Failed" with attempt count (e.g., "Attempt 1/3") | Press to retry |
| **Three Strikes** | "YOU FAIL - 3 failed attempts" — session restarts | 5 s |

### Session complete

| Screen | Description |
|--------|-------------|
| **Final Page** | "Well done! You finished the session." (timeout: 10 s) |

The LED turns magenta on the final page to celebrate completion.

## Error states

| Error | Screen Content |
|-------|----------------|
| **E-DTT-1** | "No internet. Check firewall and router." |
| **Segment Error** | "ERROR" header with reset option |

See the [Error Catalog](/dtt/firmware/error-catalog/) for engineering/internal error details.

## Button actions by state

| State | Short Press | Long Press |
|-------|-------------|------------|
| Welcome | Start preflight | Enter Wi-Fi setup |
| Session Details | Next screen | Skip to training |
| Segment Details | Start segment | Skip to training |
| Grade | Next segment | — |
| Failed | Retry segment | — |
| Final | Play again | — |

## Related references

- [Error Catalog](/dtt/firmware/error-catalog/) — internal/engineering error codes.
- [Button Controls (user guide)](https://docs.researchanddesire.com/dtt/technical/button-controls/) — end-user button interactions.
