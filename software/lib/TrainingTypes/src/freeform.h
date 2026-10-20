#ifndef FREEFORM_H
#define FREEFORM_H

#include <Arduino.h>

#include "trainingTypes.h"

class FreeformSegment final : public SegmentBase {
  public:
    explicit FreeformSegment(const TrainingParams& initialParams)
        : SegmentBase(TrainingType::FREEFORM, initialParams) {
        displayType = DisplayType::ARC;
        isWaitingForReturn = true;

        // RPM-based boundaries using API-provided target RPM
        startWindow = params.trainingSpeed;  // Use API target RPM
        endWindow = INFINITY;                // No upper RPM limit

        // it's assumed that the target is in seconds
        params.target = params.target * 1000;

        // Log initialization parameters for debugging
        Serial.println("[FREEFORM] Initializing Freeform training:");
        Serial.print("  Target RPM: ");
        Serial.println(params.trainingSpeed, 1);
        Serial.print("  Duration: ");
        Serial.print(params.target / 1000.0f, 1);
        Serial.println(" seconds");
        Serial.print("  Training depth increase: ");
        Serial.println(params.trainingDepthIncrease);
    }

    // Runs the training repetitions based on the parameters and time delta.
    void train(const int timeDeltaMs) override {
        recordMomentum();
        if (state == TrainingState::START) {
            validateParams();  // Ensure training is initialized correctly
            return;
        }

        // in freeform, the time always moves forward.
        currentValue += timeDeltaMs;

        // Update dynamic boundaries to apply trainingDepthIncrease for rep
        // detection
        updateDynamicBoundaries();

        // RPM-based window detection
        if (currentRpm < startWindow) {
            positionState = TrainingPosition::BEHIND;  // RPM too low
            timeOutsideWindow += timeDeltaMs;
            longestStreak = max(longestStreak, currentStreak);
            currentStreak = 0;
        } else {
            positionState = TrainingPosition::IN_WINDOW;  // Good RPM
            currentStreak += timeDeltaMs;
            timeInsideWindow += timeDeltaMs;
        }

        if (currentValue >= params.target) {
            state = TrainingState::END;
            longestStreak = max(longestStreak, currentStreak);
            statistics.endTimeMs = millis();
            return;
        }
    }

    // getter for grade
    [[nodiscard]] int grade() const override {
        if (timeOutsideWindow <= 0) {
            return 100;
        }

        return constrain(
            static_cast<int>(100 * timeInsideWindow /
                             (timeInsideWindow + timeOutsideWindow)),
            0, 100);
    }

    [[nodiscard]] String valueString() const override {
        // Returns the time remaining in seconds, pretty-printed to 2 decimal
        // places, using String only
        float timeRemaining = float(params.target - currentValue) / 1000.0f;
        if (timeRemaining < 0) timeRemaining = 0;
        return String(timeRemaining, 2) + " s";
    }

    // Update dynamic training boundaries based on progress and
    // trainingDepthIncrease
    void updateDynamicBoundaries() override {
        // Use previous rep's progress for current rep's boundaries
        // This ensures first rep uses original position (0% progress)
        // Formula: (currentValue - 1) / (target - 1) ensures even distribution
        // 3 reps: 0%, 50%, 100% | 4 reps: 0%, 33%, 67%, 100%
        const float prevRepProgress =
            (params.target <= 1)
                ? 0.0f
                : constrain(static_cast<float>(currentValue - 1) /
                                static_cast<float>(params.target - 1),
                            0.0f, 1.0f);

        // Calculate percentage-based depth progression
        // trainingDepthIncrease: 10=30%, 20=60%, 30=100% of available depth
        const float difficultyPercentage =
            static_cast<float>(params.trainingDepthIncrease) / 30.0f;
        const float availableDepth = params.endPosition - DEAD_ZONE_CM;
        const float maxDepthChange = availableDepth * difficultyPercentage;
        const float depthChangeAmount = maxDepthChange * prevRepProgress;

        // For Freeform: RPM-based boundaries, progressive depth
        // threshold for rep detection
        currentEffectiveStartPosition = params.startPosition;
        currentEffectiveEndPosition = params.endPosition;

        // Progressive depth threshold: base 0.5cm + difficulty scaling
        // Easy (10): 0.5cm base, small increases
        // Medium (20): 0.5cm base, moderate increases
        // Hard (30): 0.5cm base, large increases
        const float currentProgress = getTrainingProgress();
        const float difficultyMultiplier =
            static_cast<float>(params.trainingDepthIncrease) /
            30.0f;  // 10=33%, 20=67%, 30=100%
        const float maxIncrease =
            2.0f * difficultyMultiplier;  // Max 0.67cm, 1.33cm, 2.0cm increase
        float oldThreshold = freeformRepDetectionThreshold;
        freeformRepDetectionThreshold = 0.5f + (maxIncrease * currentProgress);
    }

  private:
    // Initializes the training session and validates the parameters.
    bool validateParams() override {
        state = TrainingState::TRAINING;
        return true;
    }
};

#endif  // ENDURANCE_H
