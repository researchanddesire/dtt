#include "services/serialIdentity.h"
/*
 * Deepthroat Trainer code
 * Copyright Alex Warner R+D Labs 2021
 *
 */
#include <Arduino.h>
#include "services/radHil.h"
#include "services/hardwareHealth.h"
#include <DttHardwareVariant.h>
#if defined(DTT_MIGRATION_LAB_AUTORUN)
#include <WiFi.h>
#include <esp_ota_ops.h>
#endif

// clang-format off
// these must be near the top.
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
// clang-format on

#include "components/HeaderBar.h"
#include "services/board.hpp"
#include "services/button.h"
#include "services/display.h"
#include "services/eeprom_service.h"
#include "services/leds.h"
#include "services/rad_ble.h"
#include "services/upload_queue.h"
#include "services/wifi_service.h"
#include "state/state.h"
#include "utils/update.hpp"

#ifndef FIRMWARE_BUILD_SHA
#define FIRMWARE_BUILD_SHA "unknown"
#endif

#ifndef PROVISION
#include "services/vibrator.h"
#endif

#ifdef CONFIG_APP_ROLLBACK_ENABLE
// Let setup finish its device-level health checks before accepting a new OTA
// image. The Arduino core otherwise marks it valid before setup runs.
extern "C" bool verifyRollbackLater() { return true; }
#endif

#ifndef PIO_UNIT_TESTING
void setup() {
    configureSerialIdentityUsb();
    Serial.begin(115200);
    startSerialIdentity();
    radHilStart();
    hardwareHealthBoot();

    delay(1000);

    initBoard();
    initEEPROM();
#ifndef PROVISION
    initFastLEDs();
#endif
    initDisplay();
    initHeaderBar();
#ifndef PROVISION
    initUploadQueue();
#endif
    initWifi();

    initButtonService();

#ifndef PROVISION
    initVibratorService();
#endif

    initStateMachine();
#if DTT_ENABLE_RAD_BLE
    radHilBleStarted(initRadBle());
#endif
    confirmRunningFirmware();
#if defined(DTT_MIGRATION_LAB_AUTORUN)
    xTaskCreatePinnedToCore(
        [](void *) {
            for (int attempt = 0;
                 attempt < 60 && WiFi.status() != WL_CONNECTED; ++attempt) {
                vTaskDelay(pdMS_TO_TICKS(1000));
            }
            const esp_partition_t *running =
                esp_ota_get_running_partition();
            Serial.printf(
                "DTT_LAB_BOOT build=%s app=0x%08lx wifi=%s ip=%s\n",
                FIRMWARE_BUILD_SHA,
                running == nullptr
                    ? 0UL
                    : static_cast<unsigned long>(running->address),
                WiFi.status() == WL_CONNECTED ? "connected" : "failed",
                WiFi.localIP().toString().c_str());
            if (WiFi.status() == WL_CONNECTED) {
                getHasUpdate();
                if (dashboardState.hasUpdate) {
                    Serial.println("DTT_LAB_INSTALLING_UPDATE");
                    if (!updateSoftware()) {
                        Serial.println("DTT_LAB_UPDATE_FAILED");
                    }
                } else {
                    Serial.println("DTT_LAB_NO_UPDATE");
                }
            }
            vTaskDelete(nullptr);
        },
        "migrationLab", 10 * configMINIMAL_STACK_SIZE, nullptr, 1, nullptr, 1);
#endif
}

void loop() {
    // delete the loop task. Everything is managed by the state machine now.
    vTaskDelete(nullptr);
}
#endif
