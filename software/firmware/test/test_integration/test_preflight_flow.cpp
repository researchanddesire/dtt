#include "test_helpers.h"

// --- Test 1: Health check passes ---

static void test_health_check_passes() {
    waitForPreflight();

    Serial.printf("[INFO] healthCheckPassed: %s\n",
                  healthCheckPassed ? "true" : "false");

    TEST_ASSERT_TRUE_MESSAGE(
        healthCheckPassed,
        "Health check should pass (mock server returns 200 for /health-check)");
}

// --- Test 2: Device is paired ---

static void test_is_paired() {
    Serial.printf("[INFO] dashboardState.isPaired: %s\n",
                  dashboardState.isPaired ? "true" : "false");

    TEST_ASSERT_TRUE_MESSAGE(
        dashboardState.isPaired,
        "Device should be paired (Layer 2 completed pairing via /test-pair)");
}

// --- Test 3: Preflight completes ---

static void test_preflight_completes() {
    Serial.printf("[INFO] dashboardState.preflightPending: %s\n",
                  dashboardState.preflightPending ? "true" : "false");

    TEST_ASSERT_FALSE_MESSAGE(
        dashboardState.preflightPending,
        "Preflight should complete within 20s (preflightPending = false)");
}

// --- Test 4: No update available ---

static void test_no_update_available() {
    Serial.printf("[INFO] dashboardState.hasUpdate: %s\n",
                  dashboardState.hasUpdate ? "true" : "false");

    TEST_ASSERT_FALSE_MESSAGE(
        dashboardState.hasUpdate,
        "hasUpdate should be false (NO_UPDATE build flag is set)");
}

// --- Test 5: State machine advances past init after a button event ---

static void test_state_machine_advances_past_init() {
    // init.idle has a timeout that auto-advances to init.preflight.
    // If Layer 1 tests took long enough, the timeout may have already fired.
    if (stateMachine->is("init.idle"_s)) {
        bool exited = pressButtonAndWaitForExit(
            []() { return stateMachine->is("init.idle"_s); },
            "init.idle");

        TEST_ASSERT_TRUE_MESSAGE(
            exited,
            "State machine should have left init.idle after button event");
    } else {
        Serial.println(
            "[INFO] init.idle already exited (timeout auto-advanced) — "
            "skipping button prompt");
    }

    // Give the state machine time to settle through preflight transitions
    vTaskDelay(pdMS_TO_TICKS(3000));

    bool stillInInit = stateMachine->is("init"_s);
    Serial.printf("[INFO] After advancing: init=%d\n", stillInInit);

    TEST_ASSERT_FALSE_MESSAGE(
        stillInInit,
        "State machine should have advanced past init");
}

// --- Registration ---

void register_preflight_flow_tests() {
    RUN_TEST(test_health_check_passes);
    RUN_TEST(test_is_paired);
    RUN_TEST(test_preflight_completes);
    RUN_TEST(test_no_update_available);
    RUN_TEST(test_state_machine_advances_past_init);
}
