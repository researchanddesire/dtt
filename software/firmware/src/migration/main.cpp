#include <Arduino.h>
#include <EEPROM.h>
#include <WiFi.h>
#include <bootloader_flash_config.h>
#include <esp32/rom/spi_flash.h>
#include <esp_flash.h>
#include <esp_flash_encrypt.h>
#include <esp_image_format.h>
#include <esp_ota_ops.h>
#include <esp_partition.h>
#include <esp_secure_boot.h>
#include <mbedtls/sha256.h>

#include <algorithm>
#include <cctype>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>

#include "DttMigrationAssets.h"
#include "DttMigrationPlan.h"
#include "FirmwareUpdateRuntime.h"
#include "constants/Version.h"
#include "services/eeprom_service.h"

#ifndef FIRMWARE_BUILD_SHA
#define FIRMWARE_BUILD_SHA "unknown"
#endif

#ifndef FIRMWARE_TRACK
#define FIRMWARE_TRACK "main"
#endif

// The bridge downloads over TLS and copies flash sectors from this task.
SET_LOOP_TASK_STACK_SIZE(16 * 1024);

// Keep a freshly installed bridge in the pending state until it decides to
// go ahead. A bootloader that supports rollback then returns to the previous
// firmware by itself if the bridge resets or loses power before that point.
extern "C" bool verifyRollbackLater() { return true; }

namespace {

constexpr std::uint32_t TABLE_OFFSET = 0x8000;
constexpr std::uint32_t TABLE_SECTOR_SIZE = 0x1000;
constexpr std::uint32_t BOOTLOADER_OFFSET = 0x1000;
constexpr std::uint32_t BOOTLOADER_REGION_SIZE =
    TABLE_OFFSET - BOOTLOADER_OFFSET;
constexpr std::uint32_t BOOTLOADER_HEADER_FLASH_CONFIG_OFFSET = 3;
constexpr std::uint32_t BOOTLOADER_STAGING_OFFSET = 0xF00000;
constexpr std::uint32_t V2_APP_SIZE = 0x780000;
constexpr std::uint32_t V2_APP1_OFFSET = 0x790000;
// The final firmware is staged where the 16 MiB table will place app1. Its
// record sits above the bootloader staging sectors, in the unused tail of
// that slot.
constexpr std::uint32_t FINAL_STAGE_LIMIT =
    BOOTLOADER_STAGING_OFFSET - V2_APP1_OFFSET;
constexpr std::uint32_t FINAL_RECORD_OFFSET = 0xF08000;
constexpr std::uint32_t FINAL_RECORD_MAGIC = 0x464D5444;
constexpr int FINAL_STAGE_ATTEMPTS = 2;
constexpr std::uint32_t MIGRATION_STATE_OFFSET = 0xF10000;
constexpr std::uint32_t MIGRATION_STATE_SIZE = 0x1000;
constexpr std::uint32_t MIGRATION_STATE_MAGIC = 0x324D5444;
constexpr std::uint16_t MIGRATION_STATE_VERSION = 1;

struct MigrationState {
    std::uint32_t magic;
    std::uint16_t version;
    std::uint16_t phase;
    char trainerId[100];
    char trainerIdShort[20];
    std::uint8_t isAlpha;
    std::uint8_t reserved[3];
    std::int32_t serialNumber;
    std::uint8_t legacyPartitionTableHash[32];
    std::uint8_t bridgeImageHash[32];
    std::uint8_t integrity[32];
};

static_assert(sizeof(MigrationState) < MIGRATION_STATE_SIZE,
              "migration state must fit its reserved sector");

struct FinalStageRecord {
    std::uint32_t magic;
    std::uint32_t sizeBytes;
    std::uint8_t sha256[32];
    std::uint8_t integrity[32];
};

alignas(4) std::uint8_t migrationStateSector[MIGRATION_STATE_SIZE];
alignas(4) std::uint8_t bootloaderRegion[BOOTLOADER_REGION_SIZE];

bool hashBytes(const void *data, const std::size_t size,
               std::uint8_t digest[32]) {
    return mbedtls_sha256_ret(static_cast<const std::uint8_t *>(data), size,
                              digest, 0) == 0;
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

bool rawFlashHash(const std::uint32_t address, const std::uint32_t size,
                  std::uint8_t digest[32]) {
    mbedtls_sha256_context sha;
    mbedtls_sha256_init(&sha);
    if (mbedtls_sha256_starts_ret(&sha, 0) != 0) {
        mbedtls_sha256_free(&sha);
        return false;
    }
    std::uint8_t buffer[1024];
    for (std::uint32_t offset = 0; offset < size; offset += sizeof(buffer)) {
        const auto count =
            std::min<std::uint32_t>(sizeof(buffer), size - offset);
        if (esp_flash_read(nullptr, buffer, address + offset, count) !=
                ESP_OK ||
            mbedtls_sha256_update_ret(&sha, buffer, count) != 0) {
            mbedtls_sha256_free(&sha);
            return false;
        }
    }
    const bool success = mbedtls_sha256_finish_ret(&sha, digest) == 0;
    mbedtls_sha256_free(&sha);
    return success;
}

std::string rawFlashHashString(const std::uint32_t address,
                               const std::uint32_t size) {
    std::uint8_t digest[32] = {};
    return rawFlashHash(address, size, digest) ? digestString(digest)
                                               : std::string{};
}

bool partitionMatches(const esp_partition_t *partition,
                      const std::uint32_t address, const std::uint32_t size) {
    return partition != nullptr && partition->address == address &&
           partition->size == size;
}

bool approvedLegacyTableHash(const std::string &actual) {
    for (std::size_t index = 0;
         index < dtt_migration_generated::LEGACY_PARTITION_TABLE_COUNT;
         ++index) {
        if (actual ==
            dtt_migration_generated::LEGACY_PARTITION_TABLE_SHA256[index]) {
            return true;
        }
    }
    return false;
}

const esp_partition_t *app0() {
    return esp_partition_find_first(ESP_PARTITION_TYPE_APP,
                                    ESP_PARTITION_SUBTYPE_APP_OTA_0, nullptr);
}

const esp_partition_t *app1() {
    return esp_partition_find_first(ESP_PARTITION_TYPE_APP,
                                    ESP_PARTITION_SUBTYPE_APP_OTA_1, nullptr);
}

bool legacyLayout() {
    const esp_partition_t *legacyApp0 = app0();
    const esp_partition_t *legacyApp1 = app1();
    const bool canonicalGeometry =
        partitionMatches(legacyApp0, 0x10000, 0x140000) &&
        partitionMatches(legacyApp1, 0x150000, 0x140000);
    const bool historicalGeometry =
        partitionMatches(legacyApp0, 0x10000, 0x1A0000) &&
        partitionMatches(legacyApp1, 0x1B0000, 0x1A0000);
    return (canonicalGeometry || historicalGeometry) &&
           approvedLegacyTableHash(
               rawFlashHashString(TABLE_OFFSET, TABLE_SECTOR_SIZE));
}

bool v2Layout() {
    const esp_partition_t *filesystem = esp_partition_find_first(
        ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_SPIFFS, nullptr);
    const esp_partition_t *migrationState = esp_partition_find_first(
        ESP_PARTITION_TYPE_DATA, static_cast<esp_partition_subtype_t>(0x40),
        "migrate");
    return partitionMatches(app0(), 0x10000, V2_APP_SIZE) &&
           partitionMatches(app1(), 0x790000, V2_APP_SIZE) &&
           partitionMatches(migrationState, MIGRATION_STATE_OFFSET,
                            MIGRATION_STATE_SIZE) &&
           partitionMatches(filesystem, 0xF11000, 0xDF000) &&
           rawFlashHashString(TABLE_OFFSET, TABLE_SECTOR_SIZE) ==
               dtt_migration_generated::V2_PARTITION_TABLE_SHA256;
}

bool runningFromApp0() {
    const esp_partition_t *running = esp_ota_get_running_partition();
    return running != nullptr && running->address == 0x10000;
}

std::uint32_t physicalFlashSize() {
    std::uint32_t result = 0;
    return esp_flash_get_physical_size(nullptr, &result) == ESP_OK
               ? result
               : ESP.getFlashChipSize();
}

std::string bootloaderHash() {
    return rawFlashHashString(BOOTLOADER_OFFSET,
                              TABLE_OFFSET - BOOTLOADER_OFFSET);
}

firmware::dtt::BootloaderState bootloaderState(const std::string &actual) {
    for (std::size_t index = 0;
         index < dtt_migration_generated::BOOTLOADER_TRANSITION_COUNT;
         ++index) {
        const auto &transition =
            dtt_migration_generated::BOOTLOADER_TRANSITIONS[index];
        if (actual == transition.legacyRegionSha256) {
            return firmware::dtt::BootloaderState::legacy4MiB;
        }
        if (actual == transition.migratedRegionSha256) {
            return firmware::dtt::BootloaderState::migrated16MiB;
        }
    }
    Serial.print("MIGRATOR_BOOTLOADER_NOT_APPROVED ");
    Serial.println(actual.c_str());
    return firmware::dtt::BootloaderState::unapproved;
}

const dtt_migration_generated::BootloaderTransition *legacyBootloaderTransition(
    const std::string &actual) {
    for (std::size_t index = 0;
         index < dtt_migration_generated::BOOTLOADER_TRANSITION_COUNT;
         ++index) {
        const auto &transition =
            dtt_migration_generated::BOOTLOADER_TRANSITIONS[index];
        if (actual == transition.legacyRegionSha256) return &transition;
    }
    return nullptr;
}

bool enableSixteenMiBFlashAccess() {
    if (esp_flash_default_chip == nullptr) {
        Serial.println("MIGRATOR_FLASH_DRIVER_MISSING");
        return false;
    }
    std::uint32_t current = 0;
    if (esp_flash_get_size(esp_flash_default_chip, &current) == ESP_OK &&
        current == firmware::dtt::SIXTEEN_MIB &&
        g_rom_flashchip.chip_size == firmware::dtt::SIXTEEN_MIB) {
        return true;
    }
    const std::uint32_t physical = physicalFlashSize();
    if (physical < firmware::dtt::SIXTEEN_MIB) {
        Serial.println("MIGRATOR_FLASH_TOO_SMALL");
        return false;
    }
    bootloader_flash_update_size(firmware::dtt::SIXTEEN_MIB);
    esp_flash_default_chip->size = firmware::dtt::SIXTEEN_MIB;
    std::uint32_t configured = 0;
    if (esp_flash_get_size(esp_flash_default_chip, &configured) != ESP_OK ||
        configured != firmware::dtt::SIXTEEN_MIB ||
        g_rom_flashchip.chip_size != firmware::dtt::SIXTEEN_MIB) {
        Serial.println("MIGRATOR_FLASH_CAPACITY_UPDATE_FAILED");
        return false;
    }
    Serial.println("MIGRATOR_FLASH_CAPACITY_16MB");
    return true;
}

bool securityFeaturesEnabled() {
    return esp_secure_boot_enabled() || esp_flash_encryption_enabled();
}

bool stateIntegrityValid(const MigrationState &state) {
    std::uint8_t actual[32] = {};
    return hashBytes(&state, offsetof(MigrationState, integrity), actual) &&
           memcmp(actual, state.integrity, sizeof(actual)) == 0;
}

bool migrationStateValid(const MigrationState &state) {
    return state.magic == MIGRATION_STATE_MAGIC &&
           state.version == MIGRATION_STATE_VERSION && state.phase == 1 &&
           stateIntegrityValid(state) &&
           firmware::dtt::validTrainerId(state.trainerId);
}

bool identityUsable() {
    initEEPROM();
    if (firmware::dtt::validTrainerId(trainerId.c_str())) return true;
    Serial.println("MIGRATOR_DEVICE_ID_INVALID");
    return false;
}

bool captureIdentitySnapshot(MigrationState &state) {
    if (!identityUsable()) return false;
    state = {};
    state.magic = MIGRATION_STATE_MAGIC;
    state.version = MIGRATION_STATE_VERSION;
    state.phase = 1;
    strlcpy(state.trainerId, trainerId.c_str(), sizeof(state.trainerId));
    strlcpy(state.trainerIdShort, trainerIdShort.c_str(),
            sizeof(state.trainerIdShort));
    state.isAlpha = isAlphaVersion ? 1 : 0;
    state.serialNumber = serialNumber;
    if (!rawFlashHash(TABLE_OFFSET, TABLE_SECTOR_SIZE,
                      state.legacyPartitionTableHash)) {
        Serial.println("MIGRATOR_STATE_TABLE_HASH_FAILED");
        return false;
    }
    const esp_partition_t *running = esp_ota_get_running_partition();
    if (running == nullptr ||
        esp_partition_get_sha256(running, state.bridgeImageHash) != ESP_OK ||
        !hashBytes(&state, offsetof(MigrationState, integrity),
                   state.integrity)) {
        Serial.println("MIGRATOR_STATE_IMAGE_HASH_FAILED");
        return false;
    }
    return true;
}

void encodeMigrationStateSector(const MigrationState &state) {
    memset(migrationStateSector, 0xff, sizeof(migrationStateSector));
    memcpy(migrationStateSector, &state, sizeof(state));
}

bool writeLegacyIdentitySnapshot(const MigrationState &state) {
    const esp_partition_t *legacyApp1 = app1();
    if (legacyApp1 == nullptr || legacyApp1->size < MIGRATION_STATE_SIZE) {
        Serial.println("MIGRATOR_STATE_SCRATCH_INVALID");
        return false;
    }
    const std::uint32_t offset = legacyApp1->size - MIGRATION_STATE_SIZE;
    encodeMigrationStateSector(state);
    if (esp_partition_erase_range(legacyApp1, offset, MIGRATION_STATE_SIZE) !=
            ESP_OK ||
        esp_partition_write(legacyApp1, offset, migrationStateSector,
                            sizeof(migrationStateSector)) != ESP_OK) {
        Serial.println("MIGRATOR_STATE_SCRATCH_WRITE_FAILED");
        return false;
    }
    MigrationState readback{};
    if (esp_partition_read(legacyApp1, offset, &readback, sizeof(readback)) !=
            ESP_OK ||
        memcmp(&state, &readback, sizeof(state)) != 0 ||
        !migrationStateValid(readback)) {
        Serial.println("MIGRATOR_STATE_SCRATCH_VERIFY_FAILED");
        return false;
    }
    Serial.println("MIGRATOR_STATE_SCRATCH_SAVED");
    return true;
}

bool readLegacyIdentitySnapshot(MigrationState &state) {
    const esp_partition_t *legacyApp1 = app1();
    if (legacyApp1 == nullptr || legacyApp1->size < MIGRATION_STATE_SIZE) {
        return false;
    }
    const std::uint32_t offset = legacyApp1->size - MIGRATION_STATE_SIZE;
    return esp_partition_read(legacyApp1, offset, &state, sizeof(state)) ==
               ESP_OK &&
           migrationStateValid(state);
}

bool identitySnapshotMatchesRuntime(const MigrationState &state) {
    std::uint8_t tableHash[32] = {};
    std::uint8_t imageHash[32] = {};
    const esp_partition_t *running = esp_ota_get_running_partition();
    initEEPROM();
    return rawFlashHash(TABLE_OFFSET, TABLE_SECTOR_SIZE, tableHash) &&
           running != nullptr &&
           esp_partition_get_sha256(running, imageHash) == ESP_OK &&
           memcmp(tableHash, state.legacyPartitionTableHash,
                  sizeof(tableHash)) == 0 &&
           memcmp(imageHash, state.bridgeImageHash, sizeof(imageHash)) == 0 &&
           trainerId == state.trainerId &&
           trainerIdShort == state.trainerIdShort &&
           isAlphaVersion == (state.isAlpha == 1) &&
           serialNumber == state.serialNumber;
}

bool writeHighIdentitySnapshot(const MigrationState &state) {
    if (!enableSixteenMiBFlashAccess()) return false;
    const esp_partition_t *partition = nullptr;
    const esp_err_t registration = esp_partition_register_external(
        esp_flash_default_chip, MIGRATION_STATE_OFFSET, MIGRATION_STATE_SIZE,
        "migrateTmp", ESP_PARTITION_TYPE_DATA,
        static_cast<esp_partition_subtype_t>(0x40), &partition);
    if (registration != ESP_OK || partition == nullptr) {
        Serial.printf("MIGRATOR_STATE_REGISTER_FAILED 0x%x\n", registration);
        return false;
    }
    encodeMigrationStateSector(state);
    const esp_err_t erase =
        esp_partition_erase_range(partition, 0, MIGRATION_STATE_SIZE);
    const esp_err_t write =
        erase == ESP_OK
            ? esp_partition_write(partition, 0, migrationStateSector,
                                  sizeof(migrationStateSector))
            : erase;
    MigrationState readback{};
    const esp_err_t read =
        write == ESP_OK
            ? esp_partition_read(partition, 0, &readback, sizeof(readback))
            : write;
    const esp_err_t deregistration =
        esp_partition_deregister_external(partition);
    if (erase != ESP_OK || write != ESP_OK || read != ESP_OK ||
        deregistration != ESP_OK ||
        memcmp(&state, &readback, sizeof(state)) != 0 ||
        !migrationStateValid(readback)) {
        Serial.printf("MIGRATOR_STATE_HIGH_WRITE_FAILED 0x%x 0x%x 0x%x 0x%x\n",
                      erase, write, read, deregistration);
        return false;
    }
    Serial.println("MIGRATOR_STATE_HIGH_SAVED");
    return true;
}

bool promoteIdentitySnapshot() {
    MigrationState state{};
    if (!readLegacyIdentitySnapshot(state) ||
        !identitySnapshotMatchesRuntime(state)) {
        Serial.println("MIGRATOR_STATE_SCRATCH_INVALID");
        return false;
    }
    return writeHighIdentitySnapshot(state);
}

bool readIdentitySnapshot(MigrationState &state) {
    return esp_flash_read(nullptr, &state, MIGRATION_STATE_OFFSET,
                          sizeof(state)) == ESP_OK &&
           migrationStateValid(state);
}

bool verifyOrRestoreIdentity() {
    MigrationState state{};
    if (!readIdentitySnapshot(state)) {
        Serial.println("MIGRATOR_STATE_INVALID");
        return false;
    }
    initEEPROM();
    if (trainerId == state.trainerId &&
        trainerIdShort == state.trainerIdShort &&
        isAlphaVersion == (state.isAlpha == 1) &&
        serialNumber == state.serialNumber) {
        Serial.println("MIGRATOR_IDENTITY_VERIFIED");
        return true;
    }
    EEPROM.put(0, state.trainerId);
    EEPROM.put(100, state.trainerIdShort);
    const bool restoredAlpha = state.isAlpha == 1;
    EEPROM.put(110, restoredAlpha);
    EEPROM.put(132, state.serialNumber);
    if (!EEPROM.commit()) {
        Serial.println("MIGRATOR_IDENTITY_RESTORE_FAILED");
        return false;
    }
    trainerId = state.trainerId;
    trainerIdShort = state.trainerIdShort;
    isAlphaVersion = restoredAlpha;
    serialNumber = state.serialNumber;
    Serial.println("MIGRATOR_IDENTITY_RESTORED");
    return true;
}

bool confirmMigrationImage() {
    const esp_partition_t *running = esp_ota_get_running_partition();
    if (running == nullptr) return false;
    esp_ota_img_states_t state = ESP_OTA_IMG_UNDEFINED;
    const esp_err_t result = esp_ota_get_state_partition(running, &state);
    if (result == ESP_ERR_NOT_SUPPORTED ||
        (result == ESP_OK && state != ESP_OTA_IMG_PENDING_VERIFY)) {
        return true;
    }
    return result == ESP_OK &&
           esp_ota_mark_app_valid_cancel_rollback() == ESP_OK;
}

// The firmware this bridge replaced, for as long as it can still be booted:
// the other legacy slot, holding a complete image that is not a copy of the
// bridge. Under the 16 MiB table that slot belongs to the final firmware.
const esp_partition_t *previousFirmware() {
    if (v2Layout()) return nullptr;
    const esp_partition_t *running = esp_ota_get_running_partition();
    const esp_partition_t *other = runningFromApp0() ? app1() : app0();
    if (running == nullptr || other == nullptr ||
        other->address == running->address) {
        return nullptr;
    }
    esp_image_metadata_t metadata = {};
    const esp_partition_pos_t position = {other->address, other->size};
    std::uint8_t runningDigest[32] = {};
    std::uint8_t otherDigest[32] = {};
    if (esp_image_verify(ESP_IMAGE_VERIFY_SILENT, &position, &metadata) !=
            ESP_OK ||
        esp_partition_get_sha256(running, runningDigest) != ESP_OK ||
        esp_partition_get_sha256(other, otherDigest) != ESP_OK ||
        memcmp(runningDigest, otherDigest, sizeof(runningDigest)) == 0) {
        return nullptr;
    }
    return other;
}

// Hands the device back to the firmware it ran before this update. It works
// with every bootloader, including those that cannot roll back by themselves.
// Returns only when there is no such firmware left to boot.
void returnToPreviousFirmware(const char *reason) {
    Serial.print("MIGRATOR_REFUSED ");
    Serial.println(reason);
    const esp_partition_t *previous = previousFirmware();
    if (previous == nullptr) {
        Serial.println("MIGRATOR_NO_PREVIOUS_FIRMWARE");
        return;
    }
    if (esp_ota_set_boot_partition(previous) != ESP_OK) {
        Serial.println("MIGRATOR_RETURN_SELECT_FAILED");
        // A pending image can still be handed back by the bootloader.
        esp_ota_mark_app_invalid_rollback_and_reboot();
        return;
    }
    Serial.println("MIGRATOR_RETURNING_TO_PREVIOUS_FIRMWARE");
    Serial.flush();
    delay(100);
    ESP.restart();
}

void reportPreflightFailure(const bool layoutSupported) {
    if (!layoutSupported) Serial.println("MIGRATOR_LAYOUT_NOT_APPROVED");
    if (physicalFlashSize() < firmware::dtt::SIXTEEN_MIB) {
        Serial.println("MIGRATOR_FLASH_TOO_SMALL");
    }
    if (securityFeaturesEnabled()) {
        Serial.println("MIGRATOR_SECURITY_NOT_SUPPORTED");
    }
    Serial.println("MIGRATOR_PREFLIGHT_FAILED");
}

bool relocateToApp0() {
    const esp_partition_t *source = esp_ota_get_running_partition();
    const esp_partition_t *destination = app0();
    const esp_partition_t *legacyApp1 = app1();
    if (!legacyLayout() || source == nullptr || destination == nullptr ||
        legacyApp1 == nullptr || source->address != legacyApp1->address ||
        source->size != destination->size) {
        Serial.println("MIGRATOR_RELOCATE_GUARD_FAILED");
        return false;
    }
    std::uint8_t sourceDigest[32] = {};
    if (esp_partition_get_sha256(source, sourceDigest) != ESP_OK ||
        esp_partition_erase_range(destination, 0, destination->size) !=
            ESP_OK) {
        Serial.println("MIGRATOR_RELOCATE_ERASE_FAILED");
        return false;
    }
    for (std::uint32_t offset = 0; offset < source->size;
         offset += sizeof(migrationStateSector)) {
        if (esp_partition_read(source, offset, migrationStateSector,
                               sizeof(migrationStateSector)) != ESP_OK ||
            esp_partition_write(destination, offset, migrationStateSector,
                                sizeof(migrationStateSector)) != ESP_OK) {
            Serial.println("MIGRATOR_RELOCATE_COPY_FAILED");
            return false;
        }
    }
    std::uint8_t destinationDigest[32] = {};
    if (esp_partition_get_sha256(destination, destinationDigest) != ESP_OK ||
        memcmp(sourceDigest, destinationDigest, sizeof(sourceDigest)) != 0) {
        Serial.println("MIGRATOR_RELOCATE_VERIFY_FAILED");
        return false;
    }
    if (esp_ota_set_boot_partition(destination) != ESP_OK) {
        Serial.println("MIGRATOR_RELOCATE_BOOT_FAILED");
        return false;
    }
    Serial.println("MIGRATOR_RELOCATE_OK");
    return true;
}

IRAM_ATTR esp_err_t allowBootloaderWrite(void *, const std::size_t address,
                                         const std::size_t size) {
    constexpr std::size_t end = BOOTLOADER_OFFSET + BOOTLOADER_REGION_SIZE;
    return address >= BOOTLOADER_OFFSET && address <= end && size <= end - address
               ? ESP_OK
               : ESP_ERR_INVALID_ARG;
}

bool patchAndValidateBootloader(
    const dtt_migration_generated::BootloaderTransition &transition) {
    if (transition.imageSize > sizeof(bootloaderRegion) ||
        transition.validationHashOffset + 32U != transition.imageSize ||
        BOOTLOADER_HEADER_FLASH_CONFIG_OFFSET >=
            transition.validationHashOffset ||
        bootloaderRegion[BOOTLOADER_HEADER_FLASH_CONFIG_OFFSET] !=
            transition.legacyHeaderByte) {
        Serial.println("MIGRATOR_BOOTLOADER_PATCH_GUARD_FAILED");
        return false;
    }
    bootloaderRegion[BOOTLOADER_HEADER_FLASH_CONFIG_OFFSET] =
        transition.migratedHeaderByte;
    if (!hashBytes(bootloaderRegion, transition.validationHashOffset,
                   bootloaderRegion + transition.validationHashOffset)) {
        Serial.println("MIGRATOR_BOOTLOADER_PATCH_HASH_FAILED");
        return false;
    }
    std::uint8_t regionHash[32] = {};
    if (!hashBytes(bootloaderRegion, sizeof(bootloaderRegion), regionHash) ||
        digestString(regionHash) != transition.migratedRegionSha256) {
        Serial.println("MIGRATOR_BOOTLOADER_PATCH_VERIFY_FAILED");
        return false;
    }
    return true;
}

bool stageBootloader(
    const dtt_migration_generated::BootloaderTransition &transition,
    const esp_partition_t *&staging) {
    staging = nullptr;
    const esp_err_t registration = esp_partition_register_external(
        esp_flash_default_chip, BOOTLOADER_STAGING_OFFSET,
        BOOTLOADER_REGION_SIZE, "bootStage", ESP_PARTITION_TYPE_DATA,
        static_cast<esp_partition_subtype_t>(0x41), &staging);
    if (registration != ESP_OK || staging == nullptr) {
        Serial.printf("MIGRATOR_BOOTLOADER_STAGE_REGISTER_FAILED 0x%x\n",
                      registration);
        return false;
    }
    const esp_err_t erase =
        esp_partition_erase_range(staging, 0, BOOTLOADER_REGION_SIZE);
    const esp_err_t write =
        erase == ESP_OK ? esp_partition_write(staging, 0, bootloaderRegion,
                                              sizeof(bootloaderRegion))
                        : erase;
    if (erase != ESP_OK || write != ESP_OK ||
        rawFlashHashString(BOOTLOADER_STAGING_OFFSET, BOOTLOADER_REGION_SIZE) !=
            transition.migratedRegionSha256) {
        Serial.printf("MIGRATOR_BOOTLOADER_STAGE_FAILED 0x%x 0x%x\n", erase,
                      write);
        esp_partition_deregister_external(staging);
        staging = nullptr;
        return false;
    }
    Serial.println("MIGRATOR_BOOTLOADER_STAGED");
    return true;
}

bool installBootloaderTransition() {
    const std::string actualHash = bootloaderHash();
    const auto *transition = legacyBootloaderTransition(actualHash);
    if (!legacyLayout() || !runningFromApp0() || transition == nullptr ||
        esp_flash_default_chip == nullptr ||
        esp_flash_default_chip->os_func == nullptr) {
        Serial.println("MIGRATOR_BOOTLOADER_GUARD_FAILED");
        return false;
    }
    MigrationState state{};
    if (!captureIdentitySnapshot(state) ||
        !writeLegacyIdentitySnapshot(state) ||
        esp_flash_read(nullptr, bootloaderRegion, BOOTLOADER_OFFSET,
                       sizeof(bootloaderRegion)) != ESP_OK ||
        rawFlashHashString(BOOTLOADER_OFFSET, BOOTLOADER_REGION_SIZE) !=
            transition->legacyRegionSha256 ||
        !patchAndValidateBootloader(*transition) ||
        !enableSixteenMiBFlashAccess()) {
        Serial.println("MIGRATOR_BOOTLOADER_PREPARE_FAILED");
        return false;
    }

    const esp_partition_t *staging = nullptr;
    if (!stageBootloader(*transition, staging)) return false;
    const std::uint32_t writeSpan =
        (transition->imageSize + TABLE_SECTOR_SIZE - 1U) &
        ~(TABLE_SECTOR_SIZE - 1U);
    if (writeSpan == 0 || writeSpan > BOOTLOADER_REGION_SIZE) {
        Serial.println("MIGRATOR_BOOTLOADER_WRITE_SPAN_INVALID");
        esp_partition_deregister_external(staging);
        return false;
    }
    const esp_partition_t *primary = nullptr;
    const esp_err_t registration = esp_partition_register_external(
        esp_flash_default_chip, BOOTLOADER_OFFSET, writeSpan,
        "bootPrimary", ESP_PARTITION_TYPE_DATA,
        static_cast<esp_partition_subtype_t>(0x42), &primary);
    if (registration != ESP_OK || primary == nullptr) {
        Serial.printf("MIGRATOR_BOOTLOADER_PRIMARY_REGISTER_FAILED 0x%x\n",
                      registration);
        esp_partition_deregister_external(staging);
        return false;
    }

    const esp_flash_os_functions_t *originalFunctions =
        esp_flash_default_chip->os_func;
    esp_flash_os_functions_t bootloaderFunctions = *originalFunctions;
    bootloaderFunctions.region_protected = allowBootloaderWrite;
    Serial.println("MIGRATOR_BOOTLOADER_COPY_START");
    Serial.flush();
    delay(100);
    esp_flash_default_chip->os_func = &bootloaderFunctions;
    esp_err_t copy = esp_partition_erase_range(primary, 0, writeSpan);
    for (std::uint32_t offset = 0;
         copy == ESP_OK && offset < transition->imageSize;
         offset += sizeof(migrationStateSector)) {
        const std::uint32_t count =
            std::min<std::uint32_t>(sizeof(migrationStateSector),
                                    transition->imageSize - offset);
        copy =
            esp_partition_read(staging, offset, migrationStateSector, count);
        if (copy == ESP_OK) {
            copy = esp_partition_write(primary, offset, migrationStateSector,
                                       count);
        }
    }
    esp_flash_default_chip->os_func = originalFunctions;
    const bool verified =
        copy == ESP_OK &&
        rawFlashHashString(BOOTLOADER_OFFSET, BOOTLOADER_REGION_SIZE) ==
            transition->migratedRegionSha256;
    const esp_err_t primaryDeregistration =
        esp_partition_deregister_external(primary);
    const esp_err_t stagingDeregistration =
        esp_partition_deregister_external(staging);
    if (!verified || primaryDeregistration != ESP_OK ||
        stagingDeregistration != ESP_OK) {
        Serial.printf("MIGRATOR_BOOTLOADER_COPY_FAILED 0x%x 0x%x 0x%x\n", copy,
                      primaryDeregistration, stagingDeregistration);
        return false;
    }
    Serial.println("MIGRATOR_BOOTLOADER_WRITE_OK");
    return true;
}

IRAM_ATTR esp_err_t allowPartitionTableWrite(void *, const std::size_t address,
                                             const std::size_t size) {
    constexpr std::size_t end = TABLE_OFFSET + TABLE_SECTOR_SIZE;
    return address >= TABLE_OFFSET && address <= end && size <= end - address
               ? ESP_OK
               : ESP_ERR_INVALID_ARG;
}

bool writeAndVerifyPartitionTable() {
    if (!legacyLayout() || !runningFromApp0() ||
        bootloaderState(bootloaderHash()) !=
            firmware::dtt::BootloaderState::migrated16MiB ||
        !promoteIdentitySnapshot()) {
        Serial.println("PARTITION_TABLE_GUARD_FAILED");
        return false;
    }
    if (esp_flash_default_chip == nullptr ||
        esp_flash_default_chip->os_func == nullptr) {
        Serial.println("PARTITION_TABLE_FLASH_GUARD_MISSING");
        return false;
    }
    const esp_flash_os_functions_t *originalFunctions =
        esp_flash_default_chip->os_func;
    esp_flash_os_functions_t partitionTableFunctions = *originalFunctions;
    partitionTableFunctions.region_protected = allowPartitionTableWrite;
    esp_flash_default_chip->os_func = &partitionTableFunctions;
    const esp_err_t eraseResult = esp_flash_erase_region(
        esp_flash_default_chip, TABLE_OFFSET, TABLE_SECTOR_SIZE);
    const esp_err_t writeResult =
        eraseResult == ESP_OK
            ? esp_flash_write(
                  esp_flash_default_chip,
                  dtt_migration_generated::V2_PARTITION_TABLE_SECTOR,
                  TABLE_OFFSET, TABLE_SECTOR_SIZE)
            : eraseResult;
    esp_flash_default_chip->os_func = originalFunctions;
    if (eraseResult != ESP_OK || writeResult != ESP_OK) {
        Serial.println("PARTITION_TABLE_WRITE_FAILED");
        return false;
    }
    if (rawFlashHashString(TABLE_OFFSET, TABLE_SECTOR_SIZE) !=
        dtt_migration_generated::V2_PARTITION_TABLE_SHA256) {
        Serial.println("PARTITION_TABLE_VERIFY_FAILED");
        return false;
    }
    Serial.println("PARTITION_TABLE_WRITE_OK");
    return true;
}

bool connectWifi() {
    if (WiFi.status() == WL_CONNECTED) return true;
    WiFi.mode(WIFI_STA);
    WiFi.begin();
    for (int attempt = 0; attempt < 45; ++attempt) {
        if (WiFi.status() == WL_CONNECTED) {
            Serial.println("MIGRATOR_WIFI_CONNECTED");
            return true;
        }
        delay(1000);
    }
    Serial.println("MIGRATOR_WIFI_FAILED");
    return false;
}

std::string runningFirmwareHash() {
    const esp_partition_t *running = esp_ota_get_running_partition();
    std::uint8_t digest[32] = {};
    return running != nullptr &&
                   esp_partition_get_sha256(running, digest) == ESP_OK
               ? digestString(digest)
               : std::string{};
}

// Describes the device as it will be once the 16 MiB table is installed, so
// the resolver answers with the final firmware for that layout.
firmware::DeviceReport finalFirmwareReport() {
    firmware::DeviceReport report;
    report.deviceType = "dtt";
    report.deviceId = trainerId.c_str();
    report.reportedTrack = FIRMWARE_TRACK;
    report.currentVersion = VERSION;
    report.currentBuild = FIRMWARE_BUILD_SHA;
    report.firmwareHash = runningFirmwareHash();
    report.chip = ESP.getChipModel();
    report.chipRevision = ESP.getChipRevision();
    report.chipCores = ESP.getChipCores();
    report.flashSizeBytes = physicalFlashSize();
    report.otaSlotSizeBytes = V2_APP_SIZE;
    report.psramSizeBytes = ESP.getPsramSize();
    report.partitionLayout = "dtt-ota-16mb-v1";
    report.partitionTableHash =
        rawFlashHashString(TABLE_OFFSET, TABLE_SECTOR_SIZE);
    report.bootloaderHash = bootloaderHash();
    firmware::provenance::reconcile(report);
    return report;
}

bool resolveFinalFirmware(firmware::DeviceReport &report,
                          firmware::Decision &decision) {
    report = finalFirmwareReport();
    String error;
    if (!firmware::postCheck(RAD_SERVER, report, decision, error)) {
        Serial.print("MIGRATOR_RESOLVE_FAILED ");
        Serial.println(error);
        return false;
    }
    firmware::provenance::observeCurrent(report, decision);
    if (!decision.shouldUpdate || decision.kind != "firmware") {
        Serial.println("MIGRATOR_WAITING_FOR_FINAL");
        return false;
    }
    return true;
}

bool readFinalStageRecord(FinalStageRecord &record) {
    std::uint8_t integrity[32] = {};
    return enableSixteenMiBFlashAccess() &&
           esp_flash_read(nullptr, &record, FINAL_RECORD_OFFSET,
                          sizeof(record)) == ESP_OK &&
           record.magic == FINAL_RECORD_MAGIC &&
           firmware::dtt::stagedFinalFirmwareFits(record.sizeBytes,
                                                  FINAL_STAGE_LIMIT) &&
           hashBytes(&record, offsetof(FinalStageRecord, integrity),
                     integrity) &&
           memcmp(integrity, record.integrity, sizeof(integrity)) == 0;
}

// True when the final firmware recorded by an earlier boot is still in flash,
// byte for byte.
bool finalFirmwareStaged() {
    FinalStageRecord record{};
    std::uint8_t digest[32] = {};
    return readFinalStageRecord(record) &&
           rawFlashHash(V2_APP1_OFFSET, record.sizeBytes, digest) &&
           memcmp(digest, record.sha256, sizeof(digest)) == 0;
}

// Registers a region above the legacy table for one operation.
const esp_partition_t *registerHighFlash(const std::uint32_t offset,
                                         const std::uint32_t size,
                                         const char *label,
                                         const std::uint8_t subtype) {
    const esp_partition_t *partition = nullptr;
    const esp_err_t registration = esp_partition_register_external(
        esp_flash_default_chip, offset, size, label, ESP_PARTITION_TYPE_DATA,
        static_cast<esp_partition_subtype_t>(subtype), &partition);
    if (registration != ESP_OK || partition == nullptr) {
        Serial.printf("MIGRATOR_HIGH_FLASH_REGISTER_FAILED %s 0x%x\n", label,
                      registration);
        return nullptr;
    }
    return partition;
}

bool writeFinalStageRecord(const FinalStageRecord *record) {
    const esp_partition_t *partition = registerHighFlash(
        FINAL_RECORD_OFFSET, TABLE_SECTOR_SIZE, "finalRecord", 0x44);
    if (partition == nullptr) return false;
    esp_err_t result =
        esp_partition_erase_range(partition, 0, TABLE_SECTOR_SIZE);
    if (result == ESP_OK && record != nullptr) {
        result = esp_partition_write(partition, 0, record, sizeof(*record));
    }
    const esp_err_t deregistration =
        esp_partition_deregister_external(partition);
    return result == ESP_OK && deregistration == ESP_OK;
}

// Downloads the final firmware into the flash the 16 MiB table will call
// app1, while the legacy table and the previous firmware are both untouched.
// After this, the rest of the migration needs neither Wi-Fi nor the server.
bool stageFinalFirmware() {
    if (!connectWifi()) return false;
    firmware::DeviceReport report;
    firmware::Decision decision;
    if (!resolveFinalFirmware(report, decision)) return false;
    const firmware::Artifact *application = nullptr;
    for (std::size_t index = 0; index < decision.artifactCount; ++index) {
        const firmware::Artifact &artifact = decision.artifacts[index];
        if (artifact.role == "application" && application == nullptr) {
            application = &artifact;
        } else if (artifact.role == "application" ||
                   artifact.role == "filesystem") {
            // Only a single application image can be staged ahead of the
            // table change.
            application = nullptr;
            break;
        }
    }
    if (application == nullptr ||
        !firmware::dtt::stagedFinalFirmwareFits(application->sizeBytes,
                                                FINAL_STAGE_LIMIT)) {
        Serial.println("MIGRATOR_FINAL_NOT_STAGEABLE");
        return false;
    }
    // Drop any earlier record before its image is overwritten.
    if (!enableSixteenMiBFlashAccess() || !writeFinalStageRecord(nullptr)) {
        Serial.println("MIGRATOR_FINAL_RECORD_CLEAR_FAILED");
        return false;
    }
    const std::uint32_t stageSpan =
        (application->sizeBytes + TABLE_SECTOR_SIZE - 1U) &
        ~(TABLE_SECTOR_SIZE - 1U);
    const esp_partition_t *stage =
        registerHighFlash(V2_APP1_OFFSET, stageSpan, "finalStage", 0x43);
    if (stage == nullptr) return false;
    Serial.println("MIGRATOR_FINAL_STAGE_START");
    String error;
    const bool downloaded =
        firmware::downloadArtifactToPartition(*application, stage, error);
    const esp_err_t deregistration = esp_partition_deregister_external(stage);
    if (!downloaded || deregistration != ESP_OK) {
        Serial.print("MIGRATOR_FINAL_STAGE_FAILED ");
        Serial.println(error);
        return false;
    }
    FinalStageRecord record{};
    record.magic = FINAL_RECORD_MAGIC;
    record.sizeBytes = application->sizeBytes;
    if (!rawFlashHash(V2_APP1_OFFSET, record.sizeBytes, record.sha256) ||
        !hashBytes(&record, offsetof(FinalStageRecord, integrity),
                   record.integrity) ||
        !writeFinalStageRecord(&record) || !finalFirmwareStaged()) {
        Serial.println("MIGRATOR_FINAL_RECORD_WRITE_FAILED");
        return false;
    }
    firmware::provenance::stageUpdate(report, decision);
    Serial.println("MIGRATOR_FINAL_STAGED");
    return true;
}

// Boots the staged final firmware once the 16 MiB table is in place. Its
// record is used once: a final firmware that fails to start returns here and
// is then fetched again over the network.
bool activateStagedFinalFirmware() {
    const esp_partition_t *target = app1();
    if (target == nullptr || !finalFirmwareStaged() ||
        !verifyOrRestoreIdentity()) {
        return false;
    }
    if (esp_ota_set_boot_partition(target) != ESP_OK) {
        Serial.println("MIGRATOR_FINAL_ACTIVATE_FAILED");
        return false;
    }
    esp_partition_erase_range(target, FINAL_RECORD_OFFSET - V2_APP1_OFFSET,
                              TABLE_SECTOR_SIZE);
    Serial.println("MIGRATOR_FINAL_ACTIVATED");
    return true;
}

bool installFinalFirmware() {
    if (!verifyOrRestoreIdentity() || !connectWifi()) return false;
    firmware::DeviceReport report;
    firmware::Decision decision;
    if (!resolveFinalFirmware(report, decision)) return false;
    firmware::provenance::stageUpdate(report, decision);
    String error;
    if (!firmware::installApplicationAndFilesystem(decision, error)) {
        Serial.print("MIGRATOR_FINAL_INSTALL_FAILED ");
        Serial.println(error);
        return false;
    }
    Serial.println("MIGRATOR_FINAL_OTA_OK");
    return true;
}

void runMigration() {
    const auto bootloader = bootloaderState(bootloaderHash());
    const bool legacy = legacyLayout();
    const bool v2 = v2Layout();
    const auto action = firmware::dtt::nextMigrationAction(
        legacy, v2, runningFromApp0(), physicalFlashSize(),
        securityFeaturesEnabled(), bootloader);

    // Nothing below this block may fail for a reason that could have been
    // found here, while the previous firmware can still take the device back.
    const char *refusal = "preflight";
    bool identityValid = false;
    bool finalStaged = false;
    if (action == firmware::dtt::MigrationAction::failClosed) {
        reportPreflightFailure(legacy || v2);
    } else if (legacy) {
        identityValid = identityUsable();
        finalStaged = identityValid && finalFirmwareStaged();
        if (!identityValid) refusal = "identity";
    }
    auto step = firmware::dtt::nextPreparationStep(action, legacy,
                                                   identityValid, finalStaged);
    if (step == firmware::dtt::PreparationStep::stageFinalFirmware) {
        bool staged = false;
        for (int attempt = 0; attempt < FINAL_STAGE_ATTEMPTS && !staged;
             ++attempt) {
            staged = stageFinalFirmware();
        }
        step = staged ? firmware::dtt::PreparationStep::proceed
                      : firmware::dtt::PreparationStep::refuse;
        refusal = "final-firmware-unavailable";
    }
    if (step == firmware::dtt::PreparationStep::refuse) {
        returnToPreviousFirmware(refusal);
        Serial.println("MIGRATOR_FAIL_CLOSED");
        return;
    }
    // From here the bridge owns the device until the final firmware runs.
    if (!confirmMigrationImage()) {
        Serial.println("MIGRATOR_IMAGE_CONFIRM_FAILED");
        return;
    }

    switch (action) {
        case firmware::dtt::MigrationAction::relocateToApp0:
            if (relocateToApp0()) ESP.restart();
            break;
        case firmware::dtt::MigrationAction::writeBootloader:
            if (installBootloaderTransition()) ESP.restart();
            break;
        case firmware::dtt::MigrationAction::writePartitionTable:
#if defined(DTT_MIGRATION_LAB_BOOTLOADER_CHECKPOINT_MS) && \
    DTT_MIGRATION_LAB_BOOTLOADER_CHECKPOINT_MS > 0
            Serial.println("MIGRATOR_LAB_BOOTLOADER_CHECKPOINT");
            Serial.flush();
            delay(DTT_MIGRATION_LAB_BOOTLOADER_CHECKPOINT_MS);
#endif
            if (writeAndVerifyPartitionTable()) ESP.restart();
            break;
        case firmware::dtt::MigrationAction::resolveFinalFirmware:
            if (activateStagedFinalFirmware() || installFinalFirmware()) {
                ESP.restart();
            }
            break;
        default:
            Serial.println("MIGRATOR_FAIL_CLOSED");
            break;
    }
}

}  // namespace

void setup() {
    Serial.begin(115200);
    delay(750);
    Serial.print("MIGRATOR_BOOTED ");
    Serial.print(VERSION);
    Serial.print(" ");
    Serial.print(FIRMWARE_BUILD_SHA);
    Serial.print(" ");
    Serial.println(FIRMWARE_TRACK);
    runMigration();
}

void loop() {
    delay(60000);
    runMigration();
}
