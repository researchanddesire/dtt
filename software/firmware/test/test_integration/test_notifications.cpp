#include "test_helpers.h"

// A prepared/prefetched session is not training. Only genuine play attempts
// the best-effort notification; a missing/ambiguous POST is not retried.
static void test_preflight_does_not_notify_training() {
    TEST_ASSERT_EQUAL_MESSAGE(-1, trainingStartedHttpCode,
        "Preflight/settings preparation must not emit a training notification");
    TEST_ASSERT_FALSE_MESSAGE(trainingStartedNotified,
        "Training must remain unannounced until actual play");
}

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
        "HTTP 200. -1 means the actual-play notification task never ran (check "
        "the active worker notification reservation). 404 means the dev server "
        "doesn't have the v2 route deployed. 400 means the trainerId in "
        "EEPROM is invalid.");

    TEST_ASSERT_TRUE_MESSAGE(
        trainingStartedNotified,
        "trainingStartedNotified should be true after successful POST");
}

// Phase 0 exercises paired preflight without play.
void register_notifications_idle_tests() {
    RUN_TEST(test_preflight_does_not_notify_training);
}

// Phase 1 has entered actual play before this registration.

void register_notifications_tests() {
    RUN_TEST(test_training_started_notification_fired);
}
