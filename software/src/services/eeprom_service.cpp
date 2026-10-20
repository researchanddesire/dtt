#include "eeprom_service.h"

#include <EEPROM.h>

static auto TAG = "EEPROM";

String trainerId;
String trainerIdShort;
bool isAlphaVersion;
int serialNumber = 0;

void initEEPROM() {
    ESP_LOGI(TAG, "Initializing EEPROM...");
    EEPROM.begin(EEPROM_SIZE);

    char trainerIdBuffer[100];
    char trainerIdShortBuffer[20];

    EEPROM.get(0, trainerIdBuffer);
    EEPROM.get(100, trainerIdShortBuffer);

    trainerId = String(trainerIdBuffer);
    trainerIdShort = String(trainerIdShortBuffer);

    EEPROM.get(110, isAlphaVersion);
    EEPROM.get(132, serialNumber);
    ESP_LOGI(TAG,
             "EEPROM initialization complete. TrainerId: %s, TrainerIdShort: "
             "%s, Serial: %d",
             trainerId.c_str(), trainerIdShort.c_str(), serialNumber);

    // if isAlphaVersion is not defined assume false
    // If isAlphaVersion is uninitialized (EEPROM default is 0xFF), set to false
    if (isAlphaVersion != true && isAlphaVersion != false) {
        isAlphaVersion = false;
        EEPROM.put(110, isAlphaVersion);
        EEPROM.commit();
        ESP_LOGI(TAG, "isAlphaVersion was undefined in EEPROM, set to false.");
    }

#ifdef BYPASS_EEPROM
    trainerId = "B1E57A229D22417E88B476977AF7226A";
    trainerIdShort = "7226A";
    serialNumber = 0;
    ESP_LOGI(TAG, "BYPASS_EEPROM enabled");
    ESP_LOGI(TAG, "EEPROM initialization complete. TrainerId: %s, Serial: %d",
             trainerId.c_str(), serialNumber);
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

#ifdef PROVISION
void saveToEEPROM(const String &newTrainerId, const int newSerialNumber) {
    ESP_LOGD(TAG, "Saving to EEPROM...");
    String newTrainerIdShort = newTrainerId.substring(0, 6);
    ESP_LOGD(TAG, "TrainerId: %s", trainerId.c_str());
    ESP_LOGD(TAG, "TrainerIdShort: %s", newTrainerIdShort.c_str());
    ESP_LOGD(TAG, "SerialNumber: %d", newSerialNumber);

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
    EEPROM.commit();

    // read now that trainer Id

    char newTrainerIdBuffer[100];
    char newTrainerIdShortBuffer[20];

    EEPROM.get(0, newTrainerIdBuffer);
    EEPROM.get(100, newTrainerIdShortBuffer);

    ESP_LOGI(TAG, "New TrainerId: %s", newTrainerIdBuffer);
    ESP_LOGI(TAG, "New TrainerIdShort: %s", newTrainerIdShortBuffer);

    ESP_LOGI(TAG, "EEPROM save complete.");

    // Update global variables
    trainerId = newTrainerId;
    trainerIdShort = newTrainerIdShort;
    serialNumber = newSerialNumber;
}
#endif