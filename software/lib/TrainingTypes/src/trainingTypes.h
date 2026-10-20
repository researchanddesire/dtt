#ifndef TRAININGTYPES_H
#define TRAININGTYPES_H

#include <Arduino.h>
#include <ArduinoJson.h>

#include <CircularBuffer.hpp>
#include <algorithm>

#include "uuid.hpp"

#define TRAINING_TAG "TRAINING"

constexpr float DEAD_ZONE_CM = 1.7f;
constexpr float MAX_RANGE_CM = 22.5f;
constexpr float MINIMUM_STROKE_LENGTH_CM = 0.8f;
// Stroke threshold as a percentage of the user's calibration range
// (startPosition - endPosition). Scales noise rejection to each user's device.
constexpr float STROKE_THRESHOLD_PERCENTAGE = 0.25f;
// Minimum stroke threshold floor (in cm) for very small calibration ranges
constexpr float MIN_STROKE_THRESHOLD_CM = 1.0f;

struct RpmEntry {
    int strokes = 0;
    unsigned long timestamp = 0;  // milliseconds since boot
};

static constexpr float DIRECTION_BOUNDS_WIDTH = MINIMUM_STROKE_LENGTH_CM;

template <class X, class M, class N, class O, class Q>
X map_Generic(X x, M in_min, N in_max, O out_min, Q out_max) {
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

enum class TrainingType { REPETITION, ENDURANCE, FREEFORM, BOUNCE };

enum class TrainingState { START, TRAINING, END, ERROR };

enum class TrainingPosition { AHEAD, BEHIND, IN_WINDOW };

enum class DisplayType { BOX, ARC };

// Struct for input parameters
struct TrainingParams {
    // The target could be the number of repetitions, the duration of the
    // training, or any integer value
    int target;

    float startPosition;
    float endPosition;
    int trainingDepthIncrease;
    // Speed in mm/s or rpm based on the training type
    float trainingSpeed;
    float targetWindow;
};

struct Statistics {
    float minDepth;
    float maxDepth;
    float minSpeed;
    float maxSpeed;
    float distance = 0.0f;

    // a single stroke is half of a repetition.
    int strokes = 0;
    long startTimeMs = 0;
    long endTimeMs = 0;

    // for calculating the average RPM
    double rpmSum = 0.0f;
    long rpmCount = 0;
};

struct MomentumMeasure {
    float positionCm = 0.0f;
    float speedCmPerS = 0.0f;
    float rpm = 0.0f;
    long timeMs = 0;
};

constexpr int TIME_BETWEEN_MOMENTUM_MEASUREMENTS_MS = 250;

class SegmentBase {
  public:
    virtual ~SegmentBase() = default;

    String id = uuid();

    String name;

    TrainingParams params{};
    Statistics statistics{};

#ifdef FEATURE_MOMENTUM_RECORDING
    CircularBuffer<MomentumMeasure, 1024> positionTimeBuffer;
    long lastPositionTimeMs = 0;
#endif

    TrainingType type;
    TrainingState state = TrainingState::START;
    TrainingPosition positionState = TrainingPosition::IN_WINDOW;
    DisplayType displayType = DisplayType::BOX;
    const char* errorMessage;

    // This is a value of measure relative to the TrainingParams::target
    int currentValue = 0;
    float currentPosition;
    float currentSpeed = 0.0f;
    float currentRpm = 0.0f;

    float directionBounds[2] = {0.0f, 0.0f};
    bool currentlyMovingForward = true;

    float startWindow;
    float endWindow;

    bool isWaitingForReturn = false;

    int timeInsideWindow = 0;
    int timeOutsideWindow = 0;

    unsigned int longestStreak = 0;
    unsigned int currentStreak = 0;

    // Dynamic training boundaries that change based on trainingDepthIncrease
    float currentEffectiveStartPosition = 0.0f;
    float currentEffectiveEndPosition = 0.0f;
    float freeformRepDetectionThreshold = 0.0f;

    explicit SegmentBase(const TrainingType initialType,
                         const TrainingParams& initialParams) {
        type = initialType;
        params = initialParams;

        // if endPosition is less than deadzone, set it to deadzone
        if (params.endPosition < DEAD_ZONE_CM) {
            params.endPosition = DEAD_ZONE_CM;
        }

        currentPosition = params.startPosition;
        directionBounds[0] = params.startPosition - DIRECTION_BOUNDS_WIDTH / 2;
        directionBounds[1] = params.startPosition + DIRECTION_BOUNDS_WIDTH / 2;
        currentlyMovingForward = true;
        startWindow = params.startPosition;
        endWindow = params.startPosition - params.targetWindow;

        statistics.minDepth = params.startPosition;
        statistics.maxDepth = params.startPosition;
        statistics.minSpeed = 999999.0f;  // Initialize to large value
        statistics.maxSpeed = 0.0f;
        statistics.startTimeMs = millis();
        statistics.strokes = 0;
        statistics.distance = 0.0f;

        // Initialize with a single entry to start the RPM calculation
        rpmBuffer.push({0, millis()});

        // Initialize dynamic boundaries
        currentEffectiveStartPosition = params.startPosition;
        currentEffectiveEndPosition = params.endPosition;
        freeformRepDetectionThreshold = 0.0f;

        // Initialize cumulative stroke detection
        cumulativeMovementInDirection = 0.0f;
        lastPositionForCumulative = params.startPosition;
        lastCumulativeDirection = true;

        // Compute stroke threshold from calibration range (must happen here,
        // before child constructors like EnduranceSegment reassign params)
        float calibrationRange = params.startPosition - params.endPosition;
        calibratedStrokeThreshold = std::max(
            MIN_STROKE_THRESHOLD_CM,
            calibrationRange * STROKE_THRESHOLD_PERCENTAGE);

        switch (type) {
            case TrainingType::REPETITION:
                name = "Repetition";
                break;
            case TrainingType::ENDURANCE:
                name = "Endurance";
                break;
            case TrainingType::FREEFORM:
                name = "Freeform";
                break;
            case TrainingType::BOUNCE:
                name = "Bounce";
                break;
        }
    }

    // CALL THIS EVERY TICK.
    void recordMomentum() {
#ifdef FEATURE_MOMENTUM_RECORDING

        // wait 250 ms before recording the next position
        if (millis() - lastPositionTimeMs <
            TIME_BETWEEN_MOMENTUM_MEASUREMENTS_MS) {
            return;
        }

        long delta = millis() - statistics.startTimeMs;

        positionTimeBuffer.push(
            {currentPosition, currentSpeed, currentRpm, delta});
        lastPositionTimeMs = millis();
#endif
    }

    // Method that must be overridden by the child class
    virtual void train(int timeDeltaMs) = 0;

    void setPositionSpeed(float position, float speed) {
        const int lastStrokes = statistics.strokes;

        // Update dynamic boundaries based on current progress
        updateDynamicBoundaries();

        if (position < directionBounds[0] || position > directionBounds[1]) {
            const bool lastDirection = currentlyMovingForward;
            currentlyMovingForward = position < directionBounds[0];
            directionBounds[0] = position - DIRECTION_BOUNDS_WIDTH / 2;
            directionBounds[1] = position + DIRECTION_BOUNDS_WIDTH / 2;

            if (lastDirection != currentlyMovingForward) {
                // Direction changed - check if cumulative movement in previous
                // direction was enough for a stroke
                float threshold = (type == TrainingType::FREEFORM)
                                      ? freeformRepDetectionThreshold
                                      : calibratedStrokeThreshold;

                ESP_LOGD(TRAINING_TAG,
                         "Direction change: pos=%.2fcm, cumulative=%.2fcm, "
                         "threshold=%.2fcm",
                         position, cumulativeMovementInDirection, threshold);

                if (cumulativeMovementInDirection >= threshold) {
                    statistics.strokes++;
                    ESP_LOGD(TRAINING_TAG, "Stroke counted! Total strokes: %d",
                             statistics.strokes);
                } else {
                    ESP_LOGD(TRAINING_TAG,
                             "Stroke rejected (cumulative < threshold)");
                }

                // Reset cumulative tracking for new direction
                cumulativeMovementInDirection = 0.0f;
                lastPositionForCumulative = position;
                lastCumulativeDirection = currentlyMovingForward;
            } else {
                // Same direction - accumulate movement (all training types)
                float movementDelta = abs(position - lastPositionForCumulative);
                cumulativeMovementInDirection += movementDelta;
                lastPositionForCumulative = position;
            }
        }

        statistics.minDepth = std::min(statistics.minDepth, position);
        statistics.maxDepth = std::max(statistics.maxDepth, position);
        statistics.minSpeed = std::min(statistics.minSpeed, speed);
        statistics.maxSpeed = std::max(statistics.maxSpeed, speed);
        float delta = abs(position - currentPosition);
        if (delta < 1.0f) {  // Only add if the delta is less than 1cm
            statistics.distance += delta;
        }

        // Convert strokes to reps (2 strokes = 1 rep), and ms to minutes

        updateRPM(statistics.strokes - lastStrokes);

        currentPosition = position;
        currentSpeed = speed;
    }

    // const method that must be overridden by the child class
    [[nodiscard]] virtual int grade() const = 0;

    // const method that must be overridden by the child class
    [[nodiscard]] virtual String valueString() const = 0;

    // Static method to convert distance to display X value
    static int toDisplayX(const float xValue) {
        // Assumes map_Generic and constrain are available in the global
        // namespace
        return constrain(map_Generic(xValue, 0.0f, 21.0f, 0.0f, 128.0f), 0,
                         128);
    }

    auto createPayload(String& trainerId, String& sessionId, int segmentIdx,
                       String& settingsId, String& toyId, 
                       int passedStatus = -1) {  // -1=null, 0=false, 1=true
        JsonDocument doc;
        doc["trainerId"] = trainerId;
        doc["sessionId"] = sessionId;
        doc["segmentId"] = id;
        doc["settingsId"] = settingsId;
        doc["toyId"] = toyId;
        doc["name"] = name;
        doc["idx"] = segmentIdx;

        doc["grade"]["value"] = grade();
        doc["grade"]["timeInsideWindowMs"] = timeInsideWindow;
        doc["grade"]["timeOutsideZoneMs"] = timeOutsideWindow;
        doc["grade"]["totalPlayTimeMs"] = timeInsideWindow + timeOutsideWindow;

        // Add passed field (true/false/null based on passedStatus)
        if (passedStatus == -1) {
            doc["passed"] = nullptr;  // null
        } else {
            doc["passed"] = (passedStatus == 1);  // true or false
        }

        doc["statistics"]["minDepthCm"] = statistics.minDepth;
        doc["statistics"]["maxDepthCm"] = statistics.maxDepth;
        doc["statistics"]["minSpeedCmPerS"] = statistics.minSpeed;
        doc["statistics"]["maxSpeedCmPerS"] = statistics.maxSpeed;
        doc["statistics"]["distanceCm"] = statistics.distance;
        doc["statistics"]["strokes"] = statistics.strokes;
        doc["statistics"]["startTimeMs"] = statistics.startTimeMs;
        doc["statistics"]["endTimeMs"] = statistics.endTimeMs;
        doc["statistics"]["avgRpm"] = statistics.rpmSum / statistics.rpmCount;

        doc["params"]["target"] = params.target;
        doc["params"]["startPositionCm"] = params.startPosition;
        doc["params"]["endPositionCm"] = params.endPosition;
        doc["params"]["trainingDepthIncreaseCm"] = params.trainingDepthIncrease;
        doc["params"]["trainingSpeedCmPerS"] = params.trainingSpeed;
        doc["params"]["targetWindowCm"] = params.targetWindow;

        // convert the buffer to an array of objects
#ifdef FEATURE_MOMENTUM_RECORDING
        for (int i = 0; i < positionTimeBuffer.size(); i++) {
            JsonDocument row;
            row["x"] =
                floatToScientificNotation(positionTimeBuffer[i].positionCm, 3);
            row["v"] =
                floatToScientificNotation(positionTimeBuffer[i].speedCmPerS, 3);
            row["r"] = floatToScientificNotation(positionTimeBuffer[i].rpm, 3);
            row["t"] = positionTimeBuffer[i].timeMs;
            doc["momentum"].add(row);
        }
#endif

        return doc;
    }

    // Calculate training progress as a value between 0.0 and 1.0
    // For REPETITION/BOUNCE: currentValue = completed reps, target = total reps
    // For ENDURANCE/FREEFORM: currentValue = elapsed time, target = total time
    [[nodiscard]] float getTrainingProgress() const {
        if (params.target <= 0) return 0.0f;
        return constrain(static_cast<float>(currentValue) /
                             static_cast<float>(params.target),
                         0.0f, 1.0f);
    }

    // Update dynamic training boundaries based on progress and
    // trainingDepthIncrease - must be implemented by child classes
    virtual void updateDynamicBoundaries() = 0;

    // Get the current effective start position (for dynamic boundary
    // calculations)
    [[nodiscard]] float getCurrentEffectiveStartPosition() const {
        return currentEffectiveStartPosition;
    }

    // Get the current effective end position (for dynamic boundary
    // calculations)
    [[nodiscard]] float getCurrentEffectiveEndPosition() const {
        return currentEffectiveEndPosition;
    }

    // Check if a depth change is significant enough to count as a rep (for
    // Freeform)
    [[nodiscard]] bool isDepthChangeSignificantForRep(float depthChange) const {
        if (type != TrainingType::FREEFORM) {
            return true;  // Other training types use different rep counting
                          // logic
        }

        // For Freeform, use progressive depth threshold (tech lead spec)
        // Base 0.5cm + progressive increase based on difficulty
        return abs(depthChange) >= freeformRepDetectionThreshold;
    }

  private:
    virtual bool validateParams() = 0;
    CircularBuffer<RpmEntry, 256> rpmBuffer;
    int rpmStrokeCount = 0;

    // Stroke threshold computed from calibration range in constructor
    float calibratedStrokeThreshold = MIN_STROKE_THRESHOLD_CM;
    // Cumulative stroke detection for Freeform uses a progressive depth
    // threshold (starts at 0.5cm and increases based on difficulty)
    float cumulativeMovementInDirection = 0.0f;
    float lastPositionForCumulative = 0.0f;
    bool lastCumulativeDirection = true;  // true = forward, false = backward

    void updateRPM(const int strokes) {
        const auto timestamp = millis();

        if (rpmBuffer.size() < 2) {
            // Not enough data yet, just accumulate strokes
            rpmStrokeCount = max(0, rpmStrokeCount + strokes);
            currentRpm = 0.0f;
            rpmBuffer.push({strokes, timestamp});
            return;
        }

        const RpmEntry firstEntry = rpmBuffer.first();
        rpmStrokeCount = max(0, rpmStrokeCount + strokes - firstEntry.strokes);

        const long timeDiff = timestamp - firstEntry.timestamp;
        if (timeDiff <= 0 || !isfinite(timeDiff)) {
            currentRpm = 0.0f;
            rpmBuffer.push({0, timestamp});
            return;
        }

        // Calculate reps per minute: (strokes / 2) / (time in minutes)
        const float rpm =
            constrain(static_cast<float>(rpmStrokeCount) / 2.0f /
                          (static_cast<float>(timeDiff) / 60000.0f),
                      0.0f, 500.0f);

        if (isfinite(rpm) && !isnan(rpm) && !isinf(rpm)) {
            currentRpm = static_cast<float>(rpm);
        } else {
            currentRpm = 0.0f;
        }

        statistics.rpmSum += rpm;
        statistics.rpmCount++;

        // Store the new entry in the buffer
        rpmBuffer.push({strokes, timestamp});
    }
};

#endif  // TRAININGTYPES_H
