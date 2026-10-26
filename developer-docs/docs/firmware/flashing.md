# Firmware Flashing & Streams

This reference covers firmware release streams and manual USB flashing. For the end-user over-the-air (OTA) update explanation, see the [user Firmware Updates guide](https://docs.researchanddesire.com/dtt/technical/firmware-updates/).

## Firmware streams

The trainer may receive updates from different firmware streams:

| Stream | Description |
|--------|-------------|
| **Production** | Stable releases for general use |
| **Beta** | Preview releases with new features (may have bugs) |
| **Alpha** | Early testing builds (internal/limited use) |

!!! info
    Most users receive production updates automatically. Beta enrollment is typically managed through the dashboard account or subscription tier.

### Current beta status
Active subscribers are often enrolled in the beta stream during rollouts. A dashboard toggle to switch between Production, Beta, and Latest streams is planned.

See the [Software 2.0 Preview](https://docs.researchanddesire.com/dtt/software-2.0-preview/) for details on current beta features.

## Manual USB flashing

### Local development builds

Run PlatformIO from `software/`. The `development-v1` and `development-v2`
profiles disable automatic firmware updates and default to
`http://127.0.0.1:3000`. For a physical device, copy
`local.settings.example.json` to ignored `local.settings.json` and set `server`
to the computer's explicit private LAN origin, for example
`http://192.168.1.50:3000`. A trainer's loopback address refers to the trainer.
The build accepts loopback and private LAN IP addresses without resolving DNS;
it rejects credentials, public hosts, paths, query strings and fragments.
Staging and production do not read local development settings.

Use `pio run -e development-v2 -t buildprog` to compile without connecting to
or flashing a device. Select V1 or V2 only after verifying the enrolled board's
identity, physical flash and existing partition layout. Provision bench Wi-Fi
through the supported BLE commands and keep Wi-Fi credentials out of build
flags and source files.

If a Trainer can't receive OTA updates (due to connectivity issues or network restrictions), firmware can be manually flashed using a USB cable and the Web Flasher.

!!! info
    Use manual USB flashing when troubleshooting connectivity issues or when instructed by support. Most users won't need this—OTA updates handle everything automatically.

### Prerequisites

- A USB cable that supports **data transfer** (not just charging)
- A computer with an available USB port
- Google Chrome, Edge, or another Chromium-based browser

!!! warning
    **Hardware compatibility:** Trainers purchased before July 1st, 2025 do not have the required USB interface for manual flashing. If you see a message indicating a device isn't flashable, or if the webflasher cannot detect the device, contact [support@researchanddesire.com](mailto:support@researchanddesire.com) for assistance.

### Flashing instructions

#### Step 1: Connect the Trainer

Plug the USB cable into the Deepthroat Trainer and connect the other end to the computer.

#### Step 2: Open the Web Flasher

Navigate to [dashboard.researchanddesire.com/app/tools/web-flasher](https://dashboard.researchanddesire.com/app/tools/web-flasher) in the browser.

#### Step 3: Select firmware options

In the Web Flasher:

1. Select **Deepthroat Trainer** from the device dropdown
2. Select **Production** from the firmware stream dropdown

#### Step 4: Connect to the device

Click **Connect** and select the device from the list. Look for a device labeled:

- **UART Bridge**
- **USB JTAG** (or similar)

!!! warning
    If no device appears, verify the cable supports data transfer and try a different USB port.

#### Step 5: Flash the firmware

Click **Flash** to install the firmware. Wait for the process to complete.

!!! warning
    Do **not** enable "Erase device" unless specifically instructed by support. Erasing clears the Trainer ID and requires re-provisioning.

### After flashing

Once the flash completes, the Trainer restarts with the new firmware. Connect to Wi-Fi to verify connectivity.

If **E-DTT-1** ("No internet. Check firewall and router.") appears after connecting, this confirms a network restriction is blocking the device. Follow the [E-DTT-1 troubleshooting guide](https://docs.researchanddesire.com/dtt/errors/e-dtt-1/) to resolve the issue.

## Erase / re-provisioning behavior

!!! warning
    Enabling "Erase device" in the web flasher clears **all** stored data, including the unique Trainer ID assigned during manufacturing (provisioning data).

**Symptom:** After an erase, the Trainer ID displays corrupted characters (such as ".t", "U]t", or other random symbols) and changes on every reboot — the device's provisioning data was erased during flashing.

**Cause:** This happens when the web flasher is used with the "Erase device" option enabled. The erase option clears the unique Trainer ID.

**Resolution:** Support must re-provision the device with a new Trainer ID. Contact [support@researchanddesire.com](mailto:support@researchanddesire.com) with the order number, a description of what appears on screen, and the steps taken before the issue appeared.

!!! note
    Normal firmware updates do not require erasing the device. Only enable "Erase device" if specifically instructed by support.
