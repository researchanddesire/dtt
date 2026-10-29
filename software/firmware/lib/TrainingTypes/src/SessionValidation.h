#pragma once

#include <ArduinoJson.h>

#include <cmath>
#include <cstdint>
#include <cstring>
#include <initializer_list>

#include "Calibration.h"

enum class SessionDocumentMode { DashboardPage, Complete };

constexpr uint32_t SESSION_PAGE_SIZE = 100;
constexpr uint32_t MAX_COMPLETE_SESSION_SEGMENTS = 8;

namespace session_validation {
    inline bool boundedText(JsonVariantConst value, size_t limit,
                            bool required = false) {
        if (value.isNull()) return !required;
        if (!value.is<const char *>()) return false;
        const size_t length = value.as<JsonString>().size();
        return length <= limit && (!required || length > 0) &&
               std::strlen(value.as<const char *>()) == length;
    }

    inline bool finiteNumber(JsonVariantConst value) {
        return value.is<double>() && std::isfinite(value.as<double>());
    }

    inline bool trainingType(const char *actual, const char *expected) {
        if (actual == nullptr) return false;
        while (*actual && *expected) {
            char value = *actual++;
            if (value >= 'A' && value <= 'Z') value += 'a' - 'A';
            if (value != *expected++) return false;
        }
        return *actual == *expected;
    }
}  // namespace session_validation

// Validate before parsing into Session or replacing a persisted document.
// ErrorString supports both Arduino String and std::string for native tests.
template <typename ErrorString>
bool validateSessionDocument(JsonObjectConst root, ErrorString &error,
                             SessionDocumentMode mode) {
    using namespace session_validation;
    const auto reject = [&](const char *message) {
        error = message;
        return false;
    };
    // Names are display text: dashboard templates allow 128 characters, which
    // can be 512 UTF-8 bytes, and generated plans can be unnamed.
    if (root.isNull() || !root["name"].is<const char *>() ||
        !boundedText(root["name"], 512) ||
        !root["segments"].is<JsonArrayConst>())
        return reject("Session name and segments are required");

    for (const char *key : {"id", "settingsId", "iconSetId"})
        if (!boundedText(root[key], 128))
            return reject("Session identifier is invalid or too long");
    for (const char *key : {"tagline", "description", "finalText"})
        if (!boundedText(root[key], 2048))
            return reject("Session text is invalid or too long");
    if ((!root["handsFreeMode"].isNull() &&
         !root["handsFreeMode"].is<bool>()) ||
        (!root["durationMinutes"].isNull() &&
         !root["durationMinutes"].is<uint16_t>()))
        return reject("Session options have invalid types");

    const JsonArrayConst segments = root["segments"].as<JsonArrayConst>();
    const bool complete = mode == SessionDocumentMode::Complete;
    const size_t maxSegments =
        complete ? MAX_COMPLETE_SESSION_SEGMENTS : SESSION_PAGE_SIZE;
    if (segments.size() == 0 || segments.size() > maxSegments)
        return reject("Session segment array is empty or too large");
    uint32_t count = segments.size();
    uint32_t page = 0;
    if (!complete || !root["segmentCount"].isNull()) {
        if (!root["segmentCount"].is<uint16_t>())
            return reject("segmentCount must be an unsigned integer");
        count = root["segmentCount"].as<uint16_t>();
    }
    if (!complete || !root["pageIdx"].isNull()) {
        if (!root["pageIdx"].is<uint16_t>())
            return reject("pageIdx must be an unsigned integer");
        page = root["pageIdx"].as<uint16_t>();
    }
    const uint32_t firstIndex = page * SESSION_PAGE_SIZE;
    if (count == 0 || firstIndex >= count ||
        (complete && (page != 0 || count != segments.size())) ||
        (!complete && segments.size() != (count - firstIndex < SESSION_PAGE_SIZE
                                              ? count - firstIndex
                                              : SESSION_PAGE_SIZE)))
        return reject("Session count, page and segment array do not agree");

    bool calibrated = false;
    double calibratedMin = 0;
    double calibratedMax = 0;
    if (!root["toy"].isNull()) {
        if (!root["toy"].is<JsonObjectConst>())
            return reject("Toy must be an object");
        const JsonObjectConst toy = root["toy"];
        if (!boundedText(toy["id"], 128) || !boundedText(toy["name"], 512) ||
            !boundedText(toy["tagline"], 2048) ||
            !boundedText(toy["description"], 2048))
            return reject("Toy text is invalid or too long");
        if (!toy["calibration"].isNull()) {
            if (!toy["calibration"].is<JsonObjectConst>())
                return reject("Calibration must be an object");
            const JsonObjectConst calibration = toy["calibration"];
            if (!calibration["isCalibrated"].is<bool>() ||
                !boundedText(calibration["calibratedAt"], 128))
                return reject("Calibration options have invalid types");
            calibrated = calibration["isCalibrated"].as<bool>();
            if (calibrated) {
                if (!finiteNumber(calibration["minCm"]) ||
                    !finiteNumber(calibration["maxCm"]))
                    return reject("Calibration positions must be finite");
                calibratedMin = calibration["minCm"].as<double>();
                calibratedMax = calibration["maxCm"].as<double>();
                if (calibratedMin < 0 || calibratedMax > 100 ||
                    calibratedMin >= calibratedMax)
                    return reject(
                        "Calibration positions are outside safe ranges");
                // A stored range the device cannot train with is ignored:
                // the device asks for a new calibration instead.
                if (checkCalibration(calibratedMax, calibratedMin) !=
                    CalibrationProblem::None)
                    calibrated = false;
            }
        }
    }

    uint32_t expectedIndex = firstIndex;
    for (JsonVariantConst item : segments) {
        if (!item.is<JsonObjectConst>())
            return reject("Each segment must be an object");
        const JsonObjectConst segment = item;
        if (!segment["idx"].is<uint16_t>() ||
            segment["idx"].as<uint16_t>() != expectedIndex++)
            return reject("Segment indices must be contiguous within the page");
        if (!boundedText(segment["id"], 128) ||
            !boundedText(segment["name"], 256) ||
            !boundedText(segment["difficulty"], 80))
            return reject("Segment text is invalid or too long");
        if (!boundedText(segment["type"], 16, true))
            return reject("Training type must be a bounded string");
        const char *type = segment["type"] | "";
        if (!trainingType(type, "repetition") &&
            !trainingType(type, "endurance") &&
            !trainingType(type, "freeform") && !trainingType(type, "bounce"))
            return reject("Unknown training type");
        const JsonObjectConst params = segment["params"].as<JsonObjectConst>();
        if (params.isNull() || !finiteNumber(params["target"]) ||
            !finiteNumber(params["trainingDepthIncrease"]) ||
            !finiteNumber(params["startPosition"]) ||
            !finiteNumber(params["endPosition"]) ||
            !finiteNumber(params["trainingSpeed"]) ||
            !finiteNumber(params["targetWindow"]))
            return reject("Each segment needs finite numeric parameters");
        // Stored dashboard values can be fractional. Bound the truncated
        // integers the session parser uses; out-of-range values convert to 0.
        const int32_t target = params["target"].as<int32_t>();
        const int depth = params["trainingDepthIncrease"].as<int>();
        const double start =
            calibrated ? calibratedMax : params["startPosition"].as<double>();
        const double end =
            calibrated ? calibratedMin : params["endPosition"].as<double>();
        const double speed = params["trainingSpeed"].as<double>();
        const double window = params["targetWindow"].as<double>();
        // Timed segments multiply seconds by 1000 in a signed 32-bit field.
        if (target <= 0 || target > INT32_MAX / 1000 || start <= end ||
            start > 100 || end < 0 || depth < 0 || depth > 100 || speed <= 0 ||
            speed > 1000 || window <= 0 || window > 100)
            return reject(
                "Segment parameters are outside safe training ranges");
        if (!segment["passFail"].isNull()) {
            if (!segment["passFail"].is<JsonObjectConst>())
                return reject("Pass/fail must be an object");
            const JsonObjectConst passFail = segment["passFail"];
            if (!passFail["enabled"].is<bool>() ||
                !passFail["threshold"].is<int>() ||
                passFail["threshold"].as<int>() < 0 ||
                passFail["threshold"].as<int>() > 100 ||
                !boundedText(passFail["failureText"], 2048))
                return reject("Pass/fail options are invalid");
        }
    }
    error = "";
    return true;
}
