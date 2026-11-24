#include "HeaderBar.h"
#include "services/TaskStackSizes.h"
#include "services/hardwareHealth.h"

#include "WiFi.h"
#include "input.h"
#include "services/display.h"
#include "state/state.h"

static bool lastHealthCheckPassed = false;
static bool lastWifiStatus = false;
static uint8_t lastBatteryLevel = 0;
static bool lastCharging = false;
static int lastTimeoutLevel = 0;
static bool lastShowButton = false;

bool shouldDrawWifiIcon() {
    if (const bool currentWifiStatus = WiFi.status() != WL_CONNECTED;
        currentWifiStatus != lastWifiStatus ||
        healthCheckPassed != lastHealthCheckPassed) {
        return true;
    }
    return false;
}
// --- Simple Icon Drawing Functions ---
void drawWifiIcon(const int16_t x, const int16_t y) {
    display.setFont(wifiFont);
    if (WiFi.status() != WL_CONNECTED || !healthCheckPassed) {
        display.drawGlyph(x, y + 8, GLYPH_WIFI_OFF);
    } else {
        display.drawGlyph(x, y + 8, GLYPH_WIFI_2_BARS);
    }
}

int getBatteryLevel(const float voltage) {
    if (voltage > 3.9) return 3;
    if (voltage > 3.65) return 2;
    if (voltage > 3.4) return 1;
    return 0;
}

bool shouldDrawBatteryIcon(const bool charging, const int level) {
    return charging != lastCharging || level != lastBatteryLevel;
}

void drawBatteryIcon(const int16_t x, const int16_t y, const bool charging,
                     const float voltage) {
    display.setFont(wifiFont);
    if (charging)
        display.drawGlyph(x, y + 8, GLYPH_BATTERY_CHARGING);
    else if (voltage > 3.9)
        display.drawGlyph(x, y + 8, GLYPH_BATTERY_FULL);
    else if (voltage > 3.65)
        display.drawGlyph(x, y + 8, GLYPH_BATTERY_MID);
    else
        display.drawGlyph(x, y + 8, GLYPH_BATTERY_LOW);
}

int getTimeoutLevel() {
    if (timeout >= 5000) return 0;
    if (timeout >= 4000) return 1;
    if (timeout >= 3000) return 2;
    if (timeout >= 2000) return 3;
    if (timeout >= 1000) return 4;
    if (timeout >= 250) return 5;
    return 6;
}

bool shouldDrawTimeoutIcon() {
    const int level = getTimeoutLevel();
    return showButton != lastShowButton || level != lastTimeoutLevel;
}

void drawTimeoutIcon() {
    const int x = 128 - 8;
    const int y = 58;
    const int level = getTimeoutLevel();
    display.setFont(timeoutFont);
    if (level == 0)
        display.drawGlyph(x, y + 8, GLYPH_TIMEOUT_GHOST);
    else if (level == 1)
        display.drawGlyph(x, y + 8, GLYPH_TIMEOUT_0);
    else if (level == 2)
        display.drawGlyph(x, y + 8, GLYPH_TIMEOUT_25);
    else if (level == 3)
        display.drawGlyph(x, y + 8, GLYPH_TIMEOUT_50);
    else if (level == 4)
        display.drawGlyph(x, y + 8, GLYPH_TIMEOUT_75);
    else if (level == 5)
        display.drawGlyph(x, y + 8, GLYPH_TIMEOUT_100);
    else if (showButton)
        display.drawGlyph(x, y + 8, GLYPH_TIMEOUT_GHOST);
}

// --- Header Bar Task ---
void headerBarTask(void *pvParameters) {
    vTaskDelay(1000 / portTICK_PERIOD_MS);
    long lastLoopTime = millis();
    while (true) {
        // This loop runs page timeouts on every screen, so it is the UI
        // progress the health heartbeat reports.
        hardwareHealthMenuProgress();
        long now = millis();
        long elapsedLoop = now - lastLoopTime;
        lastLoopTime = now;

        if (timeout > 0) {
            timeout -= elapsedLoop;
            if (timeout <= 0) {
                timeout = 0;
                stateMachine->process_event(timeout_expired{});
            }
        }

        // Read power before taking the display: the readings can take over
        // 100 ms, and play frames wait on the display while we hold it.
        const bool charging = checkIfCharging();
        const float voltage = getBatteryVoltage();
        const int batteryLevel = getBatteryLevel(voltage);
        const bool shouldDrawWifi = shouldDrawWifiIcon();
        const bool shouldDrawBattery = shouldDrawBatteryIcon(charging, batteryLevel);
        const bool shouldDrawTimeout = shouldDrawTimeoutIcon();

        const bool shouldDraw = shouldDrawWifi || shouldDrawBattery ||
                                shouldDrawTimeout;
        if (!shouldDraw) {
            vTaskDelay(100 / portTICK_PERIOD_MS);
            continue;
        }

        ESP_LOGV("headerBar",
                 "Header drawing because of wifi: %d, bat: %d, time: %d",
                 shouldDrawWifi, shouldDrawBattery, shouldDrawTimeout);

        if (xSemaphoreTake(displayMutex, 100) == pdTRUE) {
            if (shouldDrawWifi || shouldDrawBattery) {
                clearIcons();
                drawWifiIcon(128 - 26, 0);
                drawBatteryIcon(128 - 12, 0, charging, voltage);
                refreshIcons();
                ESP_LOGD("headerBar",
                         "shouldDrawWifi: %d, shouldDrawBattery: %d",
                         shouldDrawWifi, shouldDrawBattery);
            }
            if (shouldDrawTimeout) {
                clearTimeout();
                drawTimeoutIcon();
                refreshTimeout();
            }
            xSemaphoreGive(displayMutex);
        }


        lastWifiStatus = WiFi.status() != WL_CONNECTED;
        lastHealthCheckPassed = healthCheckPassed;
        lastBatteryLevel = batteryLevel;
        lastCharging = charging;
        lastTimeoutLevel = getTimeoutLevel();
        lastShowButton = showButton;

        vTaskDelay(100 / portTICK_PERIOD_MS);
    }
}

void initHeaderBar() {
    xTaskCreatePinnedToCore(headerBarTask, drawBatteryTaskName,
                            taskStacks::header, nullptr,
                            tskIDLE_PRIORITY, &drawBatteryTaskHandle, 0);
}
