#ifndef ENDURANCE_H
#define ENDURANCE_H

#include <Arduino.h>

#include "trainingTypes.h"

class EnduranceSegment final : public SegmentBase {
  public:
    explicit EnduranceSegment(const TrainingParams& initialParams)
        : SegmentBase(TrainingType::ENDURANCE, initialParams) {
        isWaitingForReturn = true;

        // intentionally override deadzone protection.
        endWindow = 0.0f;
        startWindow = params.endPosition + params.targetWindow;

        // in this context the "endPosition" is the deepest point the toy can
        // go. so it's meaning is inverted. in this contenxt.
        params.startPosition = params.endPosition;
        params.endPosition = 0.0f;

        currentEffectiveStartPosition = params.startPosition;
        currentEffectiveEndPosition = 0.0f;

        // it's assumed that the target is in seconds
        params.target = params.target * 1000;
    }

    // Runs the training repetitions based on the parameters and time delta.
    void train(const int timeDeltaMs) override {
        recordMomentum();
        if (state == TrainingState::START) {
            validateParams();  // Ensure training is initialized correctly
            return;
        }

        updateDynamicBoundaries();

        // Update window based on dynamic start position for progressive
        // difficulty
        startWindow = getCurrentEffectiveStartPosition() + params.targetWindow;

        if (currentPosition > startWindow) {
            positionState = TrainingPosition::BEHIND;
        } else if (currentPosition < endWindow) {
            positionState = TrainingPosition::AHEAD;
        } else {
            positionState = TrainingPosition::IN_WINDOW;
        }

        if (currentValue >= params.target) {
            state = TrainingState::END;
            longestStreak = max(longestStreak, currentStreak);
            statistics.endTimeMs = millis();
            return;
        }

        if (isWaitingForReturn) {
            if (positionState == TrainingPosition::IN_WINDOW) {
                isWaitingForReturn = false;
            }
            return;
        }

        if (positionState == TrainingPosition::AHEAD) {
            timeOutsideWindow += timeDeltaMs;
            longestStreak = max(longestStreak, currentStreak);
            currentStreak = 0;
        } else if (positionState == TrainingPosition::BEHIND) {
            timeOutsideWindow += timeDeltaMs;
            longestStreak = max(longestStreak, currentStreak);
            currentStreak = 0;
        } else {
            currentStreak += timeDeltaMs;
            currentValue += timeDeltaMs;
            timeInsideWindow += timeDeltaMs;
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
        // Calculate percentage-based depth progression
        // trainingDepthIncrease: 10=30%, 20=60%, 30=100% of available depth
        auto difficultyPercentage =
            0.5 * static_cast<float>(params.trainingDepthIncrease) / 30.0f;

        auto availableWindow = params.targetWindow * difficultyPercentage;

        float percentComplete = static_cast<float>(currentValue) /
                                static_cast<float>(params.target);

        currentEffectiveStartPosition =
            params.startPosition - availableWindow * percentComplete;
    }

  private:
    // Initializes the training session and validates the parameters.
    bool validateParams() override {
        // Safety checks

        params.trainingSpeed = constrain(params.trainingSpeed, 0.1f, 1000.0f);
        params.startPosition =
            constrain(params.startPosition,
                      float(DEAD_ZONE_CM + MINIMUM_STROKE_LENGTH_CM),
                      float(MAX_RANGE_CM));

        params.endPosition = 0.0f;
        state = TrainingState::TRAINING;

        return true;  // Assume validation passes unless an error condition is
        // met
    }
};

#endif  // ENDURANCE_H
