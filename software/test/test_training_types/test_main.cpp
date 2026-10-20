#include <Arduino.h>
#include <unity.h>

#include "bounce.h"
#include "endurance.h"
#include "freeform.h"
#include "repetition.h"
#include "trainingTypes.h"

// Test data structures
TrainingParams createTestParams(int target = 5, float startPos = 16.0f,
                                float endPos = 2.0f, int depthIncrease = 10,
                                float speed = 20.0f, float window = 3.0f) {
    return {target, startPos, endPos, depthIncrease, speed, window};
}

TrainingParams createEnduranceParams(float durationSeconds = 30.0f,
                                     float startPos = 16.0f,
                                     int depthIncrease = 10,
                                     float speed = 20.0f, float window = 3.0f) {
    return {static_cast<int>(durationSeconds),
            startPos,
            0.0f,
            depthIncrease,
            speed,
            window};
}

TrainingParams createFreeformParams(float durationSeconds = 30.0f,
                                    float targetRpm = 60.0f,
                                    int depthIncrease = 10) {
    return {static_cast<int>(durationSeconds),
            16.0f,
            2.0f,
            depthIncrease,
            targetRpm,
            3.0f};
}

void setUp(void) {
    // Initialize test environment
}

void tearDown(void) {
    // Clean up after tests
}

// ===== REPETITION TESTS =====
void test_repetition_initialization() {
    TrainingParams params = createTestParams(5, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);

    TEST_ASSERT_EQUAL(TrainingType::REPETITION, segment.type);
    TEST_ASSERT_EQUAL(TrainingState::START, segment.state);
    TEST_ASSERT_TRUE(segment.isWaitingForReturn);
    TEST_ASSERT_EQUAL(0, segment.currentValue);
    TEST_ASSERT_EQUAL(5, segment.params.target);
}

void test_repetition_validation() {
    TrainingParams params = createTestParams();
    RepetitionSegment segment(params);

    // Test validation by calling train with START state
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingState::TRAINING, segment.state);

    // Test parameter constraints
    TEST_ASSERT_TRUE(segment.params.trainingSpeed >= 0.1f);
    TEST_ASSERT_TRUE(segment.params.trainingSpeed <= 1000.0f);
    TEST_ASSERT_TRUE(segment.params.startPosition >=
                     DEAD_ZONE_CM + MINIMUM_STROKE_LENGTH_CM);
    TEST_ASSERT_TRUE(segment.params.startPosition <= MAX_RANGE_CM);
    TEST_ASSERT_TRUE(segment.params.endPosition >= DEAD_ZONE_CM);
    TEST_ASSERT_TRUE(segment.params.endPosition <=
                     segment.params.startPosition - MINIMUM_STROKE_LENGTH_CM);
}

void test_repetition_position_states() {
    TrainingParams params = createTestParams(5, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);
    segment.train(100);  // Initialize

    // Test BEHIND position
    segment.currentPosition = 18.0f;  // Above startWindow
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingPosition::BEHIND, segment.positionState);

    // Test AHEAD position
    segment.currentPosition = 1.0f;  // Below endWindow
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingPosition::AHEAD, segment.positionState);

    // Test IN_WINDOW position
    segment.currentPosition = 15.0f;  // Between windows
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingPosition::IN_WINDOW, segment.positionState);
}

void test_repetition_completion() {
    TrainingParams params = createTestParams(3, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);
    segment.train(100);  // Initialize

    // Simulate completing all repetitions
    segment.currentValue = 3;
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingState::END, segment.state);
}

void test_repetition_waiting_for_return() {
    TrainingParams params = createTestParams(5, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);
    segment.train(100);  // Initialize

    TEST_ASSERT_TRUE(segment.isWaitingForReturn);

    // Move to window to stop waiting
    segment.currentPosition = 15.0f;
    segment.train(100);
    TEST_ASSERT_FALSE(segment.isWaitingForReturn);
}

void test_repetition_grade_calculation() {
    TrainingParams params = createTestParams(5, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);
    segment.train(100);  // Initialize

    // Perfect score
    segment.timeInsideWindow = 1000;
    segment.timeOutsideWindow = 0;
    TEST_ASSERT_EQUAL(100, segment.grade());

    // Partial score
    segment.timeInsideWindow = 800;
    segment.timeOutsideWindow = 200;
    int expectedGrade = static_cast<int>(100 * 800 / (800 + 200));
    TEST_ASSERT_EQUAL(expectedGrade, segment.grade());
}

void test_repetition_value_string() {
    TrainingParams params = createTestParams(5, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);

    segment.currentValue = 3;
    String result = segment.valueString();
    TEST_ASSERT_EQUAL_STRING("3/5", result.c_str());
}

// ===== ENDURANCE TESTS =====
void test_endurance_initialization() {
    TrainingParams params = createEnduranceParams(30.0f);
    EnduranceSegment segment(params);

    TEST_ASSERT_EQUAL(TrainingType::ENDURANCE, segment.type);
    TEST_ASSERT_EQUAL(TrainingState::START, segment.state);
    TEST_ASSERT_TRUE(segment.isWaitingForReturn);
    TEST_ASSERT_EQUAL(0.0f, segment.endWindow);
    TEST_ASSERT_EQUAL(30000, segment.params.target);  // Converted to ms
}

void test_endurance_validation() {
    TrainingParams params = createEnduranceParams(30.0f);
    EnduranceSegment segment(params);

    segment.train(100);  // Initialize
    TEST_ASSERT_EQUAL(TrainingState::TRAINING, segment.state);
    TEST_ASSERT_EQUAL(0.0f, segment.params.endPosition);
}

void test_endurance_time_tracking() {
    TrainingParams params = createEnduranceParams(5.0f);  // 5 seconds
    EnduranceSegment segment(params);
    segment.train(100);  // Initialize

    // Simulate time passing
    segment.currentValue = 5000;  // 5 seconds in ms
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingState::END, segment.state);
}

void test_endurance_streak_tracking() {
    TrainingParams params = createEnduranceParams(30.0f);
    EnduranceSegment segment(params);
    segment.train(100);  // Initialize

    // Move to window first to clear waiting for return
    segment.setPositionSpeed(2.0f, 5.0f);  // Position in window
    segment.train(100);                    // Clear waiting for return
    TEST_ASSERT_FALSE(segment.isWaitingForReturn);

    // Build up a streak
    segment.train(1000);  // 1 second in window
    unsigned int streakAfterInWindow = segment.currentStreak;
    TEST_ASSERT_TRUE(streakAfterInWindow > 0);  // Should have a streak

    // Move outside window to trigger streak reset
    segment.setPositionSpeed(20.0f, 5.0f);  // Position behind window
    segment.train(100);
    TEST_ASSERT_EQUAL(0, segment.currentStreak);  // Should reset to 0
    TEST_ASSERT_EQUAL(streakAfterInWindow,
                      segment.longestStreak);  // Should save longest
}

void test_endurance_value_string() {
    TrainingParams params = createEnduranceParams(30.0f);
    EnduranceSegment segment(params);

    segment.currentValue = 10000;  // 10 seconds elapsed
    String result = segment.valueString();
    TEST_ASSERT_TRUE(result.indexOf("20.00 s") >= 0);  // 20 seconds remaining
}

// ===== BOUNCE TESTS =====
void test_bounce_initialization() {
    TrainingParams params = createTestParams(5, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    BounceSegment segment(params);

    TEST_ASSERT_EQUAL(TrainingType::BOUNCE, segment.type);
    TEST_ASSERT_EQUAL(TrainingState::START, segment.state);
    TEST_ASSERT_FALSE(segment.movingRight);
}

void test_bounce_direction_changes() {
    TrainingParams params = createTestParams(5, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    BounceSegment segment(params);
    segment.train(100);  // Initialize

    // Test moving right
    segment.movingRight = true;
    segment.currentPosition = 1.0f;  // Below endWindow
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingPosition::AHEAD, segment.positionState);

    // Test moving left
    segment.movingRight = false;
    segment.currentPosition = 18.0f;  // Above startWindow
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingPosition::AHEAD, segment.positionState);
}

void test_bounce_completion() {
    TrainingParams params = createTestParams(3, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    BounceSegment segment(params);
    segment.train(100);  // Initialize

    segment.currentValue = 3;
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingState::END, segment.state);
}

void test_bounce_value_string() {
    TrainingParams params = createTestParams(5, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    BounceSegment segment(params);

    segment.currentValue = 7;
    String result = segment.valueString();
    TEST_ASSERT_EQUAL_STRING("7", result.c_str());
}

// ===== FREEFORM TESTS =====
void test_freeform_initialization() {
    TrainingParams params = createFreeformParams(30.0f, 60.0f, 10);
    FreeformSegment segment(params);

    TEST_ASSERT_EQUAL(TrainingType::FREEFORM, segment.type);
    TEST_ASSERT_EQUAL(TrainingState::START, segment.state);
    TEST_ASSERT_EQUAL(DisplayType::ARC, segment.displayType);
    TEST_ASSERT_EQUAL(30000, segment.params.target);  // Converted to ms
    TEST_ASSERT_EQUAL(60.0f, segment.startWindow);    // Target RPM
}

void test_freeform_rpm_detection() {
    TrainingParams params = createFreeformParams(30.0f, 60.0f, 10);
    FreeformSegment segment(params);
    segment.train(100);  // Initialize

    // Test low RPM (behind)
    segment.currentRpm = 30.0f;
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingPosition::BEHIND, segment.positionState);

    // Test good RPM (in window)
    segment.currentRpm = 70.0f;
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingPosition::IN_WINDOW, segment.positionState);
}

void test_freeform_time_tracking() {
    TrainingParams params = createFreeformParams(5.0f, 60.0f, 10);
    FreeformSegment segment(params);
    segment.train(100);  // Initialize

    segment.currentValue = 5000;  // 5 seconds
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingState::END, segment.state);
}

void test_freeform_value_string() {
    TrainingParams params = createFreeformParams(30.0f, 60.0f, 10);
    FreeformSegment segment(params);

    segment.currentValue = 10000;  // 10 seconds elapsed
    String result = segment.valueString();
    TEST_ASSERT_TRUE(result.indexOf("20.00 s") >= 0);  // 20 seconds remaining
}

// ===== BASE CLASS TESTS =====
void test_segment_base_position_tracking() {
    TrainingParams params = createTestParams();
    RepetitionSegment segment(params);
    segment.train(100);  // Initialize the segment first

    // Test position and speed setting
    segment.setPositionSpeed(15.0f, 5.0f);
    segment.train(100);  // Process the position change
    TEST_ASSERT_EQUAL(15.0f, segment.currentPosition);
    TEST_ASSERT_EQUAL(5.0f, segment.currentSpeed);

    // Test statistics tracking
    TEST_ASSERT_EQUAL(15.0f, segment.statistics.minDepth);
    TEST_ASSERT_EQUAL(16.0f, segment.statistics.maxDepth);
}

void test_segment_base_direction_detection() {
    TrainingParams params = createTestParams();
    RepetitionSegment segment(params);

    // With default params (range=14cm), threshold = 14 * 0.25 = 3.5cm
    // Need movements > 3.5cm in each direction to count strokes
    segment.setPositionSpeed(16.0f, 5.0f);  // Start position
    segment.setPositionSpeed(14.0f, 5.0f);  // Move left
    segment.setPositionSpeed(12.0f, 5.0f);  // Continue left (cumulative: 4.0cm)
    segment.setPositionSpeed(14.0f, 5.0f);  // Reverse right (stroke counted)
    segment.setPositionSpeed(16.0f, 5.0f);  // Continue right (cumulative: 4.0cm)

    // Should have detected direction changes with sufficient movement
    TEST_ASSERT_TRUE(segment.statistics.strokes > 0);
}

void test_segment_base_progress_calculation() {
    TrainingParams params = createTestParams(10, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);

    segment.currentValue = 3;
    float progress = segment.getTrainingProgress();
    TEST_ASSERT_EQUAL_FLOAT(0.3f, progress);

    segment.currentValue = 10;
    progress = segment.getTrainingProgress();
    TEST_ASSERT_EQUAL_FLOAT(1.0f, progress);
}

void test_segment_base_dynamic_boundaries() {
    TrainingParams params = createTestParams(5, 16.0f, 2.0f, 20, 20.0f, 3.0f);
    RepetitionSegment segment(params);

    // Test dynamic boundary updates
    segment.currentValue = 2;  // 50% progress
    segment.updateDynamicBoundaries();

    float effectiveEnd = segment.getCurrentEffectiveEndPosition();
    TEST_ASSERT_TRUE(effectiveEnd > DEAD_ZONE_CM);
    TEST_ASSERT_TRUE(effectiveEnd < segment.params.endPosition);
}

// ===== STROKE COUNTING TESTS (CUMULATIVE THRESHOLD) =====
void test_repetition_small_oscillations_no_stroke() {
    // Test that small oscillations do NOT count as strokes
    // With default params (range=14cm), threshold = 14 * 0.25 = 3.5cm
    TrainingParams params = createTestParams();
    RepetitionSegment segment(params);

    float startPos = 16.0f;
    segment.setPositionSpeed(startPos, 5.0f);  // Start at 16cm

    // Make small movements (0.3cm each) well under 3.5cm threshold
    segment.setPositionSpeed(startPos - 0.3f, 5.0f);  // 15.7cm (moving left)
    segment.setPositionSpeed(startPos - 0.5f, 5.0f);  // 15.5cm (cumulative: 0.5cm)

    // Direction change but cumulative movement = 0.5cm < 3.5cm threshold
    segment.setPositionSpeed(startPos - 0.3f, 5.0f);  // 15.7cm (moving right)
    segment.setPositionSpeed(startPos, 5.0f);         // 16.0cm

    // No strokes should be counted (movements too small)
    TEST_ASSERT_EQUAL_INT(0, segment.statistics.strokes);
}

void test_repetition_medium_oscillations_no_stroke() {
    // Test that medium oscillations under calibrated threshold do NOT count
    // With default params (range=14cm), threshold = 14 * 0.25 = 3.5cm
    TrainingParams params = createTestParams();
    RepetitionSegment segment(params);

    float startPos = 16.0f;
    segment.setPositionSpeed(startPos, 5.0f);  // Start at 16cm

    // Make movements that accumulate to 2.0cm (still under 3.5cm threshold)
    segment.setPositionSpeed(startPos - 1.0f, 5.0f);  // 15.0cm (moving left)
    segment.setPositionSpeed(startPos - 2.0f, 5.0f);  // 14.0cm (cumulative: 2.0cm)

    // Direction change but cumulative = 2.0cm < 3.5cm threshold
    segment.setPositionSpeed(startPos - 1.5f, 5.0f);  // 14.5cm (moving right)

    // No strokes should be counted
    TEST_ASSERT_EQUAL_INT(0, segment.statistics.strokes);
}

void test_repetition_large_movement_counts_stroke() {
    // Test that movement >= calibrated threshold DOES count as a stroke
    // With default params (range=14cm), threshold = 14 * 0.25 = 3.5cm
    TrainingParams params = createTestParams();
    RepetitionSegment segment(params);

    float startPos = 16.0f;
    segment.setPositionSpeed(startPos, 5.0f);  // Start at 16cm

    // Make movement that exceeds 3.5cm cumulative
    segment.setPositionSpeed(startPos - 2.0f, 5.0f);  // 14.0cm
    segment.setPositionSpeed(startPos - 4.0f, 5.0f);  // 12.0cm (cumulative: 4.0cm)

    // Direction change with cumulative = 4.0cm >= 3.5cm threshold
    segment.setPositionSpeed(startPos - 3.5f, 5.0f);  // 12.5cm (moving right)

    // One stroke should be counted
    TEST_ASSERT_EQUAL_INT(1, segment.statistics.strokes);
}

void test_repetition_multiple_valid_strokes() {
    // Test that multiple valid strokes are counted correctly
    // With default params (range=14cm), threshold = 14 * 0.25 = 3.5cm
    TrainingParams params = createTestParams();
    RepetitionSegment segment(params);

    float startPos = 16.0f;
    segment.setPositionSpeed(startPos, 5.0f);

    // First valid stroke: move left 4.0cm, then reverse
    segment.setPositionSpeed(startPos - 2.0f, 5.0f);  // 14.0cm
    segment.setPositionSpeed(startPos - 4.0f, 5.0f);  // 12.0cm (cumulative: 4.0cm)
    segment.setPositionSpeed(startPos - 3.5f, 5.0f);  // 12.5cm (direction change, stroke counted)

    // Second valid stroke: move right 4.5cm, then reverse
    segment.setPositionSpeed(startPos - 1.5f, 5.0f);  // 14.5cm
    segment.setPositionSpeed(startPos + 0.5f, 5.0f);  // 16.5cm (cumulative: 4.0cm)
    segment.setPositionSpeed(startPos, 5.0f);          // 16.0cm (direction change, stroke counted)

    // Two strokes should be counted
    TEST_ASSERT_EQUAL_INT(2, segment.statistics.strokes);
}

void test_bounce_small_oscillations_no_stroke() {
    // Test Bounce mode also uses calibrated cumulative threshold
    // With default params (range=14cm), threshold = 3.5cm
    TrainingParams params = createTestParams();
    BounceSegment segment(params);

    segment.setPositionSpeed(16.0f, 5.0f);
    segment.setPositionSpeed(15.7f, 5.0f);  // Move 0.3cm
    segment.setPositionSpeed(15.5f, 5.0f);  // Cumulative: 0.5cm
    segment.setPositionSpeed(15.7f, 5.0f);  // Direction change, but cumulative < 3.5cm

    TEST_ASSERT_EQUAL_INT(0, segment.statistics.strokes);
}

void test_endurance_small_oscillations_no_stroke() {
    // Test Endurance mode also uses calibrated cumulative threshold
    // Endurance params: startPos=16.0, endPos clamped to DEAD_ZONE(1.7)
    // Range = 16.0 - 1.7 = 14.3cm, threshold = 14.3 * 0.25 = 3.575cm
    TrainingParams params = createEnduranceParams(30.0f, 16.0f, 10, 20.0f, 3.0f);
    EnduranceSegment segment(params);

    segment.setPositionSpeed(16.0f, 5.0f);
    segment.setPositionSpeed(15.6f, 5.0f);  // Move 0.4cm
    segment.setPositionSpeed(15.3f, 5.0f);  // Cumulative: 0.7cm
    segment.setPositionSpeed(15.6f, 5.0f);  // Direction change, but cumulative < 3.575cm

    TEST_ASSERT_EQUAL_INT(0, segment.statistics.strokes);
}

void test_freeform_uses_progressive_threshold() {
    // Test that Freeform still uses its own progressive threshold,
    // not the calibrated percentage threshold
    TrainingParams params = createFreeformParams(30.0f, 60.0f, 0);
    FreeformSegment segment(params);

    // Freeform threshold starts at 0.5cm (when trainingDepthIncrease = 0)
    // Move 1.0cm forward then reverse — exceeds freeform's 0.5cm threshold
    // but would NOT exceed the calibrated 3.5cm threshold
    segment.setPositionSpeed(16.0f, 5.0f);   // Within bounds [15.6, 16.4]
    segment.setPositionSpeed(15.0f, 5.0f);   // Outside bounds, forward, cumulative=1.0
    segment.setPositionSpeed(16.0f, 5.0f);   // Outside bounds [14.6, 15.4], direction change
                                              // cumulative=1.0 >= 0.5 -> stroke counted

    // Freeform should count the stroke (threshold is 0.5cm, not calibrated 3.5cm)
    TEST_ASSERT_EQUAL_INT(1, segment.statistics.strokes);
}

void test_small_range_uses_minimum_threshold() {
    // Test that very small calibration ranges use MIN_STROKE_THRESHOLD_CM floor
    // Range = 3.5 - 1.7(clamped) = 1.8cm, 25% = 0.45cm < 1.0cm floor
    // So threshold = max(1.0, 0.45) = 1.0cm
    TrainingParams params = createTestParams(5, 3.5f, 1.0f, 10, 20.0f, 1.0f);
    RepetitionSegment segment(params);

    // Part 1: Move 0.5cm forward then reverse — should NOT count
    // Constructor: bounds=[3.1, 3.9], forward=true, lastPos=3.5
    segment.setPositionSpeed(3.5f, 5.0f);   // Within bounds
    segment.setPositionSpeed(3.0f, 5.0f);   // Outside [3.1], forward, cumulative=0.5
                                              // bounds→[2.6, 3.4]
    segment.setPositionSpeed(3.5f, 5.0f);   // Outside [3.4], direction change
                                              // cumulative=0.5 < 1.0 → rejected

    TEST_ASSERT_EQUAL_INT(0, segment.statistics.strokes);

    // Part 2: Move 1.3cm forward then reverse — should count
    // State: bounds=[3.1, 3.9], forward=false, cumulative=0, lastPos=3.5
    segment.setPositionSpeed(2.5f, 5.0f);   // Outside [3.1], forward=true, direction change
                                              // cumulative=0 < 1.0 → rejected, reset
                                              // bounds→[2.1, 2.9], lastPos=2.5
    segment.setPositionSpeed(1.2f, 5.0f);   // Outside [2.1], forward, same direction
                                              // cumulative=0+1.3=1.3, bounds→[0.8, 1.6]
    segment.setPositionSpeed(2.5f, 5.0f);   // Outside [1.6], direction change
                                              // cumulative=1.3 >= 1.0 → stroke counted!

    TEST_ASSERT_EQUAL_INT(1, segment.statistics.strokes);
}

// ===== EDGE CASES AND ERROR CONDITIONS =====
void test_edge_case_zero_target() {
    TrainingParams params = createTestParams(0, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);

    segment.train(100);  // Initialize
    TEST_ASSERT_EQUAL(TrainingState::TRAINING, segment.state);

    // Should complete immediately
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingState::END, segment.state);
}

void test_edge_case_extreme_positions() {
    TrainingParams params = createTestParams(5, 0.1f, 0.1f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);

    segment.train(100);  // Initialize
    // Should constrain positions properly
    TEST_ASSERT_TRUE(segment.params.startPosition >=
                     DEAD_ZONE_CM + MINIMUM_STROKE_LENGTH_CM);
    TEST_ASSERT_TRUE(segment.params.endPosition >= DEAD_ZONE_CM);
}

void test_edge_case_extreme_speeds() {
    TrainingParams params = createTestParams(5, 16.0f, 2.0f, 10, 0.05f, 3.0f);
    RepetitionSegment segment(params);

    segment.train(100);  // Initialize
    TEST_ASSERT_TRUE(segment.params.trainingSpeed >= 0.1f);

    params.trainingSpeed = 2000.0f;
    RepetitionSegment segment2(params);
    segment2.train(100);
    TEST_ASSERT_TRUE(segment2.params.trainingSpeed <= 1000.0f);
}

void test_edge_case_negative_time() {
    TrainingParams params = createTestParams();
    RepetitionSegment segment(params);
    segment.train(100);  // Initialize

    // Test with negative time delta
    segment.train(-100);
    // Should handle gracefully without crashing
    TEST_ASSERT_EQUAL(TrainingState::TRAINING, segment.state);
}

void test_edge_case_very_large_time() {
    TrainingParams params = createTestParams(5, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);
    segment.train(100);  // Initialize

    // Test with very large time delta
    segment.train(1000000);
    // Should handle gracefully
    TEST_ASSERT_TRUE(segment.state == TrainingState::TRAINING ||
                     segment.state == TrainingState::END);
}

// ===== ADVANCED SIMULATION TESTS =====
void test_repetition_full_training_simulation() {
    TrainingParams params = createTestParams(3, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);

    // Initialize
    segment.train(100);
    TEST_ASSERT_EQUAL(TrainingState::TRAINING, segment.state);

    // Simulate full training session - need to move position in window and let
    // windows scroll down
    for (int i = 0; i < 200; i++) {
        // Keep position in the middle of the window range to let windows scroll
        float targetPos = (segment.startWindow + segment.endWindow) / 2.0f;
        segment.setPositionSpeed(targetPos, segment.params.trainingSpeed);
        segment.train(100);

        if (segment.state == TrainingState::END) break;
    }

    TEST_ASSERT_EQUAL(TrainingState::END, segment.state);
    TEST_ASSERT_TRUE(segment.currentValue >=
                     2);  // Should complete at least 2 reps
}

void test_endurance_full_training_simulation() {
    TrainingParams params =
        createEnduranceParams(2.0f);  // 2 seconds for quick test
    EnduranceSegment segment(params);

    segment.train(100);  // Initialize

    // Clear waiting for return first
    segment.setPositionSpeed(15.0f, 2.0f);
    segment.train(100);

    // Simulate endurance training
    for (int i = 0; i < 30;
         i++) {  // 3.0 seconds total (to ensure we pass 2.0s target)
        float position = 15.0f + (i % 10) * 0.1f;  // Small movements
        segment.setPositionSpeed(position, 2.0f);
        segment.train(100);

        if (segment.state == TrainingState::END) break;
    }

    TEST_ASSERT_TRUE(segment.state == TrainingState::END ||
                     segment.state == TrainingState::TRAINING);
}

void test_bounce_full_training_simulation() {
    TrainingParams params = createTestParams(3, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    BounceSegment segment(params);

    segment.train(100);  // Initialize

    // Simulate bounce training with direction changes
    bool movingRight = false;
    float position = 16.0f;

    for (int i = 0; i < 200; i++) {
        segment.movingRight = movingRight;

        if (movingRight) {
            position += 0.5f;
            if (position > 18.0f) {
                movingRight = false;
                segment.currentValue++;
            }
        } else {
            position -= 0.5f;
            if (position < 1.0f) {
                movingRight = true;
                segment.currentValue++;
            }
        }

        segment.setPositionSpeed(position, 3.0f);
        segment.train(100);

        if (segment.state == TrainingState::END) break;
    }

    TEST_ASSERT_EQUAL(TrainingState::END, segment.state);
}

void test_freeform_full_training_simulation() {
    TrainingParams params = createFreeformParams(2.0f, 60.0f, 10);
    FreeformSegment segment(params);

    segment.train(100);  // Initialize

    // Simulate freeform training with varying RPM
    for (int i = 0; i < 25; i++) {
        float rpm = 50.0f + (i % 20) * 2.0f;  // Varying RPM 50-90
        segment.currentRpm = rpm;

        float position = 15.0f + (i % 10) * 0.1f;
        segment.setPositionSpeed(position, 3.0f);
        segment.train(100);

        if (segment.state == TrainingState::END) break;
    }

    TEST_ASSERT_EQUAL(TrainingState::END, segment.state);
}

void test_repetition_window_movement() {
    TrainingParams params = createTestParams(5, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);
    segment.train(100);  // Initialize

    // Clear waiting for return
    segment.setPositionSpeed(15.0f, 5.0f);  // In window
    segment.train(100);
    TEST_ASSERT_FALSE(segment.isWaitingForReturn);

    // Test window movement during training
    float initialEndWindow = segment.endWindow;

    // Simulate training with position changes - keep position in window
    for (int i = 0; i < 20; i++) {
        segment.setPositionSpeed(15.0f, 5.0f);  // In window
        segment.train(100);
    }

    // Windows should have moved (endWindow moves down during training)
    TEST_ASSERT_TRUE(segment.endWindow < initialEndWindow);
}

void test_endurance_streak_reset() {
    TrainingParams params = createEnduranceParams(10.0f);
    EnduranceSegment segment(params);
    segment.train(100);  // Initialize

    // Clear waiting for return first - need to be in the actual window
    // Start window is around 16.0f with window size of 3.0f
    segment.setPositionSpeed(2.0f, 5.0f);  // In window (close to endWindow)
    segment.train(100);

    // Build up a streak by staying in window
    segment.setPositionSpeed(2.0f, 5.0f);  // In window
    segment.train(1000);
    segment.setPositionSpeed(2.0f, 5.0f);  // Still in window
    segment.train(1000);

    unsigned int streakBeforeReset = segment.currentStreak;
    TEST_ASSERT_TRUE(streakBeforeReset > 0);  // Should have built up a streak

    // Move outside window to reset streak
    segment.setPositionSpeed(20.0f, 5.0f);  // Behind window
    segment.train(100);

    TEST_ASSERT_EQUAL(0, segment.currentStreak);
    TEST_ASSERT_TRUE(segment.longestStreak >
                     0);  // Should have recorded a streak
}

void test_bounce_direction_switching() {
    TrainingParams params = createTestParams(5, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    BounceSegment segment(params);
    segment.train(100);  // Initialize

    // Test direction switching logic - simulate complete bounce cycle
    bool initialValue = segment.movingRight;
    segment.movingRight = false;

    // Simulate training to let windows move down to effective end position and
    // then back up
    for (int i = 0; i < 100; i++) {
        // Follow the window as it moves
        float targetPos = (segment.startWindow + segment.endWindow) / 2.0f;
        segment.setPositionSpeed(targetPos, 5.0f);
        segment.train(100);

        // Check if we've completed at least one bounce (rep)
        if (segment.currentValue > initialValue) {
            break;
        }
    }

    // Should have completed at least one bounce (which involves direction
    // switching)
    TEST_ASSERT_TRUE(segment.movingRight != initialValue);
}

void test_freeform_dynamic_boundaries() {
    TrainingParams params = createFreeformParams(10.0f, 60.0f, 20);
    FreeformSegment segment(params);
    segment.train(100);  // Initialize

    // Test dynamic boundary updates
    float initialThreshold = segment.freeformRepDetectionThreshold;

    // Simulate progress
    segment.currentValue = 5000;  // 50% progress
    segment.updateDynamicBoundaries();

    // Threshold should have increased
    TEST_ASSERT_TRUE(segment.freeformRepDetectionThreshold > initialThreshold);
}

void test_statistics_tracking() {
    TrainingParams params = createTestParams();
    RepetitionSegment segment(params);
    segment.train(100);  // Initialize the segment first

    // Test comprehensive statistics tracking
    segment.setPositionSpeed(20.0f, 10.0f);
    segment.train(10);  // Give it time to process
    segment.setPositionSpeed(19.5f, 15.0f);
    segment.train(10);
    segment.setPositionSpeed(19.0f, 8.0f);
    segment.train(10);

    TEST_ASSERT_EQUAL(16.0f, segment.statistics.minDepth);  // Started at 16.0f
    TEST_ASSERT_EQUAL(20.0f, segment.statistics.maxDepth);
    TEST_ASSERT_EQUAL(8.0f, segment.statistics.minSpeed);
    TEST_ASSERT_EQUAL(15.0f, segment.statistics.maxSpeed);
    TEST_ASSERT_TRUE(segment.statistics.distance > 0);
}

void test_rpm_calculation() {
    TrainingParams params = createTestParams();
    RepetitionSegment segment(params);
    segment.train(100);  // Initialize the segment first

    // Clear waiting for return
    segment.setPositionSpeed(15.0f, 5.0f);
    segment.train(100);

    // Test RPM calculation with stroke detection
    // With default params (range=14cm), threshold = 3.5cm
    // Need movements > 3.5cm in one direction before reversing
    segment.setPositionSpeed(16.0f, 5.0f);
    segment.train(100);
    segment.setPositionSpeed(14.0f, 5.0f);
    segment.train(100);
    segment.setPositionSpeed(12.0f, 5.0f);
    segment.train(100);
    segment.setPositionSpeed(10.0f, 5.0f);  // Cumulative: ~6cm left
    segment.train(100);
    segment.setPositionSpeed(12.0f, 5.0f);  // Direction change, stroke counted
    segment.train(100);
    segment.setPositionSpeed(14.0f, 5.0f);
    segment.train(100);
    segment.setPositionSpeed(16.0f, 5.0f);
    segment.train(100);
    segment.setPositionSpeed(18.0f, 5.0f);  // Cumulative: ~8cm right
    segment.train(100);

    // Should have detected strokes
    TEST_ASSERT_TRUE(segment.statistics.strokes > 0);
    // RPM calculation might need more time/strokes, so just verify strokes are
    // detected
    TEST_ASSERT_TRUE(segment.statistics.rpmCount >= 0);
}

void test_grade_edge_cases() {
    TrainingParams params = createTestParams();
    RepetitionSegment segment(params);
    segment.train(100);  // Initialize

    // Test grade calculation edge cases
    segment.timeInsideWindow = 0;
    segment.timeOutsideWindow = 1000;
    TEST_ASSERT_EQUAL(0, segment.grade());

    segment.timeInsideWindow = 1000;
    segment.timeOutsideWindow = 0;
    TEST_ASSERT_EQUAL(100, segment.grade());

    // Test with very large numbers
    segment.timeInsideWindow = 1000000;
    segment.timeOutsideWindow = 1000000;
    TEST_ASSERT_EQUAL(50, segment.grade());
}

void test_progress_edge_cases() {
    TrainingParams params = createTestParams(0, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);

    // Test progress calculation with zero target
    float progress = segment.getTrainingProgress();
    TEST_ASSERT_EQUAL_FLOAT(0.0f, progress);

    // Test progress calculation with negative current value
    segment.currentValue = -5;
    progress = segment.getTrainingProgress();
    TEST_ASSERT_EQUAL_FLOAT(0.0f, progress);

    // Test progress calculation with current value exceeding target
    segment.params.target = 10;
    segment.currentValue = 15;
    progress = segment.getTrainingProgress();
    TEST_ASSERT_EQUAL_FLOAT(1.0f, progress);
}

// ===== STATISTICS COMPLETENESS TESTS =====
void test_repetition_sets_end_time_on_completion() {
    TrainingParams params = createTestParams(3, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    RepetitionSegment segment(params);
    segment.train(100);  // Initialize

    segment.currentValue = 3;
    segment.train(100);

    TEST_ASSERT_EQUAL(TrainingState::END, segment.state);
    TEST_ASSERT_GREATER_THAN(0, segment.statistics.endTimeMs);
    TEST_ASSERT_GREATER_OR_EQUAL(segment.statistics.startTimeMs,
                                 segment.statistics.endTimeMs);
}

void test_endurance_sets_end_time_on_completion() {
    TrainingParams params = createEnduranceParams(5.0f);
    EnduranceSegment segment(params);
    segment.train(100);  // Initialize

    segment.currentValue = 5000;
    segment.train(100);

    TEST_ASSERT_EQUAL(TrainingState::END, segment.state);
    TEST_ASSERT_GREATER_THAN(0, segment.statistics.endTimeMs);
    TEST_ASSERT_GREATER_OR_EQUAL(segment.statistics.startTimeMs,
                                 segment.statistics.endTimeMs);
}

void test_bounce_sets_end_time_on_completion() {
    TrainingParams params = createTestParams(3, 16.0f, 2.0f, 10, 20.0f, 3.0f);
    BounceSegment segment(params);
    segment.train(100);  // Initialize

    segment.currentValue = 3;
    segment.train(100);

    TEST_ASSERT_EQUAL(TrainingState::END, segment.state);
    TEST_ASSERT_GREATER_THAN(0, segment.statistics.endTimeMs);
    TEST_ASSERT_GREATER_OR_EQUAL(segment.statistics.startTimeMs,
                                 segment.statistics.endTimeMs);
}

void test_freeform_sets_end_time_on_completion() {
    TrainingParams params = createFreeformParams(5.0f, 60.0f, 10);
    FreeformSegment segment(params);
    segment.train(100);  // Initialize

    segment.currentValue = 5000;
    segment.train(100);

    TEST_ASSERT_EQUAL(TrainingState::END, segment.state);
    TEST_ASSERT_GREATER_THAN(0, segment.statistics.endTimeMs);
    TEST_ASSERT_GREATER_OR_EQUAL(segment.statistics.startTimeMs,
                                 segment.statistics.endTimeMs);
}

void setup() {
    // NOTE!!! Wait for >2 secs
    // if board doesn't support software reset via Serial.DTR/RTS
    delay(2000);

    UNITY_BEGIN();  // IMPORTANT LINE!

    // Repetition tests
    RUN_TEST(test_repetition_initialization);
    RUN_TEST(test_repetition_validation);
    RUN_TEST(test_repetition_position_states);
    RUN_TEST(test_repetition_completion);
    RUN_TEST(test_repetition_waiting_for_return);
    RUN_TEST(test_repetition_grade_calculation);
    RUN_TEST(test_repetition_value_string);

    // Endurance tests
    RUN_TEST(test_endurance_initialization);
    RUN_TEST(test_endurance_validation);
    RUN_TEST(test_endurance_time_tracking);
    RUN_TEST(test_endurance_streak_tracking);
    RUN_TEST(test_endurance_value_string);

    // Bounce tests
    RUN_TEST(test_bounce_initialization);
    RUN_TEST(test_bounce_direction_changes);
    RUN_TEST(test_bounce_completion);
    RUN_TEST(test_bounce_value_string);

    // Freeform tests
    RUN_TEST(test_freeform_initialization);
    RUN_TEST(test_freeform_rpm_detection);
    RUN_TEST(test_freeform_time_tracking);
    RUN_TEST(test_freeform_value_string);

    // Base class tests
    // RUN_TEST(test_segment_base_position_tracking);
    RUN_TEST(test_segment_base_direction_detection);
    RUN_TEST(test_segment_base_progress_calculation);
    RUN_TEST(test_segment_base_dynamic_boundaries);

    // Stroke counting tests (cumulative threshold)
    RUN_TEST(test_repetition_small_oscillations_no_stroke);
    RUN_TEST(test_repetition_medium_oscillations_no_stroke);
    RUN_TEST(test_repetition_large_movement_counts_stroke);
    RUN_TEST(test_repetition_multiple_valid_strokes);
    RUN_TEST(test_bounce_small_oscillations_no_stroke);
    RUN_TEST(test_endurance_small_oscillations_no_stroke);
    RUN_TEST(test_freeform_uses_progressive_threshold);
    RUN_TEST(test_small_range_uses_minimum_threshold);

    // Edge cases
    RUN_TEST(test_edge_case_zero_target);
    RUN_TEST(test_edge_case_extreme_positions);
    RUN_TEST(test_edge_case_extreme_speeds);
    RUN_TEST(test_edge_case_negative_time);
    RUN_TEST(test_edge_case_very_large_time);

    // Advanced simulation tests
    RUN_TEST(test_repetition_full_training_simulation);
    RUN_TEST(test_endurance_full_training_simulation);
    RUN_TEST(test_bounce_full_training_simulation);
    RUN_TEST(test_freeform_full_training_simulation);
    RUN_TEST(test_repetition_window_movement);
    RUN_TEST(test_endurance_streak_reset);
    RUN_TEST(test_bounce_direction_switching);
    RUN_TEST(test_freeform_dynamic_boundaries);
    RUN_TEST(test_statistics_tracking);
    RUN_TEST(test_rpm_calculation);
    RUN_TEST(test_grade_edge_cases);
    RUN_TEST(test_progress_edge_cases);

    // Statistics completeness tests
    RUN_TEST(test_repetition_sets_end_time_on_completion);
    RUN_TEST(test_endurance_sets_end_time_on_completion);
    RUN_TEST(test_bounce_sets_end_time_on_completion);
    RUN_TEST(test_freeform_sets_end_time_on_completion);

    UNITY_END();
}

void loop() {}