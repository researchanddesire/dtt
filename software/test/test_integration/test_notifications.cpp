#include "test_helpers.h"

// Layer 4: Notifications
//
// Verifies that the init.idle -> init.preflight transition spawns
// notifyTrainingTask, which POSTs to /api/dtt/v2/training-started and
// sets the test observability flags (trainingStartedNotified,
// trainingStartedHttpCode) on a successful 200 response.
//
// Regression context: this notification was silently broken for ~9 months
// after a state-machine refactor in July 2025 dropped the side-effect that
// invokes notifyTrainingTask from the init.idle exit transitions. This test
// catches that exact class of regression — if the / startTask(...) is
// removed from the transitions in machine.h, trainingStartedHttpCode stays
// at -1 and the test fails with a diagnostic pointing at machine.h.
//
// Depends on test_preflight_flow::test_state_machine_advances_past_init
// having driven the device past init.idle (via button press or timeout).

// --- Test 1: notifyTrainingTask fired and POST returned 200 ---

static void test_training_started_notification_fired() {
    // Wait for the HTTP response (any code, not just 200)
    waitForNotifyTrainingTaskComplete(15000);

    Serial.printf("[INFO] trainingStartedHttpCode: %d\n",
                  trainingStartedHttpCode);
    Serial.printf("[INFO] trainingStartedNotified: %s\n",
                  trainingStartedNotified ? "true" : "false");

    TEST_ASSERT_EQUAL_MESSAGE(
        200, trainingStartedHttpCode,
        "notifyTrainingTask should POST to /training-started and receive "
        "HTTP 200. -1 means the task never ran (regression — check init.idle "
        "exit transitions in machine.h). 404 means the rad-app dev server "
        "doesn't have the v2 route deployed. 400 means the trainerId in "
        "EEPROM is invalid.");

    TEST_ASSERT_TRUE_MESSAGE(
        trainingStartedNotified,
        "trainingStartedNotified should be true after successful POST");
}

// --- Registration ---

void register_notifications_tests() {
    RUN_TEST(test_training_started_notification_fired);
}
