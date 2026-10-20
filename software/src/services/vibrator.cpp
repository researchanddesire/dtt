#include "vibrator.h"

#ifndef PROVISION

#include "../utils/easing.h"
#include "wifiSettings.h"

// Initialize the global vibrator instance
Vibrator vibratorInstance;

// Service initialization function
void initVibratorService() {
    ledcSetup(0, 20000, 8);
    ledcAttachPin(REWARD_OUTPUT, 0);
}

void Vibrator::off() {
    ledcWrite(0, 0);
    ESP_LOGD(VIBRATOR_TAG, "Turning off Vibrator");
}

void Vibrator::tick() {
    unsigned long currentTime = millis();

    // Record the previous tick timestamp
    vibratorInstance.previousTickTime = currentTime;

    // Simple logic: 100% power when IN_WINDOW, gradual fade when out of window
    if (currentSegment->positionState == TrainingPosition::IN_WINDOW) {
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
