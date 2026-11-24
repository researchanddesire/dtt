#include "wifi_service.h"

#include <ArduinoJson.h>
#include <WiFi.h>
#include <esp_system.h>

#include "pages/TextPages.h"
#include "state/state.h"
#include "hardwareHealth.h"
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
    wm.setConfigPortalTimeout(WIFI_MANAGER_PORTAL_TIMEOUT);
    wm.setAPClientCheck(false);
    wm.setWebPortalClientCheck(false);

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
    // A fresh password requires physical access to this setup session. Never
    // derive it from a MAC/serial number or persist it in logs or firmware.
    uint8_t entropy[8];
    esp_fill_random(entropy, sizeof(entropy));
    char password[17] = {};
    static constexpr char PASSWORD_ALPHABET[] = "0123456789ABCDEF";
    for (size_t index = 0; index < sizeof(entropy); ++index) {
        password[2 * index] = PASSWORD_ALPHABET[entropy[index] >> 4];
        password[2 * index + 1] = PASSWORD_ALPHABET[entropy[index] & 0xf];
    }
    // The QR code joins the protected network directly; the text beside it
    // is for typing the password by hand.
    TextPage setupPage = wifiSetupPage;
    setupPage.url = String("WIFI:T:WPA;S:Trainer Setup;P:") + password + ";;";
    setupPage.content = String("Password: ") + String(password).substring(0, 8) +
                        " " + String(password).substring(8);
    drawQRCodePage(setupPage);
    wm.startConfigPortal("Trainer Setup", password);
    memset(password, 0, sizeof(password));
    memset(entropy, 0, sizeof(entropy));
    const uint32_t startedAt = millis();
    wm.process();

    while (isInCorrectState() && wm.getConfigPortalActive() &&
           static_cast<uint32_t>(millis() - startedAt) <
               WIFI_MANAGER_PORTAL_TIMEOUT * 1000UL) {
        wm.process();
        vTaskDelay(pdMS_TO_TICKS(50));
    }

    // WiFiManager may already have torn down the portal after a successful
    // save. Calling stopConfigPortal() again dereferences its released server.
    if (wm.getConfigPortalActive()) {
        wm.stopConfigPortal();
    }
    wm.process();
    setupPage.url = "";
    setupPage.content = "";
    if (isInCorrectState()) {
        setupPage.title = "Setup closed";
        setupPage.content = "Power cycle to retry";
        drawTextPage(setupPage);
    }
    vTaskDelete(nullptr);
}

void healthCheckWifi() {
    // Default to false
    healthCheckPassed = false;

    // Check if WiFi is connected
    if (WiFi.status() != WL_CONNECTED) {
        ESP_LOGW("WIFI_HEALTH", "WiFi not connected, health check failed");
        hardwareHealthCloudResult(false);
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
        hardwareHealthCloudResult(false);
        return;
    }

    healthCheckPassed = true;
    hardwareHealthCloudResult(true);
}
