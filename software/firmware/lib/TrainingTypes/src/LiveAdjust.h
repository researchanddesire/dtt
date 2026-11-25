#ifndef LIVE_ADJUST_H
#define LIVE_ADJUST_H

// Bounds for changing a playing segment over Bluetooth. Plain C++ so the
// host tests can check them.

#include <algorithm>
#include <cmath>

// Positions are distances from the sensor in cm: the tip is the larger number.
struct LiveAdjustLimits {
    float tipCm;          // the segment's start position
    float deepestCm;      // the deepest end position allowed (calibrated deep)
    float minStrokeCm;    // room always left between the block and the tip
};

struct LiveAdjustValues {
    float endPosition;    // the deep end of the moving block's travel
    float targetWindow;   // the block's width
    float trainingSpeed;  // block speed (cm/s x 10) or freeform target rpm
};

constexpr float LIVE_ADJUST_MIN_WINDOW_CM = 0.5f;
constexpr float LIVE_ADJUST_MIN_SPEED = 0.1f;
constexpr float LIVE_ADJUST_MAX_SPEED = 1000.0f;

inline bool liveAdjustFinite(const LiveAdjustValues& values) {
    return std::isfinite(values.endPosition) &&
           std::isfinite(values.targetWindow) &&
           std::isfinite(values.trainingSpeed);
}

// Brings requested values inside the segment's limits. The block keeps at
// least its minimum width, never goes deeper than the deepest position and
// always leaves minStrokeCm below the tip. The result is what gets applied.
inline LiveAdjustValues clampLiveAdjust(const LiveAdjustValues& requested,
                                        const LiveAdjustLimits& limits) {
    LiveAdjustValues applied{};
    applied.trainingSpeed = std::min(
        LIVE_ADJUST_MAX_SPEED,
        std::max(LIVE_ADJUST_MIN_SPEED, requested.trainingSpeed));
    const float travel =
        std::max(0.0f, limits.tipCm - limits.deepestCm - limits.minStrokeCm);
    const float widest = std::max(LIVE_ADJUST_MIN_WINDOW_CM, travel);
    applied.targetWindow = std::min(
        widest, std::max(LIVE_ADJUST_MIN_WINDOW_CM, requested.targetWindow));
    const float shallowest =
        std::max(limits.deepestCm,
                 limits.tipCm - applied.targetWindow - limits.minStrokeCm);
    applied.endPosition = std::min(
        shallowest, std::max(limits.deepestCm, requested.endPosition));
    return applied;
}

#endif  // LIVE_ADJUST_H
