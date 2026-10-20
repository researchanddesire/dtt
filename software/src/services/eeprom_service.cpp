#include "eeprom_service.h"

#include <EEPROM.h>

static auto TAG = "EEPROM";

String trainerId;
String trainerIdShort;
bool isAlphaVersion;
int serialNumber = 0;

// Erased flash reads back as 0xFF with no terminator. A trainer whose NVS was
// wiped (for example by a flasher writing over it) must not treat that, or
// whatever follows it on the stack, as its identity.
static bool isUsableIdentity(const char *buffer, const size_t size) {
    for (size_t i = 0; i < size; i++) {
        const auto c = static_cast<unsigned char>(buffer[i]);
        if (c == '\0') {
            return i > 0;
        }
        if (c < 0x20 || c > 0x7E) {
            return false;
        }
    }
    return false;  // no terminator inside the buffer
}

void initEEPROM() {
    ESP_LOGI(TAG, "Initializing EEPROM...");
    const bool eepromReady = EEPROM.begin(EEPROM_SIZE);
    if (!eepromReady) {
        ESP_LOGE(TAG, "EEPROM storage unavailable; treating identity as blank");
    }

    // Zeroed so an unreadable EEPROM reads as empty, never as stack noise.
    char trainerIdBuffer[100] = {};
    char trainerIdShortBuffer[20] = {};

    if (eepromReady) {
        EEPROM.get(0, trainerIdBuffer);
        EEPROM.get(100, trainerIdShortBuffer);
    }
    trainerIdBuffer[sizeof(trainerIdBuffer) - 1] = '\0';
    trainerIdShortBuffer[sizeof(trainerIdShortBuffer) - 1] = '\0';

    if (isUsableIdentity(trainerIdBuffer, sizeof(trainerIdBuffer)) &&
        isUsableIdentity(trainerIdShortBuffer, sizeof(trainerIdShortBuffer))) {
        trainerId = String(trainerIdBuffer);
        trainerIdShort = String(trainerIdShortBuffer);
    } else {
        trainerId = "";
        trainerIdShort = "";
        ESP_LOGW(TAG,
                 "No usable trainer ID in EEPROM; the device will provision "
                 "itself once online");
    }

    // Read the persisted flag as a byte: 0xFF is not a valid bool value.
    uint8_t alphaValue = 0;
    if (eepromReady) {
        EEPROM.get(110, alphaValue);
        EEPROM.get(132, serialNumber);
    }
    isAlphaVersion = alphaValue == 1;
    if (serialNumber < 0) {
        serialNumber = 0;  // erased flash reads back as -1
    }
    ESP_LOGI(TAG, "EEPROM initialization complete");

    // if isAlphaVersion is not defined assume false
    // If isAlphaVersion is uninitialized (EEPROM default is 0xFF), set to false
    if (eepromReady && alphaValue > 1) {
        isAlphaVersion = false;
        EEPROM.put(110, isAlphaVersion);
        EEPROM.commit();
        ESP_LOGI(TAG, "isAlphaVersion was undefined in EEPROM, set to false.");
    }

#ifdef BYPASS_EEPROM
    // Matches rad-app's integration seed (042_dtt_integration_test.sql).
    trainerId = "B1E57A229D22417E88B476977AF7226A";
    trainerIdShort = "7226A";
    serialNumber = 0;
    ESP_LOGI(TAG, "BYPASS_EEPROM enabled");
#endif

#ifdef FORCE_TRAINER_ID
    trainerId = FORCE_TRAINER_ID;
    trainerIdShort = String(FORCE_TRAINER_ID).substring(0, 6);
    serialNumber = 0;
#endif
}

void toggleIsAlpha() {
    EEPROM.put(110, !isAlphaVersion);
    EEPROM.commit();

    isAlphaVersion = !isAlphaVersion;
}

bool saveToEEPROM(const String &newTrainerId, const int newSerialNumber) {
    ESP_LOGD(TAG, "Saving to EEPROM...");
    String newTrainerIdShort = newTrainerId.substring(0, 6);

    // Store char buffers to EEPROM with size limits
    char trainerIdBuffer[100];
    char trainerIdShortBuffer[20];

    // Copy string data to buffers, ensuring null termination
    strncpy(trainerIdBuffer, newTrainerId.c_str(), sizeof(trainerIdBuffer) - 1);
    trainerIdBuffer[sizeof(trainerIdBuffer) - 1] = '\0';

    strncpy(trainerIdShortBuffer, newTrainerIdShort.c_str(),
            sizeof(trainerIdShortBuffer) - 1);
    trainerIdShortBuffer[sizeof(trainerIdShortBuffer) - 1] = '\0';

    EEPROM.put(0, trainerIdBuffer);
    EEPROM.put(100, trainerIdShortBuffer);
    EEPROM.put(110, false);
    EEPROM.put(132, newSerialNumber);
    const bool committed = EEPROM.commit();

    // Read back and compare before anyone reboots on this identity: an
    // unsaved ID would just provision again on the next boot, forever.
    char newTrainerIdBuffer[100] = {};
    char newTrainerIdShortBuffer[20] = {};
    int newSerialNumberReadBack = -1;

    EEPROM.get(0, newTrainerIdBuffer);
    EEPROM.get(100, newTrainerIdShortBuffer);
    EEPROM.get(132, newSerialNumberReadBack);
    newTrainerIdBuffer[sizeof(newTrainerIdBuffer) - 1] = '\0';
    newTrainerIdShortBuffer[sizeof(newTrainerIdShortBuffer) - 1] = '\0';

    const bool saved =
        committed &&
        memcmp(newTrainerIdBuffer, trainerIdBuffer, sizeof(trainerIdBuffer)) == 0 &&
        memcmp(newTrainerIdShortBuffer, trainerIdShortBuffer,
               sizeof(trainerIdShortBuffer)) == 0 &&
        newSerialNumberReadBack == newSerialNumber;
    if (!saved) {
        ESP_LOGE(TAG, "EEPROM save failed (commit=%d); identity not updated",
                 committed);
        return false;
    }

    ESP_LOGI(TAG, "EEPROM save complete.");

    // Update global variables
    trainerId = newTrainerId;
    trainerIdShort = newTrainerIdShort;
    serialNumber = newSerialNumber;
    return true;
}
