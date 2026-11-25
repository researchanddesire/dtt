#include <unity.h>

#include <cmath>
#include <cstring>
#include <limits>
#include <string>

#include "LiveAdjust.h"
#include "SessionSnapshot.h"
#include "SessionValidation.h"
#include "TrainingFeed.h"

void setUp() {}
void tearDown() {}

namespace {
    JsonDocument validSession() {
        JsonDocument doc;
        deserializeJson(doc, R"({
      "name":"Synthetic session","segmentCount":1,"pageIdx":0,
      "segments":[{"id":"test-segment","idx":0,"name":"Test",
      "type":"repetition","params":{"target":5,"startPosition":16,
      "endPosition":2,"trainingDepthIncrease":10,"trainingSpeed":20,
      "targetWindow":3}}]})");
        return doc;
    }

    bool valid(const JsonDocument &doc,
               SessionDocumentMode mode = SessionDocumentMode::DashboardPage) {
        std::string error;
        const bool result =
            validateSessionDocument(doc.as<JsonObjectConst>(), error, mode);
        TEST_ASSERT_EQUAL(result, error.empty());
        return result;
    }

    void test_valid_modes_and_training_types() {
        for (const char *type :
             {"repetition", "endurance", "freeform", "BOUNCE"}) {
            auto doc = validSession();
            doc["segments"][0]["type"] = type;
            TEST_ASSERT_TRUE(valid(doc));
            TEST_ASSERT_TRUE(valid(doc, SessionDocumentMode::Complete));
        }
    }

    void test_invalid_segment_indices_are_rejected() {
        for (const char *invalid :
             {"null", "-1", "1", "65536", "0.5", "\"0\""}) {
            auto candidate = validSession();
            JsonDocument index;
            deserializeJson(index, invalid);
            candidate["segments"][0]["idx"].set(index.as<JsonVariantConst>());
            TEST_ASSERT_FALSE(valid(candidate));
            TEST_ASSERT_FALSE(valid(candidate, SessionDocumentMode::Complete));
        }
    }

    void test_empty_unknown_and_malformed_segments_are_rejected() {
        auto doc = validSession();
        doc["segments"].to<JsonArray>();
        TEST_ASSERT_FALSE(valid(doc));
        doc = validSession();
        doc["segments"][0]["type"] = "unknown";
        TEST_ASSERT_FALSE(valid(doc));
        doc["segments"][0]["type"] = std::string("repetition\0unknown", 18);
        TEST_ASSERT_FALSE(valid(doc));
        doc = validSession();
        doc["segments"][0] = nullptr;
        TEST_ASSERT_FALSE(valid(doc));
        doc = validSession();
        doc["segments"][0]["params"]["target"] = "5";
        TEST_ASSERT_FALSE(valid(doc));
        doc = validSession();
        doc["segmentCount"] = "1";
        TEST_ASSERT_FALSE(valid(doc));
        doc = validSession();
        doc["handsFreeMode"] = 1;
        TEST_ASSERT_FALSE(valid(doc));
    }

    void test_finite_and_overflow_boundaries() {
        for (const char *key : {"startPosition", "endPosition", "trainingSpeed",
                                "targetWindow"}) {
            auto doc = validSession();
            doc["segments"][0]["params"][key] =
                std::numeric_limits<double>::infinity();
            TEST_ASSERT_FALSE(valid(doc));
            doc["segments"][0]["params"][key] =
                std::numeric_limits<double>::quiet_NaN();
            TEST_ASSERT_FALSE(valid(doc));
        }
        auto doc = validSession();
        doc["segments"][0]["type"] = "freeform";
        doc["segments"][0]["params"]["target"] = 18000;
        TEST_ASSERT_TRUE(valid(doc));
        doc["segments"][0]["params"]["target"] = INT32_MAX / 1000;
        TEST_ASSERT_TRUE(valid(doc));
        doc["segments"][0]["params"]["target"] = INT32_MAX / 1000 + 1;
        TEST_ASSERT_FALSE(valid(doc));
        doc["segments"][0]["params"]["target"] = 0;
        TEST_ASSERT_FALSE(valid(doc));
        doc["segments"][0]["params"]["target"] = -25;
        TEST_ASSERT_FALSE(valid(doc));
        doc["segments"][0]["params"]["target"] = 3e9;
        TEST_ASSERT_FALSE(valid(doc));
    }

    void test_fractional_dashboard_values_use_parsed_integers() {
        auto doc = validSession();
        doc["segments"][0]["params"]["target"] = 12.5;
        doc["segments"][0]["params"]["trainingDepthIncrease"] = 12.5;
        TEST_ASSERT_TRUE(valid(doc));
        TEST_ASSERT_EQUAL(
            12, doc["segments"][0]["params"]["target"].as<int32_t>());
        doc["segments"][0]["params"]["target"] = 0.5;
        TEST_ASSERT_FALSE(valid(doc));
        doc = validSession();
        doc["segments"][0]["params"]["trainingDepthIncrease"] = 100.5;
        TEST_ASSERT_TRUE(valid(doc));
        doc["segments"][0]["params"]["trainingDepthIncrease"] = 101;
        TEST_ASSERT_FALSE(valid(doc));
        doc["segments"][0]["params"]["trainingDepthIncrease"] = -0.5;
        TEST_ASSERT_TRUE(valid(doc));
        doc["segments"][0]["params"]["trainingDepthIncrease"] = -1;
        TEST_ASSERT_FALSE(valid(doc));
        doc["segments"][0]["params"]["trainingDepthIncrease"] = "10";
        TEST_ASSERT_FALSE(valid(doc));
    }

    void test_dashboard_pagination_and_complete_limits() {
        auto doc = validSession();
        auto item = validSession();
        doc["segments"].to<JsonArray>();
        doc["segmentCount"] = 101;
        for (int index = 0; index < 100; ++index) {
            item["segments"][0]["idx"] = index;
            doc["segments"].add(item["segments"][0]);
        }
        TEST_ASSERT_TRUE(valid(doc));
        TEST_ASSERT_FALSE(valid(doc, SessionDocumentMode::Complete));
        doc["segments"][99]["idx"] = 98;
        TEST_ASSERT_FALSE(valid(doc));
        doc = validSession();
        doc["segmentCount"] = 101;
        doc["pageIdx"] = 1;
        doc["segments"][0]["idx"] = 100;
        TEST_ASSERT_TRUE(valid(doc));
        TEST_ASSERT_FALSE(valid(doc, SessionDocumentMode::Complete));
        doc["pageIdx"] = 65535;
        TEST_ASSERT_FALSE(valid(doc));
        doc = validSession();
        doc.remove("segmentCount");
        doc.remove("pageIdx");
        TEST_ASSERT_TRUE(valid(doc, SessionDocumentMode::Complete));
        TEST_ASSERT_FALSE(valid(doc));
    }

    void test_calibration_override_preserves_existing_dashboard_format() {
        auto doc = validSession();
        doc["segments"][0]["params"]["startPosition"] = 2;
        doc["segments"][0]["params"]["endPosition"] = 16;
        TEST_ASSERT_FALSE(valid(doc));
        auto calibration = doc["toy"]["calibration"].to<JsonObject>();
        calibration["isCalibrated"] = true;
        calibration["minCm"] = 2;
        calibration["maxCm"] = 16;
        TEST_ASSERT_TRUE(valid(doc));
        calibration["minCm"] = 16;
        TEST_ASSERT_FALSE(valid(doc));
        calibration["minCm"] = nullptr;
        TEST_ASSERT_FALSE(valid(doc));
        // A stored range the device cannot train with is ignored, so the
        // segment's own positions decide.
        calibration["minCm"] = 10;
        calibration["maxCm"] = 11;
        TEST_ASSERT_FALSE(valid(doc));
        doc["segments"][0]["params"]["startPosition"] = 16;
        doc["segments"][0]["params"]["endPosition"] = 2;
        TEST_ASSERT_TRUE(valid(doc));
    }

    void test_calibration_range_checks() {
        TEST_ASSERT_TRUE(checkCalibration(16, 2) == CalibrationProblem::None);
        TEST_ASSERT_TRUE(checkCalibration(12, 10) == CalibrationProblem::None);
        TEST_ASSERT_TRUE(checkCalibration(NAN, 2) == CalibrationProblem::SensorError);
        TEST_ASSERT_TRUE(checkCalibration(16, INFINITY) == CalibrationProblem::SensorError);
        // Nothing in front of the sensor reads about 22 cm.
        TEST_ASSERT_TRUE(checkCalibration(21.9f, 2) == CalibrationProblem::OutOfRange);
        TEST_ASSERT_TRUE(checkCalibration(16, 1) == CalibrationProblem::OutOfRange);
        TEST_ASSERT_TRUE(checkCalibration(2, 16) == CalibrationProblem::Reversed);
        TEST_ASSERT_TRUE(checkCalibration(10, 10) == CalibrationProblem::TooShort);
        TEST_ASSERT_TRUE(checkCalibration(10, 11) == CalibrationProblem::TooShort);
        TEST_ASSERT_TRUE(checkCalibration(11.9f, 10) == CalibrationProblem::TooShort);
    }

    void test_bounded_text_and_pass_fail_types() {
        auto doc = validSession();
        doc["name"] = "";
        TEST_ASSERT_TRUE(valid(doc));
        doc["name"] = std::string(512, 'a');
        TEST_ASSERT_TRUE(valid(doc));
        doc["name"] = std::string(513, 'a');
        TEST_ASSERT_FALSE(valid(doc));
        doc["name"] = 5;
        TEST_ASSERT_FALSE(valid(doc));
        doc.remove("name");
        TEST_ASSERT_FALSE(valid(doc));
        doc = validSession();
        auto passFail = doc["segments"][0]["passFail"].to<JsonObject>();
        passFail["enabled"] = false;
        passFail["threshold"] = 100;
        passFail["failureText"] = nullptr;
        TEST_ASSERT_TRUE(valid(doc));
        passFail["enabled"] = "false";
        TEST_ASSERT_FALSE(valid(doc));
        passFail["enabled"] = false;
        passFail["threshold"] = 101;
        TEST_ASSERT_FALSE(valid(doc));
    }

    void test_countdown_snapshot_survives_session_reallocation() {
        struct TestSegment {
            uint16_t idx;
            std::string name;
        };
        std::vector<TestSegment> source = {{0, std::string(128, 'a')}};
        const auto snapshot = copySegmentByIdx(source, 0);
        TEST_ASSERT_TRUE(snapshot.has_value());
        source.clear();
        source.shrink_to_fit();
        for (int index = 0; index < 1000; ++index)
            source.push_back(
                {static_cast<uint16_t>(index), std::string(256, 'b')});
        TEST_ASSERT_EQUAL_STRING(std::string(128, 'a').c_str(),
                                 snapshot->name.c_str());
        TEST_ASSERT_FALSE(copySegmentByIdx(source, 1001).has_value());
        TEST_ASSERT_FALSE(
            copySegmentByIdx(std::vector<TestSegment>{}, 0).has_value());
    }
    std::string feedSample(const TrainingFeedSample &sample) {
        char json[TRAINING_FEED_SAMPLE_MAX_BYTES + 1];
        const size_t length =
            writeTrainingFeedSample(sample, json, sizeof(json));
        TEST_ASSERT_EQUAL(std::strlen(json), length);
        return json;
    }

    std::string feedEvent(const TrainingFeedEvent &event) {
        char json[TRAINING_FEED_EVENT_MAX_BYTES + 1];
        const size_t length = writeTrainingFeedEvent(event, json, sizeof(json));
        TEST_ASSERT_EQUAL(std::strlen(json), length);
        return json;
    }

    void test_training_feed_depth_scale() {
        // Distances are from the sensor: the tip is farther than the deep end.
        TEST_ASSERT_EQUAL(0, trainingFeedScale(16.0f, 16.0f, 2.0f));
        TEST_ASSERT_EQUAL(1000, trainingFeedScale(2.0f, 16.0f, 2.0f));
        TEST_ASSERT_EQUAL(500, trainingFeedScale(9.0f, 16.0f, 2.0f));
        TEST_ASSERT_EQUAL(734, trainingFeedScale(5.724f, 16.0f, 2.0f));
        // Readings beyond either end stay on the same scale.
        TEST_ASSERT_EQUAL(-429, trainingFeedScale(22.0f, 16.0f, 2.0f));
        TEST_ASSERT_EQUAL(1143, trainingFeedScale(0.0f, 16.0f, 2.0f));
        TEST_ASSERT_EQUAL(TRAINING_FEED_SCALE_LIMIT,
                          trainingFeedScale(1.8f, 21.5f, 21.4f));
        TEST_ASSERT_EQUAL(-TRAINING_FEED_SCALE_LIMIT,
                          trainingFeedScale(22.0f, 4.0f, 3.9f));
        const float infinity = std::numeric_limits<float>::infinity();
        const float nan = std::numeric_limits<float>::quiet_NaN();
        for (const float unusable : {infinity, -infinity, nan}) {
            TEST_ASSERT_EQUAL(TRAINING_FEED_NO_VALUE,
                              trainingFeedScale(unusable, 16.0f, 2.0f));
            TEST_ASSERT_EQUAL(TRAINING_FEED_NO_VALUE,
                              trainingFeedScale(9.0f, unusable, 2.0f));
            TEST_ASSERT_EQUAL(TRAINING_FEED_NO_VALUE,
                              trainingFeedScale(9.0f, 16.0f, unusable));
        }
        TEST_ASSERT_EQUAL(TRAINING_FEED_NO_VALUE,
                          trainingFeedScale(9.0f, 2.0f, 2.0f));
        TEST_ASSERT_EQUAL(TRAINING_FEED_NO_VALUE,
                          trainingFeedScale(9.0f, 2.0f, 16.0f));
    }

    void test_training_feed_sample_shape() {
        TrainingFeedSample sample;
        sample.segment = 2;
        TEST_ASSERT_EQUAL_STRING(
            "{\"segment\":2,\"depth\":null,\"posState\":null,"
            "\"trainState\":null,\"strokes\":null,\"progress\":null,"
            "\"grade\":null,\"windowStart\":null,\"windowEnd\":null}",
            feedSample(sample).c_str());

        sample.available = true;
        sample.depth = trainingFeedScale(5.724f, 16.0f, 2.0f);
        sample.positionState = 2;
        sample.trainingState = 1;
        sample.strokes = 14;
        sample.progress = 0.7f;
        sample.grade = 87;
        sample.windowStart = trainingFeedScale(7.5f, 16.0f, 2.0f);
        sample.windowEnd = trainingFeedScale(4.5f, 16.0f, 2.0f);
        const std::string running = feedSample(sample);
        TEST_ASSERT_EQUAL_STRING(
            "{\"segment\":2,\"depth\":0.734,\"posState\":2,\"trainState\":1,"
            "\"strokes\":14,\"progress\":0.700,\"grade\":87,"
            "\"windowStart\":0.607,\"windowEnd\":0.821}",
            running.c_str());

        JsonDocument parsed;
        TEST_ASSERT_TRUE(deserializeJson(parsed, running) ==
                         DeserializationError::Ok);
        TEST_ASSERT_EQUAL(2, parsed["segment"].as<int>());
        TEST_ASSERT_FLOAT_WITHIN(0.0005f, 0.734f, parsed["depth"].as<float>());
        TEST_ASSERT_EQUAL(87, parsed["grade"].as<int>());

        // A freeform segment has no positional window.
        sample.windowStart = TRAINING_FEED_NO_VALUE;
        sample.windowEnd = TRAINING_FEED_NO_VALUE;
        JsonDocument freeform;
        TEST_ASSERT_TRUE(deserializeJson(freeform, feedSample(sample)) ==
                         DeserializationError::Ok);
        TEST_ASSERT_TRUE(freeform["windowStart"].isNull());
        TEST_ASSERT_TRUE(freeform["windowEnd"].isNull());
        TEST_ASSERT_FALSE(freeform["depth"].isNull());
    }

    void test_training_feed_sample_fits_one_notification() {
        // RadBLE adds a 20-byte header, and a central at ATT MTU 185 receives
        // at most 182 bytes per notification.
        constexpr size_t STREAM_HEADER_BYTES = 20;
        constexpr size_t MTU_185_VALUE_BYTES = 182;
        TEST_ASSERT_TRUE(STREAM_HEADER_BYTES + TRAINING_FEED_SAMPLE_MAX_BYTES <=
                         MTU_185_VALUE_BYTES);

        TrainingFeedSample widest;
        widest.segment = std::numeric_limits<uint16_t>::max();
        widest.available = true;
        widest.depth = -TRAINING_FEED_SCALE_LIMIT;
        widest.positionState = 2;
        widest.trainingState = 3;
        widest.strokes = std::numeric_limits<uint32_t>::max();
        widest.progress = 1.0f;
        widest.grade = 100;
        widest.windowStart = -TRAINING_FEED_SCALE_LIMIT;
        widest.windowEnd = -TRAINING_FEED_SCALE_LIMIT;
        const std::string json = feedSample(widest);
        TEST_ASSERT_EQUAL_STRING(
            "{\"segment\":65535,\"depth\":-9.999,\"posState\":2,"
            "\"trainState\":3,\"strokes\":4294967295,\"progress\":1.000,"
            "\"grade\":100,\"windowStart\":-9.999,\"windowEnd\":-9.999}",
            json.c_str());
        TEST_ASSERT_EQUAL(150, json.size());

        // No field value, valid or not, makes the sample longer.
        const int extremes[] = {std::numeric_limits<int>::min() + 1,
                                -TRAINING_FEED_SCALE_LIMIT - 1,
                                -1,
                                0,
                                TRAINING_FEED_SCALE_LIMIT + 1,
                                std::numeric_limits<int>::max(),
                                TRAINING_FEED_NO_VALUE};
        const float ratios[] = {-1.0f,
                                0.0f,
                                0.9996f,
                                2.0f,
                                std::numeric_limits<float>::infinity(),
                                std::numeric_limits<float>::quiet_NaN()};
        size_t longest = 0;
        for (const int scale : extremes)
            for (const int state : extremes)
                for (const float ratio : ratios)
                    for (const bool available : {false, true}) {
                        TrainingFeedSample sample = widest;
                        sample.available = available;
                        sample.depth = scale;
                        sample.windowStart = scale;
                        sample.windowEnd = scale;
                        sample.positionState = state;
                        sample.trainingState = state;
                        sample.grade = state;
                        sample.progress = ratio;
                        const std::string candidate = feedSample(sample);
                        JsonDocument parsed;
                        TEST_ASSERT_TRUE(deserializeJson(parsed, candidate) ==
                                         DeserializationError::Ok);
                        if (candidate.size() > longest)
                            longest = candidate.size();
                    }
        TEST_ASSERT_EQUAL(150, longest);
        TEST_ASSERT_TRUE(longest <= TRAINING_FEED_SAMPLE_MAX_BYTES);

        // A buffer that is too small reports failure instead of truncating.
        char small[100];
        TEST_ASSERT_EQUAL(
            0, writeTrainingFeedSample(widest, small, sizeof(small)));
        TEST_ASSERT_EQUAL(0, writeTrainingFeedSample(widest, small, 0));
    }

    void test_training_feed_events() {
        TrainingFeedEvent started;
        started.kind = TrainingFeedEvent::SegmentStarted;
        started.segment = 1;
        started.type = 3;
        started.target = 12;
        TEST_ASSERT_EQUAL_STRING(
            "{\"event\":\"segment.started\",\"segment\":1,\"type\":3,"
            "\"target\":12}",
            feedEvent(started).c_str());

        TrainingFeedEvent completed;
        completed.kind = TrainingFeedEvent::SegmentCompleted;
        completed.segment = 1;
        completed.grade = 62;
        TEST_ASSERT_EQUAL_STRING(
            "{\"event\":\"segment.completed\",\"segment\":1,\"grade\":62,"
            "\"passed\":null,\"strikes\":0}",
            feedEvent(completed).c_str());
        completed.passed = 0;
        completed.strikes = 2;
        TEST_ASSERT_EQUAL_STRING(
            "{\"event\":\"segment.completed\",\"segment\":1,\"grade\":62,"
            "\"passed\":false,\"strikes\":2}",
            feedEvent(completed).c_str());
        completed.passed = 1;
        completed.strikes = 0;
        JsonDocument parsed;
        TEST_ASSERT_TRUE(deserializeJson(parsed, feedEvent(completed)) ==
                         DeserializationError::Ok);
        TEST_ASSERT_EQUAL_STRING("segment.completed",
                                 parsed["event"].as<const char *>());
        TEST_ASSERT_TRUE(parsed["passed"].as<bool>());

        // The widest values of every field stay within the event limit.
        started.segment = completed.segment =
            std::numeric_limits<uint16_t>::max();
        started.type = std::numeric_limits<uint8_t>::max();
        started.target = std::numeric_limits<uint32_t>::max();
        completed.grade = std::numeric_limits<uint8_t>::max();
        completed.passed = 0;
        completed.strikes = std::numeric_limits<uint8_t>::max();
        TEST_ASSERT_EQUAL(74, feedEvent(started).size());
        TEST_ASSERT_EQUAL_STRING(
            "{\"event\":\"segment.completed\",\"segment\":65535,"
            "\"grade\":100,\"passed\":false,\"strikes\":255}",
            feedEvent(completed).c_str());
        TEST_ASSERT_TRUE(feedEvent(completed).size() <=
                         TRAINING_FEED_EVENT_MAX_BYTES);
    }
}  // namespace

void test_live_adjust_keeps_values_inside_the_segment() {
    // Tip 16 cm, calibrated deep 4 cm, 0.8 cm kept below the tip.
    const LiveAdjustLimits limits{16.0f, 4.0f, 0.8f};

    const LiveAdjustValues inside = clampLiveAdjust({8.0f, 3.0f, 40.0f}, limits);
    TEST_ASSERT_EQUAL_FLOAT(8.0f, inside.endPosition);
    TEST_ASSERT_EQUAL_FLOAT(3.0f, inside.targetWindow);
    TEST_ASSERT_EQUAL_FLOAT(40.0f, inside.trainingSpeed);

    // Never deeper than the deepest position.
    TEST_ASSERT_EQUAL_FLOAT(
        4.0f, clampLiveAdjust({1.0f, 3.0f, 40.0f}, limits).endPosition);
    // The block and the shortest stroke always fit below the tip.
    TEST_ASSERT_EQUAL_FLOAT(
        12.2f, clampLiveAdjust({15.9f, 3.0f, 40.0f}, limits).endPosition);
    // Block width stays between its minimum and the whole travel.
    TEST_ASSERT_EQUAL_FLOAT(
        LIVE_ADJUST_MIN_WINDOW_CM,
        clampLiveAdjust({8.0f, 0.0f, 40.0f}, limits).targetWindow);
    const LiveAdjustValues wide = clampLiveAdjust({8.0f, 50.0f, 40.0f}, limits);
    TEST_ASSERT_EQUAL_FLOAT(11.2f, wide.targetWindow);
    TEST_ASSERT_EQUAL_FLOAT(4.0f, wide.endPosition);
    // Speed stays in the range session validation allows.
    TEST_ASSERT_EQUAL_FLOAT(
        LIVE_ADJUST_MIN_SPEED,
        clampLiveAdjust({8.0f, 3.0f, -5.0f}, limits).trainingSpeed);
    TEST_ASSERT_EQUAL_FLOAT(
        LIVE_ADJUST_MAX_SPEED,
        clampLiveAdjust({8.0f, 3.0f, 5000.0f}, limits).trainingSpeed);
}

void test_live_adjust_rejects_non_finite_values() {
    TEST_ASSERT_TRUE(liveAdjustFinite({8.0f, 3.0f, 40.0f}));
    TEST_ASSERT_FALSE(liveAdjustFinite(
        {std::numeric_limits<float>::quiet_NaN(), 3.0f, 40.0f}));
    TEST_ASSERT_FALSE(liveAdjustFinite(
        {8.0f, std::numeric_limits<float>::infinity(), 40.0f}));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_valid_modes_and_training_types);
    RUN_TEST(test_invalid_segment_indices_are_rejected);
    RUN_TEST(test_empty_unknown_and_malformed_segments_are_rejected);
    RUN_TEST(test_finite_and_overflow_boundaries);
    RUN_TEST(test_fractional_dashboard_values_use_parsed_integers);
    RUN_TEST(test_dashboard_pagination_and_complete_limits);
    RUN_TEST(test_calibration_override_preserves_existing_dashboard_format);
    RUN_TEST(test_calibration_range_checks);
    RUN_TEST(test_bounded_text_and_pass_fail_types);
    RUN_TEST(test_countdown_snapshot_survives_session_reallocation);
    RUN_TEST(test_training_feed_depth_scale);
    RUN_TEST(test_training_feed_sample_shape);
    RUN_TEST(test_training_feed_sample_fits_one_notification);
    RUN_TEST(test_training_feed_events);
    RUN_TEST(test_live_adjust_keeps_values_inside_the_segment);
    RUN_TEST(test_live_adjust_rejects_non_finite_values);
    return UNITY_END();
}
