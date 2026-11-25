#include "vibrator.h"

#ifndef PROVISION

#include "../utils/easing.h"
#include "wifiSettings.h"

// Initialize the global vibrator instance
Vibrator vibratorInstance;
std::atomic<bool> vibratorFollowsPace{false};

// Service initialization function
void initVibratorService() {
    ledcSetup(0, 20000, 8);
    ledcAttachPin(REWARD_OUTPUT, 0);
}

void Vibrator::off() {
    ledcWrite(0, 0);
    ESP_LOGD(VIBRATOR_TAG, "Turning off Vibrator");
}

void Vibrator::tick(const SegmentBase& segment) {
    unsigned long currentTime = millis();
    const unsigned long sinceLastTick =
        currentTime - vibratorInstance.previousTickTime;

    // Record the previous tick timestamp
    vibratorInstance.previousTickTime = currentTime;

    // Freeform, when a Bluetooth client asks for it: power follows the pace.
    // At or above the target RPM it is 100%; below it, it is the share of the
    // target reached (half the target pace gives 50%). The measured RPM steps
    // once per stroke, so glide towards it rather than jumping.
    if (vibratorFollowsPace && segment.type == TrainingType::FREEFORM &&
        segment.params.trainingSpeed > 0.0f) {
        const double share = constrain(
            segment.currentRpm / segment.params.trainingSpeed, 0.0f, 1.0f);
        const double target = 100.0 * share;
        // Roughly a 300 ms glide, whatever the loop rate.
        const double step = constrain(sinceLastTick / 300.0, 0.0, 1.0);
        vibratorInstance.currentPercentagePower +=
            (target - vibratorInstance.currentPercentagePower) * step;
        vibratorInstance.targetPercentagePower = target;
        vibratorInstance.isFading = false;
    } else if (segment.positionState == TrainingPosition::IN_WINDOW) {
        // Other segments: 100% power when IN_WINDOW, gradual fade when out
        // Immediately set target to 100% when in window
        vibratorInstance.targetPercentagePower = 100.0;
        vibratorInstance.currentPercentagePower = 100.0;
        vibratorInstance.isFading = false;
    } else {
        // Set target to 0% when out of window
        vibratorInstance.targetPercentagePower = 0.0;

        // Start fading if not already fading
        if (!vibratorInstance.isFading) {
            vibratorInstance.isFading = true;
            vibratorInstance.fadeStartTime = currentTime;
            vibratorInstance.fadeStartPower =
                vibratorInstance.currentPercentagePower;
        }

        // Calculate fade progress over 10 seconds (10000ms)
        unsigned long fadeDuration = 1000;
        unsigned long elapsedTime =
            currentTime - vibratorInstance.fadeStartTime;

        if (elapsedTime >= fadeDuration) {
            // Fade complete
            vibratorInstance.currentPercentagePower = 0.0;
        } else {
            // Calculate fade progress (0.0 to 1.0)
            double fadeProgress = static_cast<double>(elapsedTime) /
                                  static_cast<double>(fadeDuration);

            // Use easing function to smoothly transition from fade start power
            // to target (0)
            double easedProgress = ease(fadeProgress);

            // Interpolate between the power level when fade started and target
            // (0)
            vibratorInstance.currentPercentagePower =
                vibratorInstance.fadeStartPower +
                (vibratorInstance.targetPercentagePower -
                 vibratorInstance.fadeStartPower) *
                    easedProgress;
        }
    }

    ESP_LOGV(VIBRATOR_TAG, "Vibrating at %f%%",
             vibratorInstance.currentPercentagePower);

    ledcWrite(
        0, static_cast<short>(2.55f * vibratorInstance.currentPercentagePower));
}

#endif  // PROVISION
