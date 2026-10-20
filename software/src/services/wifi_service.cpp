#include "wifi_service.h"

#include <ArduinoJson.h>
#include <WiFi.h>

#include "state/state.h"
#include "upload_queue.h"
#include "wifiSettings.h"

// Initialize the global WiFiManager instance
WiFiManager wm;

// Initialize health check status
bool healthCheckPassed = false;

// Optional: Add initialization code for the service
void initWifi() {
#ifdef AUTOPLAY_FOR_VIDEO
    dashboardState.isPaired = true;
    dashboardState.hasUpdate = false;
    dashboardState.preflightPending = false;
    return;
#endif

#ifdef WIFI_SSID
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
#else
    WiFi.enableIpV6();
    WiFi.begin();
#endif

    wm.setClass("invert");
    wm.setConfigPortalBlocking(false);
    wm.setConfigPortalTimeout(400);

    wm.setSaveConfigCallback([]() {
        if (stateMachine != nullptr) {
            stateMachine->process_event(wifi_configured{});
        }
    });

    xTaskCreatePinnedToCore(
        [](void* pvParameters) {
            // if there's no wifi save, then exit.
            if (const bool isWifiSaved = wm.getWiFiIsSaved(); !isWifiSaved) {
                // assume it's paired.
                dashboardState.isPaired = true;
                // assume it's up to date.
                dashboardState.hasUpdate = false;
                // don't wait for preflight.
                dashboardState.preflightPending = false;
                vTaskDelete(nullptr);
                return;
            }

            // else, wait up to 10 seconds for wifi to connect.
            int numChecks = 0;
            while (numChecks < 10) {
                // is Wifi connected?
                if (WiFi.status() != WL_CONNECTED) {
                    numChecks++;
                    vTaskDelay(1000 / portTICK_PERIOD_MS);
                    continue;
                }
                break;
            }

            healthCheckWifi();
            vTaskDelay(1);
            getIsPaired();
            vTaskDelay(1);
#ifndef PROVISION
            getHasUpdate();
            vTaskDelay(1);
#endif

            dashboardState.preflightPending = false;

            // Boot/reconnect recovery: heap is at its highest right after boot,
            // so results that were queued to flash before a reboot (or while
            // offline) upload successfully here. This is the primary recovery
            // path for the memory-exhaustion failure mode.
            if (WiFi.status() == WL_CONNECTED && healthCheckPassed) {
                const int recovered = flushUploadQueue();
                if (recovered > 0) {
                    ESP_LOGI("UPQ", "recovered %d queued segment(s) on boot",
                             recovered);
                }
            }

            if (stateMachine != nullptr) {
                stateMachine->process_event(preflight_done{});
            } else {
                ESP_LOGW("WIFI_HEALTH",
                         "Preflight completed before state machine startup");
            }

            vTaskDelete(nullptr);
        },
        preflightChecksTaskName, 10 * configMINIMAL_STACK_SIZE, nullptr, 1,
        &preflightChecksTaskHandle, 1);
}

void processWifiTask(void* pvParameters) {
    auto isInCorrectState = []() {
#ifdef PROVISION
        return stateMachine->is("provisioning.wifiSettings"_s);
#else
        return stateMachine->is("wifiSettings"_s) ||
               stateMachine->is("provisioning.wifiSettings"_s);
#endif
    };
    wm.startConfigPortal("Trainer Setup");
    wm.process();

    while (isInCorrectState()) {
        wm.process();
        vTaskDelay(pdMS_TO_TICKS(50));
    }

    // WiFiManager may already have torn down the portal after a successful
    // save. Calling stopConfigPortal() again dereferences its released server.
    if (wm.getConfigPortalActive()) {
        wm.stopConfigPortal();
    }
    wm.process();
    vTaskDelete(nullptr);
}

void healthCheckWifi() {
    // Default to false
    healthCheckPassed = false;

    // Check if WiFi is connected
    if (WiFi.status() != WL_CONNECTED) {
        ESP_LOGW("WIFI_HEALTH", "WiFi not connected, health check failed");
        return;
    }

    // Prepare the request payload with MAC address and trainerId
    JsonDocument requestDoc;
    requestDoc["macAddress"] = WiFi.macAddress();

    // Store response payload
    String responsePayload;

    // Make POST request to /health-check endpoint
    int httpResponseCode =
        postJson("/health-check", requestDoc, &responsePayload);

#if defined(RAD_HIL_VARIANT)
    // Credential-free diagnostic for the application's own preflight failure.
    Serial.printf("\nRAD_DIAG health_http=%d heap=%u max_alloc=%u\n",
                  httpResponseCode, ESP.getFreeHeap(), ESP.getMaxAllocHeap());
#endif

    // Check if response code is 200
    if (httpResponseCode != 200) {
        ESP_LOGW("WIFI_HEALTH", "Health check failed with HTTP code: %d",
                 httpResponseCode);
        return;
    }

    healthCheckPassed = true;
}
