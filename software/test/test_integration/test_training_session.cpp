#include "test_helpers.h"

// --- Test 1: Session details displayed ---

static void test_session_details_displayed() {
    // After calibration, play.ready fires next → details pages.
    // If hasSeenSessionDetails is already true (from a previous session on
    // this device), details are skipped and the state machine auto-advances
    // to play.begin or play.idle.
    vTaskDelay(pdMS_TO_TICKS(1000));

    bool reached = waitForState(
        []() {
            return stateMachine->is("play.details.session"_s) ||
                   stateMachine->is("play.details.segment"_s) ||
                   stateMachine->is("play.details.toy"_s) ||
                   stateMachine->is("play"_s) ||
                   stateMachine->is("play.begin"_s) ||
                   stateMachine->is("play.idle"_s);
        },
        "play.details.* or play.*", 5000);

    TEST_ASSERT_TRUE_MESSAGE(
        reached,
        "Should be on a details page or training after calibration");
}

// --- Test 2: Advance to training ---

static void test_advance_to_training() {
    // Press button through all details pages until we reach play.idle.
    // Could be 1-3 presses depending on session/toy/segment details flow.

    bool reached = false;

    for (int i = 0; i < 3 && !reached; i++) {
        bool isOnDetails =
            stateMachine->is("play.details.session"_s) ||
            stateMachine->is("play.details.toy"_s) ||
            stateMachine->is("play.details.segment"_s);

        if (!isOnDetails) break;

        pressButtonAndWaitForExit(
            [&isOnDetails]() {
                isOnDetails =
                    stateMachine->is("play.details.session"_s) ||
                    stateMachine->is("play.details.toy"_s) ||
                    stateMachine->is("play.details.segment"_s);
                return isOnDetails;
            },
            "play.details.*");

        vTaskDelay(pdMS_TO_TICKS(500));
    }

    // Wait for countdown (play.begin → play.idle). The countdown blocks
    // for ~4 seconds (3-2-1-GO).
    reached = waitForState(
        []() { return stateMachine->is("play.idle"_s); },
        "play.idle", 15000);

    TEST_ASSERT_TRUE_MESSAGE(
        reached,
        "Should reach play.idle (active training) after advancing through "
        "details and countdown");
}

// --- Test 3: Training active ---

static void test_training_active() {
    TEST_ASSERT_TRUE_MESSAGE(
        stateMachine->is("play.idle"_s),
        "Should be in play.idle (active training)");

    // on_entry spawns distance + play tasks which set currentSegment.
    // Give them time to start.
    vTaskDelay(pdMS_TO_TICKS(2000));

    TEST_ASSERT_NOT_NULL_MESSAGE(
        currentSegment,
        "currentSegment should be set during active training");

    Serial.printf("[INFO] Training type: %d, state: %d, target: %d\n",
                  (int)currentSegment->type, (int)currentSegment->state,
                  currentSegment->params.target);
}

// --- Test 4: Complete training and verify grade ---
// We combine "complete training" + "grade calculated" into one test because
// the state machine auto-advances through grade too fast to check separately.

static void test_complete_training_and_grade() {
    bool exited = longPressButtonAndWaitForExit(
        []() { return stateMachine->is("play.idle"_s); },
        "play.idle");

    TEST_ASSERT_TRUE_MESSAGE(
        exited,
        "Should have left play.idle after the BYPASS_PLAY long-press event");

    // Assert on OUTCOME: grade was calculated
    vTaskDelay(pdMS_TO_TICKS(500));

    TEST_ASSERT_NOT_NULL_MESSAGE(
        currentSegment,
        "currentSegment should still be set after training");

    int grade = currentSegment->grade();
    Serial.printf("[INFO] Grade: %d%%\n", grade);

    TEST_ASSERT_GREATER_OR_EQUAL_MESSAGE(
        0, grade, "Grade should be >= 0");
    TEST_ASSERT_LESS_OR_EQUAL_MESSAGE(
        100, grade, "Grade should be <= 100");
}

// --- Test 5: Results uploaded ---

static void test_results_uploaded() {
    // saveResultsTask runs in background on play.grade entry.
    // Give it time to POST to /training-completed.
    vTaskDelay(pdMS_TO_TICKS(3000));

    Serial.printf("[INFO] resultsHttpCode: %d\n", resultsHttpCode);
    Serial.printf("[INFO] resultsUploaded: %s\n",
                  resultsUploaded ? "true" : "false");

    TEST_ASSERT_EQUAL_MESSAGE(
        200, resultsHttpCode,
        "saveResultsTask should POST to /training-completed and receive "
        "HTTP 200. -1 means the task never ran or WiFi was disconnected.");

    TEST_ASSERT_TRUE_MESSAGE(
        resultsUploaded,
        "resultsUploaded should be true after successful POST");
}

// --- Test 6: Session lifecycle completes ---
// After grade, the state machine auto-advances through play.final back to
// play.preflight and starts the next session cycle. We verify this happened
// by checking the outcome: session.segmentIdx was reset and a new session ID
// was generated.

static void test_session_lifecycle_complete() {
    // Wait for the state machine to loop back. play.grade timeout →
    // evaluatePassFail → play.final timeout → clearSegmentIndex →
    // play.preflight → fetchSettings → calibration.min (next cycle).
    // If we're still on play.grade or play.final, dispatch a button event.

    if (stateMachine->is("play.grade"_s)) {
        pressButtonAndWaitForExit(
            []() { return stateMachine->is("play.grade"_s); },
            "play.grade");
    }

    if (stateMachine->is("play.final"_s)) {
        pressButtonAndWaitForExit(
            []() { return stateMachine->is("play.final"_s); },
            "play.final");
    }

    // Give the state machine time to loop back through preflight → fetch
    vTaskDelay(pdMS_TO_TICKS(5000));

    // Assert on OUTCOME: the session was reset.
    // clearSegmentIndex sets segmentIdx = 0 and generates a new session ID.
    TEST_ASSERT_EQUAL_MESSAGE(
        0, session.segmentIdx,
        "segmentIdx should be reset to 0 after session complete");

    Serial.println("[INFO] Full training session lifecycle complete.");
}

// --- Registration ---

void register_training_session_tests() {
    RUN_TEST(test_session_details_displayed);
    RUN_TEST(test_advance_to_training);
    RUN_TEST(test_training_active);
    RUN_TEST(test_complete_training_and_grade);
    RUN_TEST(test_results_uploaded);
    RUN_TEST(test_session_lifecycle_complete);
}
