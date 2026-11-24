#include "hardwareHealth.h"

#include <Arduino.h>
#include <DttHardwareVariant.h>
#include <WiFi.h>
#include <atomic>
#include <esp_ota_ops.h>
#include <esp_partition.h>
#include <esp_random.h>
#include <esp_system.h>
#include <esp_timer.h>

#include "hardwareHealthFormat.h"

#ifndef FIRMWARE_BUILD_SHA
#define FIRMWARE_BUILD_SHA "unknown"
#endif
#ifndef FIRMWARE_TRACK
#define FIRMWARE_TRACK "development"
#endif

namespace {
uint32_t bootId = 0;
std::atomic<uint32_t> menuProgressMs{0};
std::atomic<bool> cloudOk{false};
uint32_t lastHeartbeatMs = 0;

uint64_t uptimeMs() { return static_cast<uint64_t>(esp_timer_get_time() / 1000); }

// Release builds compile logging out, so records go straight to the UART0
// console the serial identity uses. One write per record, so other writers
// cannot split it.
void emit(const char* record, size_t size) {
    if (size != 0) Serial.write(reinterpret_cast<const uint8_t*>(record), size);
}
}  // namespace

void hardwareHealthBoot() {
    bootId = esp_random();
    char deviceId[13];
    hardwareHealth::formatDeviceId(ESP.getEfuseMac(), deviceId);
    // The running image's SHA-256, computed exactly as the Lockbox does.
    uint8_t digest[32] = {};
    const esp_partition_t* running = esp_ota_get_running_partition();
    const bool hashed =
        running != nullptr && esp_partition_get_sha256(running, digest) == ESP_OK;
    char imageSha256[65];
    hardwareHealth::formatSha256(hashed ? digest : nullptr, imageSha256);
    char record[hardwareHealth::RECORD_CAPACITY];
    emit(record, hardwareHealth::formatBoot(
                     record, sizeof(record),
                     {bootId, uptimeMs(), FIRMWARE_BUILD_SHA, FIRMWARE_TRACK,
                      dtt::HARDWARE_VARIANT, deviceId, imageSha256,
                      static_cast<int>(esp_reset_reason())}));
    // Every got-IP, including reconnects. Register before Wi-Fi starts.
    WiFi.onEvent(
        [](WiFiEvent_t, WiFiEventInfo_t info) {
            char record[160];
            emit(record, hardwareHealth::formatWifiConnected(
                             record, sizeof(record), bootId, uptimeMs(),
                             info.got_ip.ip_info.ip.addr));
        },
        ARDUINO_EVENT_WIFI_STA_GOT_IP);
}

void hardwareHealthCloudResult(bool succeeded) {
    // Once per boot, and again after any failed check.
    if (cloudOk.exchange(succeeded) || !succeeded) return;
    char record[128];
    emit(record, hardwareHealth::formatCloudOk(record, sizeof(record), bootId,
                                               uptimeMs()));
}

void hardwareHealthMenuProgress() {
    menuProgressMs.store(millis(), std::memory_order_relaxed);
}

void hardwareHealthHeartbeat(bool atMainMenu) {
    if (!hardwareHealth::heartbeatDue(millis(), lastHeartbeatMs)) return;
    // Read progress before the clock: the UI loop on the other core can
    // advance it meanwhile, and the age must not wrap.
    const uint32_t menuMs = menuProgressMs.load(std::memory_order_relaxed);
    const uint32_t sampled = millis();
    char record[192];
    emit(record, hardwareHealth::formatHeartbeat(
                     record, sizeof(record),
                     {bootId, uptimeMs(), atMainMenu && menuMs != 0,
                      sampled - menuMs}));
}
