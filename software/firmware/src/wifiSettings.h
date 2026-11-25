#ifndef WIFI_SETTINGS_H_
#define WIFI_SETTINGS_H_

#include <Arduino.h>
#include <ArduinoJson.h>  // https://github.com/bblanchon/ArduinoJson
#include <HTTPClient.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>

#ifndef PROVISION
#include <trainingTypes.h>
#include <TrainingLifecycle.h>
#include <memory>
#include <mutex>
#include "utils/RecusiveMutex.h"
#include "Session.h"
#else
#include "structs/DashboardState.h"
#endif

#include "services/eeprom_service.h"
#include "services/settings_fetch_status.h"

extern DashboardState dashboardState;

// Helper to POST JSON to Bubble server
int postJson(const String &endpoint, const JsonDocument &doc,
             String *responsePayload = nullptr, int timeoutMs = 15000,
             DashboardResponseMetrics *metrics = nullptr);

void getIsPaired();

// Self-provisioning: ask the server for this trainer's identity by hardware
// address and store it. Used by the factory image and by production firmware
// that finds its stored identity blank.
extern String provisionError;

#ifdef PROVISION
bool getTrainerIdAndSerial();
void provisionTask(void *pvParameters);
#else

extern std::shared_ptr<SegmentBase> currentSegment;
extern ESP32RecursiveMutex trainingMutex;
using TrainingGuard = std::lock_guard<ESP32RecursiveMutex>;
extern TrainingLifecycle trainingLifecycle;
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
void startSaveResultsTask();
WiFiClient *getCurrentWiFiClient();
void fetchSettingsTask(void *pvParameters);
void loadSessionTask(void *pvParameters);
void provisionTask(void *pvParameters);
void checkIfPairedTask(void *pvParameters);
void notifyTrainingTask(void *pvParameters);
void sendCalibrationToBackend(float minCm, float maxCm);
// controller: the name of a Bluetooth controller app starting this session
// (for example "E-Stim Bridge"). Such a session is not saved, the trainer shows
// only the app's name for it, and the trainer's own session comes back once the
// app lets go of control. Empty for an ordinary session, which is saved.
bool applySessionDocument(JsonDocument sessionJson, String &error,
                          const String &controller = String());
bool controllerSessionActive();
String controllerSessionName();
// Called when the control lease ends, from any task.
void markControllerReleased();
// True once per release; the caller then redraws the details screen.
bool takeControllerReleaseNotice();
// Puts the trainer's own session back if the controller has let go. Only call
// while no segment is playing.
void restoreOwnSessionIfReleased();
// Forgets the controller session without restoring (a new session replaced it).
void forgetControllerSession();
SettingsFetchStatus getSettingsFetchStatus();
#endif  // PROVISION

#endif  // WIFI_SETTINGS_H_
