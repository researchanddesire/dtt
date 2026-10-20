#include "utils/update.hpp"

#include <Arduino.h>
#include <WiFi.h>
#include <esp_flash.h>
#include <esp_ota_ops.h>
#include <esp_partition.h>
#include <mbedtls/sha256.h>

#include <algorithm>
#include <cstdint>
#include <string>

#include "FirmwareUpdateRuntime.h"
#include "FirmwareUpdateFlow.h"
#include "constants/Version.h"
#include "services/eeprom_service.h"
#include "services/upload_queue.h"
#include "wifiSettings.h"

#define UPDATE_TAG "UPDATE"

#ifndef FIRMWARE_TRACK
#define FIRMWARE_TRACK "main"
#endif

#ifndef FIRMWARE_BUILD_SHA
#define FIRMWARE_BUILD_SHA "unknown"
#endif

namespace {

constexpr std::uint32_t BOOTLOADER_OFFSET = 0x1000;
constexpr std::uint32_t PARTITION_TABLE_OFFSET = 0x8000;
constexpr std::uint32_t PARTITION_TABLE_SECTOR_SIZE = 0x1000;

firmware::Decision pendingFirmwareDecision;
bool pendingFirmwareDecisionValid = false;

String currentPartitionLayout() {
    const esp_partition_t *app0 = esp_partition_find_first(
        ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_OTA_0, nullptr);
    const esp_partition_t *app1 = esp_partition_find_first(
        ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_OTA_1, nullptr);
    if (app0 == nullptr || app1 == nullptr) return "unknown";
    if (app0->address == 0x10000 && app0->size == 0x780000 &&
        app1->address == 0x790000 && app1->size == 0x780000) {
        return "dtt-ota-16mb-v1";
    }
    if ((app0->address == 0x10000 && app0->size == 0x140000 &&
         app1->address == 0x150000 && app1->size == 0x140000) ||
        (app0->address == 0x10000 && app0->size == 0x1A0000 &&
         app1->address == 0x1B0000 && app1->size == 0x1A0000)) {
        return "legacy-v1";
    }
    return "unknown";
}

std::string digestString(const std::uint8_t digest[32]) {
    static constexpr char HEX_DIGITS[] = "0123456789abcdef";
    std::string output(64, '0');
    for (std::size_t index = 0; index < 32; ++index) {
        output[index * 2] = HEX_DIGITS[(digest[index] >> 4) & 0x0f];
        output[index * 2 + 1] = HEX_DIGITS[digest[index] & 0x0f];
    }
    return output;
}

std::string runningFirmwareHash() {
    const esp_partition_t *running = esp_ota_get_running_partition();
    std::uint8_t digest[32] = {};
    if (running == nullptr ||
        esp_partition_get_sha256(running, digest) != ESP_OK) {
        return {};
    }
    return digestString(digest);
}

std::string rawFlashHash(const std::uint32_t address,
                         const std::uint32_t size) {
    mbedtls_sha256_context sha;
    mbedtls_sha256_init(&sha);
    if (mbedtls_sha256_starts_ret(&sha, 0) != 0) {
        mbedtls_sha256_free(&sha);
        return {};
    }
    std::uint8_t buffer[1024];
    for (std::uint32_t offset = 0; offset < size; offset += sizeof(buffer)) {
        const std::uint32_t count =
            std::min<std::uint32_t>(sizeof(buffer), size - offset);
        if (esp_flash_read(nullptr, buffer, address + offset, count) != ESP_OK ||
            mbedtls_sha256_update_ret(&sha, buffer, count) != 0) {
            mbedtls_sha256_free(&sha);
            return {};
        }
    }
    std::uint8_t digest[32] = {};
    const bool finalized = mbedtls_sha256_finish_ret(&sha, digest) == 0;
    mbedtls_sha256_free(&sha);
    return finalized ? digestString(digest) : std::string{};
}

firmware::DeviceReport currentFirmwareReport() {
    std::uint32_t physicalFlashSize = 0;
    if (esp_flash_get_physical_size(nullptr, &physicalFlashSize) != ESP_OK) {
        physicalFlashSize = ESP.getFlashChipSize();
    }
    firmware::DeviceReport report;
    report.deviceType = "dtt";
    report.deviceId = trainerId.c_str();
    report.reportedTrack = FIRMWARE_TRACK;
#ifdef PROVISION
    // Provisioning is a bootstrap image, never an acceptable terminal client
    // image. Report a baseline version and omit client build/hash identity so
    // the resolver installs the latest assigned production release even when
    // this image was compiled from the same source version.
    report.currentVersion = "0.0.0";
#else
    report.currentVersion = VERSION;
    report.currentBuild = FIRMWARE_BUILD_SHA;
    report.firmwareHash = runningFirmwareHash();
#endif
    report.chip = ESP.getChipModel();
    report.chipRevision = ESP.getChipRevision();
    report.chipCores = ESP.getChipCores();
    report.flashSizeBytes = physicalFlashSize;
    const esp_partition_t *nextUpdatePartition =
        esp_ota_get_next_update_partition(nullptr);
    report.otaSlotSizeBytes =
        nextUpdatePartition == nullptr ? 0 : nextUpdatePartition->size;
    report.psramSizeBytes = ESP.getPsramSize();
    report.partitionLayout = currentPartitionLayout().c_str();
    report.partitionTableHash =
        rawFlashHash(PARTITION_TABLE_OFFSET, PARTITION_TABLE_SECTOR_SIZE);
    report.bootloaderHash = rawFlashHash(
        BOOTLOADER_OFFSET, PARTITION_TABLE_OFFSET - BOOTLOADER_OFFSET);
    firmware::provenance::reconcile(report);
    return report;
}

bool checkDatabaseForUpdate() {
    pendingFirmwareDecisionValid = false;
    dashboardState.hasUpdate = false;
    if (WiFi.status() != WL_CONNECTED || trainerId.isEmpty()) {
        ESP_LOGW(UPDATE_TAG, "Cannot check firmware without WiFi and trainer ID");
        return false;
    }

    String error;
    const firmware::DeviceReport report = currentFirmwareReport();
    if (!firmware::postCheck(RAD_SERVER, report, pendingFirmwareDecision,
                             error)) {
        ESP_LOGW(UPDATE_TAG, "Firmware check failed: %s", error.c_str());
        return false;
    }
    firmware::provenance::observeCurrent(report, pendingFirmwareDecision);
    firmware::provenance::stageUpdate(report, pendingFirmwareDecision);
    ESP_LOGI(UPDATE_TAG,
             "Firmware tracks reported=%s assigned=%s update=%s reason=%s target=%s hop=%s",
             pendingFirmwareDecision.reportedTrack.c_str(),
             pendingFirmwareDecision.assignedTrack.c_str(),
             pendingFirmwareDecision.shouldUpdate ? "true" : "false",
             pendingFirmwareDecision.reason.c_str(),
             pendingFirmwareDecision.targetVersion.c_str(),
             pendingFirmwareDecision.nextHopVersion.c_str());
    pendingFirmwareDecisionValid = true;
    dashboardState.hasUpdate = pendingFirmwareDecision.shouldUpdate;
    // This return value reports whether the check succeeded. The update
    // decision itself is carried by dashboardState.hasUpdate; already-current
    // is a successful check, not an error.
    return true;
}

}  // namespace

bool confirmRunningFirmware() {
    const esp_partition_t *running = esp_ota_get_running_partition();
    if (running == nullptr) return false;

    esp_ota_img_states_t state = ESP_OTA_IMG_UNDEFINED;
    const esp_err_t stateResult = esp_ota_get_state_partition(running, &state);
    if (stateResult == ESP_ERR_NOT_SUPPORTED ||
        (stateResult == ESP_OK && state != ESP_OTA_IMG_PENDING_VERIFY)) {
        return true;
    }
    if (stateResult != ESP_OK) {
        ESP_LOGW(UPDATE_TAG, "Unable to read running OTA state: %s",
                 esp_err_to_name(stateResult));
        return false;
    }

    const esp_err_t confirmResult = esp_ota_mark_app_valid_cancel_rollback();
    if (confirmResult != ESP_OK) {
        ESP_LOGE(UPDATE_TAG, "Unable to confirm running firmware: %s",
                 esp_err_to_name(confirmResult));
        return false;
    }
    ESP_LOGI(UPDATE_TAG, "Confirmed running OTA image");
    return true;
}

void getHasUpdate() {
#ifdef NO_UPDATE
    pendingFirmwareDecisionValid = false;
    dashboardState.hasUpdate = false;
#else
    checkDatabaseForUpdate();
#endif
}

void invalidateFirmwareUpdateDecision() {
    pendingFirmwareDecisionValid = false;
    dashboardState.hasUpdate = false;
}

bool updateSoftware() {
#ifdef PROVISION
    constexpr bool INSTALL_REQUIRED = true;
#else
    constexpr bool INSTALL_REQUIRED = false;
#endif
    auto action = firmware::selectUpdateAction(
        pendingFirmwareDecisionValid, pendingFirmwareDecision.shouldUpdate,
        INSTALL_REQUIRED);
    if (action == firmware::UpdateAction::resolve) {
        if (!checkDatabaseForUpdate()) return false;
        action = firmware::selectUpdateAction(
            pendingFirmwareDecisionValid, pendingFirmwareDecision.shouldUpdate,
            INSTALL_REQUIRED);
    }

    if (action == firmware::UpdateAction::reject) {
        ESP_LOGE(UPDATE_TAG,
                 "Provisioning requires a client install, but resolver returned no update");
        invalidateFirmwareUpdateDecision();
        return false;
    }

    if (action == firmware::UpdateAction::complete) {
        ESP_LOGI(UPDATE_TAG,
                 "Firmware update complete without install: reason=%s current=%s",
                 pendingFirmwareDecision.reason.c_str(), VERSION);
        // A later manual request must resolve again instead of reusing a stale
        // already-current decision.
        invalidateFirmwareUpdateDecision();
        return true;
    }

    if (pendingFirmwareDecision.kind == "migration") {
        const int uploaded = flushUploadQueue();
        ESP_LOGI(UPDATE_TAG,
                 "Migration selected; best-effort upload queue drain sent %d item(s)",
                 uploaded);
    }

    String error;
    if (!firmware::installApplicationAndFilesystem(pendingFirmwareDecision,
                                                   error)) {
        ESP_LOGE(UPDATE_TAG, "Firmware install failed: %s", error.c_str());
        // Signed artifact URLs and release assignments may change before a
        // technician retries, so never reuse a failed install decision.
        invalidateFirmwareUpdateDecision();
        return false;
    }

    ESP_LOGI(UPDATE_TAG, "Firmware hop installed; rebooting");
    delay(250);
    ESP.restart();
    return true;
}
