#pragma once

#include <cmath>

// Matches the dashboard's calibrate-toy contract
// (rad-app packages/schemas/src/dtt/calibration.ts). Distances are from the
// sensor: the tip position is farther away than the deepest position.
constexpr float CALIBRATION_MIN_CM = 1.5f;
// The sensor reads about 22 cm when nothing is in front of it.
constexpr float CALIBRATION_MAX_CM = 21.5f;
// Training windows are fractions of the range; below this they are smaller
// than the sensor noise and the stroke threshold.
constexpr float CALIBRATION_MIN_GAP_CM = 2.0f;

enum class CalibrationProblem { None, SensorError, OutOfRange, Reversed, TooShort };

// A tip beyond the sensor's reach reads about 22 cm, the same as an empty
// sensor. That is a normal starting position for a long toy, so it counts as
// the longest range the dashboard stores.
inline float calibrationTipCm(const float tipCm) {
    return tipCm > CALIBRATION_MAX_CM ? CALIBRATION_MAX_CM : tipCm;
}

inline CalibrationProblem checkCalibration(const float rawTipCm, const float deepCm) {
    if (!std::isfinite(rawTipCm) || !std::isfinite(deepCm))
        return CalibrationProblem::SensorError;
    const float tipCm = calibrationTipCm(rawTipCm);
    if (deepCm < CALIBRATION_MIN_CM) return CalibrationProblem::OutOfRange;
    // Positions in the wrong order by more than noise were taken backwards;
    // anything closer together is a range that is too short to train with.
    if (deepCm - tipCm >= CALIBRATION_MIN_GAP_CM) return CalibrationProblem::Reversed;
    // The deepest position has to be a real reading: past the sensor's reach
    // there is no toy in front of it.
    if (deepCm > CALIBRATION_MAX_CM) return CalibrationProblem::OutOfRange;
    if (tipCm - deepCm < CALIBRATION_MIN_GAP_CM) return CalibrationProblem::TooShort;
    return CalibrationProblem::None;
}
