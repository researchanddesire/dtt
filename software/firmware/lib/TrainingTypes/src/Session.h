#ifndef SESSION_H
#define SESSION_H

#include <Arduino.h>
#include "structs/DashboardState.h"

#ifndef PROVISION

#include <map>
#include <optional>

#include "constants/strings.h"
#include "trainingTypes.h"
#include "uuid.hpp"

struct PassFailConfig {
    bool enabled = false;
    int threshold = 0;  // 0-100
    String failureText = "";
};

struct Segment {
    String id;
    uint16_t idx;  // Global expanded index from backend (0-based)
    String name;
    String difficulty;
    TrainingType type;
    TrainingParams params;
    PassFailConfig passFail;
};

static const Segment defaultSegment = {
    .id = DEFAULT_ID,
    .idx = 0,
    .name = DEFAULT_SEGMENT_NAME,
    .difficulty = DEFAULT_SEGMENT_DIFFICULTY,
    .type = TrainingType::REPETITION,
    .params =
        {
            .target = 5,
            .startPosition = 16,
            .endPosition = 2,
            .trainingDepthIncrease = 1,
            .trainingSpeed = 20,
            .targetWindow = 3,
        },
};

struct ToyCalibration {
    bool isCalibrated = false;
    float minCm = 0.0f;
    float maxCm = 0.0f;
    String calibratedAt = "";
};

struct Toy {
    String id;
    String name;
    String tagline;
    ToyCalibration calibration;
};

static const Toy defaultToy = {.id = DEFAULT_ID,
                               .name = DEFAULT_TOY_NAME,
                               .tagline = DEFAULT_TOY_DESCRIPTION};

struct IconConfig {
    String set = "streamline";
    int set_id = 588;
};

static const IconConfig defaultIconConfig = {.set = "streamline",
                                             .set_id = 588};

struct Session {
    String id = uuid();
    String settingsId = DEFAULT_ID;
    String name = DEFAULT_SESSION_NAME;
    String tagline = EMPTY_STRING;
    std::optional<int> iconId = std::nullopt;
    String description = DEFAULT_SESSION_DESCRIPTION;
    String finalText = DEFAULT_SESSION_FINAL_TEXT;
    std::optional<uint8_t> finalColor = std::nullopt;  // LED color for final page (LED_GREEN, LED_RED, LED_YELLOW, LED_BLUE, etc.)
    std::optional<Toy> toy = defaultToy;
    IconConfig icon = defaultIconConfig;
    uint16_t segmentCount = 1;
    uint16_t segmentIdx = 0;
    uint16_t pageIdx = 0;
    uint16_t durationMinutes = 5;
    bool hasSeenSessionDetails = false;
    bool handsFreeMode = false;
    std::vector<Segment> segments = {defaultSegment};
    bool isCalibrated = false;
    float calibratedMinPosition = 0.0;
    float calibratedMaxPosition = 0.0;
    std::map<String, int> segmentFailureCounts;  // segmentId -> failure count
};

#endif  // PROVISION

#endif  // SESSION_H