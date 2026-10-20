#include "test_helpers.h"

#include "esp_system.h"

void setUp(void) {}
void tearDown(void) {}

extern void register_hardware_init_tests();
extern void register_pairing_flow_tests();
extern void register_preflight_flow_tests();
extern void register_notifications_tests();
extern void register_settings_fetch_tests();
extern void register_calibration_tests();
extern void register_training_session_tests();
extern void register_error_path_tests();

void setup() {
    Serial.begin(115200);
    delay(1000);

    // Detect a crash only after the suite recorded an in-progress phase. A
    // production image may itself have left ESP_RST_PANIC as the reset reason;
    // treating that as a test crash makes the first clean hardware run
    // impossible without erasing the provisioned device.
    esp_reset_reason_t reason = esp_reset_reason();
    int phase = getTestPhase();
    if (reason == ESP_RST_PANIC && phase != 0) {
        Serial.println("\n");
        Serial.println("========================================");
        Serial.println("!!! CRASH DETECTED FROM PREVIOUS RUN !!!");
        Serial.println("========================================");
        Serial.println("The device crashed during the previous test run.");
        Serial.println("Check the serial output above for the backtrace.");
        Serial.println("Scroll up to see which test was running when it crashed.");
        Serial.println("");
        // Unity-format output so PlatformIO recognizes the failure
        Serial.println("test/test_integration/test_main.cpp:1:test_crash_detection:FAIL: Device crashed in previous test run (ESP_RST_PANIC)");
        Serial.println("");
        Serial.println("-----------------------");
        Serial.println("1 Tests 1 Failures 0 Ignored");
        Serial.println("FAIL");
        Serial.flush();
        // Halt to prevent infinite reboot loop
        while (1) { delay(1000); }
    }

    // Clear phase on fresh flash, preserve on ESP.restart()
    if (reason != ESP_RST_SW) {
        Serial.println("[TEST] Fresh flash detected, clearing test phase");
        clearTestPhase();
    }

    phase = getTestPhase();
    Serial.printf("\n[TEST] ===== Phase %d =====\n", phase);

    UNITY_BEGIN();

    if (phase == 0) {
        // Phase 0: Device PAIRED, test notification
        // Ensure paired state before init (notification fires on state machine start)
        initHardwareBeforeStateMachine();
        waitForWifi();
        triggerPairing();  // Guarantee paired state
        initStateMachinePhase();  // Notification fires with valid user

        register_hardware_init_tests();
        advancePastInit();  // Trigger init.idle → init.preflight (fires notification)
        register_notifications_tests();  // Should get 200

        // NOTE: Do NOT call UNITY_END() here — PlatformIO exits on seeing the
        // summary line. Phase 1 will call UNITY_END() with the combined count.

        // Prepare for phase 1: unpair and restart
        Serial.println("[TEST] Phase 0 complete. Unpairing and restarting...");
        triggerUnpairing();  // Set ownerId = NULL for phase 1
        setTestPhase(1);
        // Wait for any in-flight HTTP tasks to complete before restart
        waitForNotifyTrainingTaskComplete(5000);
        delay(500);
        ESP.restart();

    } else if (phase == 1) {
        // Phase 1: Device UNPAIRED, test pairing flow + everything else
        initHardwareBeforeStateMachine();
        waitForWifi();
        triggerUnpairing();  // Guarantee unpaired state for pairing tests
        initStateMachinePhase();  // Preflight sees unpaired

        register_pairing_flow_tests();      // Pairs device mid-test
        register_preflight_flow_tests();
        register_settings_fetch_tests();
        register_calibration_tests();
        register_training_session_tests();
        register_error_path_tests();

        // Restore paired state for next run (self-resetting)
        triggerPairing();
        clearTestPhase();
        Serial.println("[TEST] All phases complete!");

        UNITY_END();
    }
}

void loop() {}
