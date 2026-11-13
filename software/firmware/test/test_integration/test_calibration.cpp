#include "test_helpers.h"

// --- Test 1: Reaches calibration ---

static void test_reaches_calibration() {
    // Layer 4 already confirmed we're in play.calibration.min.
    // Verify it's still true (no unexpected transition).
    TEST_ASSERT_TRUE_MESSAGE(
        stateMachine->is("play.calibration.min"_s),
        "Should be in play.calibration.min (session has no toy calibration)");
}

// --- Test 2: Capture min position (OUTER) ---

static void test_capture_min_position() {
    bool exited = pressButtonAndWaitForExit(
        []() { return stateMachine->is("play.calibration.min"_s); },
        "play.calibration.min");

    TEST_ASSERT_TRUE_MESSAGE(
        exited,
        "Should have left play.calibration.min after button press (timed out)");

    // captureMinPosition holds the reading until the deep position passes
    // the range check, so check the same sensor read directly.
    vTaskDelay(pdMS_TO_TICKS(500));
    const float tipCm = getDistance(100);

    Serial.printf("[INFO] tip reading: %.2f cm\n", tipCm);

    TEST_ASSERT_GREATER_THAN_MESSAGE(0.0f, tipCm, "tip reading should be > 0");
    TEST_ASSERT_LESS_THAN_MESSAGE(
        25.0f, tipCm, "tip reading should be < 25cm (sensor range)");

    TEST_ASSERT_TRUE_MESSAGE(
        stateMachine->is("play.calibration.max"_s),
        "Should have transitioned to play.calibration.max");
}

// --- Test 3: Capture max position (INNER) ---

static void test_capture_max_position() {
    bool exited = pressButtonAndWaitForExit(
        []() { return stateMachine->is("play.calibration.max"_s); },
        "play.calibration.max");

    TEST_ASSERT_TRUE_MESSAGE(
        exited,
        "Should have left play.calibration.max after button press (timed out)");

    // The CI fixture has no mechanical actuator to move the carriage between
    // the two captures, so both read the same distance. The device must
    // reject that zero-width range instead of training on it.
    bool rejected = waitForState(
        []() { return stateMachine->is("play.calibration.invalid"_s); },
        "play.calibration.invalid", 5000);

    TEST_ASSERT_TRUE_MESSAGE(
        rejected,
        "A stationary fixture's zero-width range should be rejected");
    TEST_ASSERT_FALSE_MESSAGE(
        session.isCalibrated,
        "A rejected calibration must not mark the session calibrated");

    // Use a deterministic valid span for the remaining server and lifecycle
    // tests, then keep it from the rejection page as a user keeps a previous
    // calibration. Production calibration uses the two physical positions.
    constexpr float FIXTURE_INNER_CM = 2.0f;
    constexpr float FIXTURE_OUTER_CM = 12.0f;
    session.calibratedMinPosition = FIXTURE_OUTER_CM;
    session.calibratedMaxPosition = FIXTURE_INNER_CM;
    session.isCalibrated = true;

    for (auto& segment : session.segments) {
        segment.params.startPosition = FIXTURE_OUTER_CM;
        segment.params.endPosition = FIXTURE_INNER_CM;
    }

    calibrationHttpCode = -1;
    calibrationUploaded = false;
    sendCalibrationToBackend(FIXTURE_INNER_CM, FIXTURE_OUTER_CM);

    TEST_ASSERT_TRUE_MESSAGE(
        longPressButtonAndWaitForExit(
            []() { return stateMachine->is("play.calibration.invalid"_s); },
            "play.calibration.invalid"),
        "Holding the button should keep the existing calibration");
}

// --- Test 4: Calibration applied to segments ---

static void test_calibration_applied_to_segments() {
    for (size_t i = 0; i < session.segments.size(); i++) {
        const auto& seg = session.segments[i];

        Serial.printf("[INFO] segment[%d] startPos=%.2f, endPos=%.2f\n",
                      i, seg.params.startPosition, seg.params.endPosition);

        TEST_ASSERT_FLOAT_WITHIN_MESSAGE(
            0.01f, session.calibratedMinPosition, seg.params.startPosition,
            "Segment startPosition should match calibratedMinPosition");
        TEST_ASSERT_FLOAT_WITHIN_MESSAGE(
            0.01f, session.calibratedMaxPosition, seg.params.endPosition,
            "Segment endPosition should match calibratedMaxPosition");
    }
}

// --- Test 5: Calibration uploaded to server ---

static void test_calibration_uploaded() {
    // sendCalibrationToBackend runs async. Give it time to complete.
    vTaskDelay(pdMS_TO_TICKS(3000));

    Serial.printf("[INFO] calibrationHttpCode: %d\n", calibrationHttpCode);
    Serial.printf("[INFO] calibrationUploaded: %s\n",
                  calibrationUploaded ? "true" : "false");

    TEST_ASSERT_EQUAL_MESSAGE(
        200, calibrationHttpCode,
        "sendCalibrationToBackend should POST to /calibrate-toy and receive "
        "HTTP 200. -1 means the function never ran or WiFi was disconnected.");

    TEST_ASSERT_TRUE_MESSAGE(
        calibrationUploaded,
        "calibrationUploaded should be true after successful POST");

    // Verify state machine advanced past calibration
    bool reached = waitForState(
        []() {
            return stateMachine->is("play.details.session"_s) ||
                   stateMachine->is("play.details.segment"_s) ||
                   stateMachine->is("play.ready"_s);
        },
        "play.details.* or play.ready", 5000);

    TEST_ASSERT_TRUE_MESSAGE(
        reached,
        "State machine should have advanced past calibration");

    Serial.println("[INFO] Calibration complete — device is ready to train.");
}

// --- Registration ---

void register_calibration_tests() {
    RUN_TEST(test_reaches_calibration);
    RUN_TEST(test_capture_min_position);
    RUN_TEST(test_capture_max_position);
    RUN_TEST(test_calibration_applied_to_segments);
    RUN_TEST(test_calibration_uploaded);
}
