#ifndef WIFI_SETTINGS_H_
#define WIFI_SETTINGS_H_

#include <Arduino.h>
#include <ArduinoJson.h>  // https://github.com/bblanchon/ArduinoJson
#include <HTTPClient.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>

#ifndef PROVISION
#include <trainingTypes.h>
#include "Session.h"
#else
#include "structs/DashboardState.h"
#endif

#include "services/eeprom_service.h"

extern DashboardState dashboardState;

// Helper to POST JSON to Bubble server
int postJson(const String &endpoint, const JsonDocument &doc,
             String *responsePayload = nullptr, int timeoutMs = 15000);

void getIsPaired();

// Self-provisioning: ask the server for this trainer's identity by hardware
// address and store it. Used by the factory image and by production firmware
// that finds its stored identity blank.
extern String provisionError;

#ifdef PROVISION
bool getTrainerIdAndSerial();
void provisionTask(void *pvParameters);
#else

extern SegmentBase *currentSegment;
extern Session session;

#ifdef PIO_UNIT_TESTING
// Test observability hooks — written by async tasks, read by
// test/test_integration/ tests. Only compiled during tests.
extern bool trainingStartedNotified;
extern int trainingStartedHttpCode;

// Calibration upload hooks — written by sendCalibrationToBackend
extern bool calibrationUploaded;
extern int calibrationHttpCode;

// Results upload hooks — written by saveResultsTask
extern bool resultsUploaded;
extern int resultsHttpCode;
#endif

#define PAGE_SIZE 100

inline const Segment* getSegmentByIdx(uint16_t idx) {
    for (const auto& segment : session.segments) {
        if (segment.idx == idx) {
            return &segment;
        }
    }
    return nullptr;
}

inline bool isSegmentLoaded(uint16_t idx) {
    return getSegmentByIdx(idx) != nullptr;
}

bool getTrainerIdAndSerial();
void saveResultsTask(void *pvParameters);
WiFiClient *getCurrentWiFiClient();
void fetchSettingsTask(void *pvParameters);
void loadSessionTask(void *pvParameters);
void provisionTask(void *pvParameters);
void checkIfPairedTask(void *pvParameters);
void notifyTrainingTask(void *pvParameters);
void sendCalibrationToBackend(float minCm, float maxCm);
bool applySessionDocument(JsonDocument sessionJson, String &error);
#endif  // PROVISION

#endif  // WIFI_SETTINGS_H_
