#ifndef TEST_INTEGRATION_HELPERS_H
#define TEST_INTEGRATION_HELPERS_H

#include <Arduino.h>
#include <Preferences.h>
#include <WiFi.h>
#include <unity.h>

// clang-format off
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
// clang-format on

#include "components/HeaderBar.h"
#include "services/board.hpp"
#include "services/button.h"
#include "services/display.h"
#include "services/eeprom_service.h"
#include "services/handles.h"
#include "services/leds.h"
#include "services/upload_queue.h"
#include "services/vibrator.h"
#include "services/wifi_service.h"
#include "state/state.h"
#include "wifiSettings.h"

namespace sml = boost::sml;

static bool hardwareInitialized = false;
static bool preStateMachineInitDone = false;

/// Initialize hardware up to WiFi connection (before state machine).
/// Call this first, then triggerUnpairing(), then initStateMachinePhase().
static void initHardwareBeforeStateMachine() {
    if (preStateMachineInitDone) return;

    Serial.begin(115200);
    delay(1000);

    initBoard();
    initEEPROM();
    initFastLEDs();
    initDisplay();
    initHeaderBar();
    initUploadQueue();
    initWifi();
    initButtonService();
    initVibratorService();

    preStateMachineInitDone = true;
}

/// Initialize state machine (triggers preflight).
/// Call after initHardwareBeforeStateMachine() and any pre-preflight setup.
static void initStateMachinePhase() {
    if (hardwareInitialized) return;
    initStateMachine();
    hardwareInitialized = true;
}

/// Run the full firmware boot sequence (same as production main.cpp).
/// Safe to call multiple times — only runs once.
static void initHardware() {
    if (hardwareInitialized) return;

    Serial.begin(115200);
    delay(1000);

    initBoard();
    initEEPROM();
    initFastLEDs();
    initDisplay();
    initHeaderBar();
    initUploadQueue();
    initWifi();
    initButtonService();
    initVibratorService();
    initStateMachine();

    hardwareInitialized = true;
}

/// POST to /api/dtt/v2/test-unpair to reset pairing state.
/// Returns HTTP status code (200 on success).
static int triggerUnpairing() {
    JsonDocument doc;
    doc["trainerId"] = trainerId;

    String payload;
    int httpCode = postJson("/test-unpair", doc, &payload);

    Serial.printf("[INFO] test-unpair response: %d, payload: %s\n", httpCode,
                  payload.c_str());
    return httpCode;
}

/// POST to /api/dtt/v2/test-pair to pair the device.
/// Returns HTTP status code (200 on success).
static int triggerPairing() {
    JsonDocument doc;
    doc["trainerId"] = trainerId;

    String payload;
    int httpCode = postJson("/test-pair", doc, &payload);

    Serial.printf("[INFO] test-pair response: %d, payload: %s\n", httpCode,
                  payload.c_str());
    return httpCode;
}

// --- NVS-based test phase tracking ---
// Allows tests to restart the device and continue from where they left off.

static Preferences testPrefs;

/// Get the current test phase from NVS (0 = initial, 1 = after restart).
static int getTestPhase() {
    testPrefs.begin("test_phase", true);  // read-only
    int phase = testPrefs.getInt("phase", 0);
    testPrefs.end();
    return phase;
}

/// Set the test phase in NVS (persists across restarts).
static void setTestPhase(int phase) {
    testPrefs.begin("test_phase", false);  // read-write
    testPrefs.putInt("phase", phase);
    testPrefs.end();
}

/// Clear the test phase from NVS (resets to phase 0).
static void clearTestPhase() {
    testPrefs.begin("test_phase", false);
    testPrefs.clear();
    testPrefs.end();
}

/// Wait for checkIfPairedTaskHandle to become non-NULL.
/// Needed because on_entry actions (including startTask) run after state change.
static void waitForCheckIfPairedTaskHandle() {
    Serial.println("[TEST] Waiting for checkIfPairedTaskHandle...");
    int elapsed = 0;
    while (checkIfPairedTaskHandle == NULL && elapsed < 2000) {
        vTaskDelay(pdMS_TO_TICKS(50));
        elapsed += 50;
    }
    Serial.printf("[TEST] checkIfPairedTaskHandle is now: %p (waited %dms)\n",
                  (void*)checkIfPairedTaskHandle, elapsed);
}

/// Suspend checkIfPairedTask to prevent concurrent HTTP requests during tests.
/// Waits for the task handle to become valid first.
static void suspendCheckIfPairedTask() {
    waitForCheckIfPairedTaskHandle();
    Serial.printf("[TEST] suspendCheckIfPairedTask: handle=%p\n",
                  (void*)checkIfPairedTaskHandle);
    if (checkIfPairedTaskHandle != NULL) {
        vTaskSuspend(checkIfPairedTaskHandle);
        Serial.println("[TEST] Suspended checkIfPairedTask");
    } else {
        Serial.println("[TEST] WARNING: checkIfPairedTaskHandle is NULL after wait, cannot suspend");
    }
}

/// Resume checkIfPairedTask after test HTTP calls complete.
static void resumeCheckIfPairedTask() {
    if (checkIfPairedTaskHandle != NULL) {
        vTaskResume(checkIfPairedTaskHandle);
        Serial.println("[TEST] Resumed checkIfPairedTask");
    }
}

/// Wait for notifyTrainingTask to complete (HTTP response received).
/// trainingStartedHttpCode is -1 until the task writes the response code.
static void waitForNotifyTrainingTaskComplete(int timeoutMs = 15000) {
    Serial.println("[TEST] Waiting for notifyTrainingTask to complete...");
    int elapsed = 0;
    while (trainingStartedHttpCode == -1 && elapsed < timeoutMs) {
        vTaskDelay(pdMS_TO_TICKS(250));
        elapsed += 250;
    }
    Serial.printf("[TEST] notifyTrainingTask: httpCode=%d (waited %dms)\n",
                  trainingStartedHttpCode, elapsed);
}

/// Wait for WiFi connection, up to 15 seconds.
static void waitForWifi() {
    int elapsed = 0;
    while (WiFi.status() != WL_CONNECTED && elapsed < 15000) {
        vTaskDelay(pdMS_TO_TICKS(500));
        elapsed += 500;
    }
}

/// Wait for preflight to complete, up to 20 seconds.
static void waitForPreflight() {
    int elapsed = 0;
    while (dashboardState.preflightPending && elapsed < 20000) {
        vTaskDelay(pdMS_TO_TICKS(500));
        elapsed += 500;
    }
}

/// Dispatch the same event as the physical button service and wait for the
/// state machine to leave a state. Hardware CI cannot depend on a human being
/// present to press the fixture button, but the transition actions still use
/// the real board services and sensors.
template <typename IsInStateFn>
static bool pressButtonAndWaitForExit(IsInStateFn isInState,
                                      const char* stateName,
                                      int timeoutMs = 5000) {
    Serial.printf("[TEST] Dispatching button press in '%s'\n", stateName);
    stateMachine->process_event(button_pressed{});

    int elapsed = 0;
    while (elapsed < timeoutMs) {
        if (!isInState()) return true;
        vTaskDelay(pdMS_TO_TICKS(250));
        elapsed += 250;
    }
    return false;
}

template <typename IsInStateFn>
static bool longPressButtonAndWaitForExit(IsInStateFn isInState,
                                          const char* stateName,
                                          int timeoutMs = 5000) {
    Serial.printf("[TEST] Dispatching long button press in '%s'\n", stateName);
    stateMachine->process_event(button_long_pressed{});

    int elapsed = 0;
    while (elapsed < timeoutMs) {
        if (!isInState()) return true;
        vTaskDelay(pdMS_TO_TICKS(250));
        elapsed += 250;
    }
    return false;
}

/// Wait for the state machine to reach a specific state.
/// Uses a lambda so callers can pass compile-time `"state"_s` literals.
///
/// Usage:
///   waitForState([](){ return stateMachine->is("play.grade"_s); },
///                "play.grade", 60000);
template <typename IsInStateFn>
static bool waitForState(IsInStateFn isInState, const char* stateName,
                         int timeoutMs) {
    Serial.printf("[WAIT] Waiting up to %ds for state '%s'...\n",
                  timeoutMs / 1000, stateName);

    int elapsed = 0;
    while (elapsed < timeoutMs) {
        if (isInState()) {
            Serial.printf("[WAIT] Reached '%s' after %dms\n", stateName,
                          elapsed);
            return true;
        }
        vTaskDelay(pdMS_TO_TICKS(250));
        elapsed += 250;
    }
    Serial.printf("[WAIT] Timed out waiting for '%s'\n", stateName);
    return false;
}

/// Advance the state machine past init.idle with an automated button event.
/// This triggers the init.idle → init.preflight transition, which fires
/// the notifyTrainingTask.
/// Returns true if successfully advanced past init, false on timeout.
static bool advancePastInit() {
    if (stateMachine->is("init.idle"_s)) {
        bool exited = pressButtonAndWaitForExit(
            []() { return stateMachine->is("init.idle"_s); },
            "init.idle");

        if (!exited) {
            Serial.println("[ERROR] Timed out waiting for init.idle exit");
            return false;
        }
    } else {
        Serial.println(
            "[INFO] init.idle already exited (timeout auto-advanced)");
    }

    // Give the state machine time to settle through preflight transitions
    vTaskDelay(pdMS_TO_TICKS(3000));

    bool stillInInit = stateMachine->is("init"_s);
    Serial.printf("[INFO] After advancing: init=%d\n", stillInInit);

    return !stillInInit;
}

#endif  // TEST_INTEGRATION_HELPERS_H
