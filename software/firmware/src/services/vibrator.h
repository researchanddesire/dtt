#ifndef VIBRATOR_H
#define VIBRATOR_H

#ifndef PROVISION

#define VIBRATOR_TAG "Vibrator"

#include <atomic>

#include "services/board.hpp"
class SegmentBase;

class Vibrator {
  private:
    unsigned long previousTickTime = 0;
    double currentPercentagePower = 0.0;
    double targetPercentagePower = 0.0;
    double fadeStartPower = 0.0;
    unsigned long fadeStartTime = 0;
    bool isFading = false;

  public:
    Vibrator() = default;

    static void off();

    static void tick(const SegmentBase& segment);
};

extern Vibrator vibratorInstance;

// Off by default: the vibrator runs at full power while in the window. A
// Bluetooth client may turn it on so freeform power follows the pace. It is
// not saved, and goes back to off when that client disconnects.
extern std::atomic<bool> vibratorFollowsPace;

void initVibratorService();

#endif  // PROVISION

#endif  // VIBRATOR_H
