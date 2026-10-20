# Architecture

DTT is an ESP32-based training device: WiFi connectivity, vibration feedback, RGB LED indicators, and an OLED display. Users configure sessions via the RAD dashboard; the device runs patterns locally with real-time feedback and syncs session data back for analytics.

## State machine

Core logic is a custom Boost::SML-inspired state machine in `src/state/machine.h`. Supporting pieces live alongside it:

- `state/state.h/cpp` — state data structures and transitions
- `state/events.hpp` — event definitions (e.g. `ButtonPressed`, `SessionComplete`)
- `state/guards.hpp` — transition guard conditions
- `state/actions.hpp` — transition action handlers
- `state/utils.h/cpp` — state utility functions

Flow: `Event → Guard check → Action execution → New state`.

## Services

Hardware abstraction lives under `src/services/`:

| Service | Role |
|------|------|
| `display` | OLED UI rendering (U8g2, SSD1306/SH1106) |
| `leds` | FastLED RGB control |
| `vibrator` | Vibration motor PWM control |
| `button` | OneButton debounced input |
| `wifi_service` | WiFi management |
| `eeprom_service` | Settings persistence to EEPROM |
| `charging_service` | Battery/charging detection |
| `handles` | HTTP API request handlers |

Pin definitions are in `services/board.hpp`.

## Communication

The device talks to the rad-app backend over HTTP (JSON). Key endpoints under `{RAD_SERVER}/api/dtt/`:

- `POST .../v2/training-started` — notify session start (fire-and-forget)
- `POST .../log-session` — upload completed session data
- `GET .../get-settings` — fetch user training settings
- `POST .../register` — initial device registration
- `POST .../v2/calibrate-toy` — calibration upload
- `GET .../ota` — firmware update check

Requests are keyed by `bubbleId` (device UUID). Each environment sets `RAD_SERVER` in `software/platformio.ini`.

## WiFi provisioning

First boot (or after a WiFi reset) starts a `DTT-SETUP` access point with a captive portal at `192.168.4.1`. Credentials are saved to EEPROM and persist across firmware flashes (hold the button during boot to reset them).

## OTA updates

The device compares its local `SW_VERSION` against the server and won't downgrade unless `FORCE_UPDATE` is set (`SW_VERSION=0` always triggers an update, for testing). OTA images are verified with `RAD_PUBLIC_KEY` (Ed25519).

## Training patterns

Pattern definitions live in the `lib/TrainingTypes/` library (ramp, interval, endurance, bounce, freeform), shared across RAD devices.
