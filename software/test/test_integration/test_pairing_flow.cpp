#include "test_helpers.h"

// Layer 2: Pairing Flow (runs in Phase 1)
//
// Tests the device's ability to detect unpaired state, enter the pairing
// screen, and transition out when pairing is completed server-side.
//
// Depends on:
// - Phase 0 completing and calling triggerUnpairing() before restart
// - Phase 1 init sees unpaired state during preflight
//
// After these tests complete, the device is PAIRED and ready for Layer 3+.
// triggerPairing() is defined in test_helpers.h

// --- Test 1: Device detects unpaired state ---

static void test_device_detects_unpaired() {
    // Wait for preflight to complete
    waitForPreflight();

    Serial.printf("[INFO] dashboardState.isPaired: %s\n",
                  dashboardState.isPaired ? "true" : "false");

    TEST_ASSERT_FALSE_MESSAGE(
        dashboardState.isPaired,
        "Device should detect unpaired state (seed data has ownerId = NULL)");
}

// --- Test 2: State machine enters pairing state ---

static void test_enters_pairing_state() {
    // Since device is unpaired, it should transition to pairing state
    // after preflight completes.
    bool reachedPairing =
        waitForState([]() { return stateMachine->is("pairing"_s); }, "pairing",
                     20000);

    TEST_ASSERT_TRUE_MESSAGE(
        reachedPairing,
        "State machine should enter 'pairing' state when device is unpaired");
}

// --- Test 3: Pairing screen is displayed ---

static void test_pairing_screen_displayed() {
    // Verify we're showing the pairing page (has QR code/trainer ID)
    TEST_ASSERT_TRUE_MESSAGE(stateMachine->is("pairing"_s),
                             "Should be in pairing state");

    // The pairingPage displays trainerId - verify it's non-empty
    TEST_ASSERT_GREATER_THAN_MESSAGE(
        0, (int)trainerId.length(),
        "trainerId should be displayed on pairing screen");

    Serial.printf("[INFO] Pairing screen active. TrainerId: %s\n",
                  trainerId.c_str());
}

// --- Test 4: Trigger pairing via test endpoint ---

static void test_trigger_pairing_endpoint() {
    // Suspend background polling to prevent concurrent SSL allocations
    suspendCheckIfPairedTask();

    int httpCode = triggerPairing();

    // Let heap settle before resuming background task
    vTaskDelay(200 / portTICK_PERIOD_MS);
    resumeCheckIfPairedTask();

    TEST_ASSERT_EQUAL_MESSAGE(200, httpCode,
                              "POST to /test-pair should return 200. "
                              "404 = endpoint not deployed. "
                              "403 = running against production (blocked). "
                              "500 = database error.");
}

// --- Test 5: Device detects pairing completed ---

static void test_detects_pairing_completed() {
    // checkIfPairedTask polls every 2 seconds.
    // Wait for it to detect the pairing change.
    bool exitedPairing =
        waitForState([]() { return !stateMachine->is("pairing"_s); },
                     "NOT pairing", 10000);

    TEST_ASSERT_TRUE_MESSAGE(
        exitedPairing,
        "Device should exit pairing state after /test-pair sets ownerId "
        "(checkIfPairedTask polls every 2s)");

    Serial.printf("[INFO] dashboardState.isPaired after trigger: %s\n",
                  dashboardState.isPaired ? "true" : "false");

    TEST_ASSERT_TRUE_MESSAGE(
        dashboardState.isPaired,
        "dashboardState.isPaired should be true after pairing");
}

// --- Test 6: Transitions to play.preflight ---

static void test_transitions_to_play_preflight() {
    bool reachedPlayFlow = waitForState(
        []() {
            return stateMachine->is("play.preflight"_s) ||
                   stateMachine->is("play.fetchSettings"_s) ||
                   stateMachine->is("play.calibration.min"_s);
        },
        "play.preflight or play.fetchSettings or play.calibration.min", 15000);

    TEST_ASSERT_TRUE_MESSAGE(
        reachedPlayFlow,
        "After pairing, state machine should advance to play flow");
}

// --- Registration ---

void register_pairing_flow_tests() {
    RUN_TEST(test_device_detects_unpaired);
    RUN_TEST(test_enters_pairing_state);
    RUN_TEST(test_pairing_screen_displayed);
    RUN_TEST(test_trigger_pairing_endpoint);
    RUN_TEST(test_detects_pairing_completed);
    RUN_TEST(test_transitions_to_play_preflight);
}
