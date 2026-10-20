#ifndef BOUNCE_H
#define BOUNCE_H

#include <Arduino.h>

#include "trainingTypes.h"

class BounceSegment final : public SegmentBase {
  public:
    explicit BounceSegment(const TrainingParams &initialParams)
        : SegmentBase(TrainingType::BOUNCE, initialParams),
          movingRight(false) {}

    bool movingRight;

    void train(const int timeDeltaMs) override {
        recordMomentum();
        if (state == TrainingState::START) {
            validateParams();

            startWindow = getCurrentEffectiveStartPosition();
            endWindow =
                getCurrentEffectiveStartPosition() - params.targetWindow;
            return;
        }

        if (currentPosition > startWindow && !movingRight) {
            positionState = TrainingPosition::AHEAD;
        } else if (currentPosition < endWindow && !movingRight) {
            positionState = TrainingPosition::BEHIND;
        } else if (currentPosition < endWindow && movingRight) {
            positionState = TrainingPosition::AHEAD;
        } else if (currentPosition > startWindow && movingRight) {
            positionState = TrainingPosition::BEHIND;
        } else {
            positionState = TrainingPosition::IN_WINDOW;
        }

        if (currentValue >= params.target) {
            state = TrainingState::END;
            statistics.endTimeMs = millis();
            return;
        }

        double speedModifier = 1.0;

        if (positionState == TrainingPosition::AHEAD) {
            speedModifier = 0.5;
            timeOutsideWindow += timeDeltaMs;
        } else if (positionState == TrainingPosition::BEHIND) {
            speedModifier = 0.0;
            timeOutsideWindow += timeDeltaMs;
        } else {
            timeInsideWindow += timeDeltaMs;
        }

        const double delta =
            speedModifier * (params.trainingSpeed / 10) * timeDeltaMs / 1000;

        if (movingRight) {
            startWindow =
                constrain(startWindow + delta, getCurrentEffectiveEndPosition(),
                          getCurrentEffectiveStartPosition());
            endWindow = constrain(startWindow - params.targetWindow,
                                  getCurrentEffectiveEndPosition(),
                                  getCurrentEffectiveStartPosition());

            if (startWindow >= getCurrentEffectiveStartPosition()) {
                movingRight = false;
                currentValue++;
            }
        } else {
            startWindow =
                constrain(startWindow - delta, getCurrentEffectiveEndPosition(),
                          getCurrentEffectiveStartPosition());
            endWindow = constrain(startWindow - params.targetWindow,
                                  getCurrentEffectiveEndPosition(),
                                  getCurrentEffectiveStartPosition());

            if (endWindow <= getCurrentEffectiveEndPosition()) {
                movingRight = true;
            }
        }
    }

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
        return String(currentValue);
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

        // For Bounce: endPosition moves toward DEAD_ZONE_CM
        currentEffectiveStartPosition = params.startPosition;
        float oldEndPosition = currentEffectiveEndPosition;
        currentEffectiveEndPosition =
            constrain(params.endPosition - depthChangeAmount, DEAD_ZONE_CM,
                      params.startPosition);
    }

  private:
    bool validateParams() override {
        params.trainingSpeed = constrain(params.trainingSpeed, 0.1f, 1000.0f);
        params.startPosition =
            constrain(params.startPosition,
                      float(DEAD_ZONE_CM + MINIMUM_STROKE_LENGTH_CM),
                      float(MAX_RANGE_CM));

        params.endPosition =
            constrain(params.endPosition, float(DEAD_ZONE_CM),
                      params.startPosition - MINIMUM_STROKE_LENGTH_CM);

        state = TrainingState::TRAINING;
        return true;
    }
};

#endif  // BOUNCE_H