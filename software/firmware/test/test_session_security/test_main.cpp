#include <unity.h>

#include <limits>
#include <string>

#include "SessionSnapshot.h"
#include "SessionValidation.h"

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
        // A tip beyond the sensor's reach reads about 22 cm. It counts as
        // the longest range, as it did before the range check existed.
        TEST_ASSERT_TRUE(checkCalibration(22.05f, 6) == CalibrationProblem::None);
        TEST_ASSERT_TRUE(checkCalibration(21.9f, 2) == CalibrationProblem::None);
        TEST_ASSERT_EQUAL_FLOAT(CALIBRATION_MAX_CM, calibrationTipCm(22.05f));
        TEST_ASSERT_EQUAL_FLOAT(16.0f, calibrationTipCm(16.0f));
        // What the dashboard stores for that calibration is still usable.
        TEST_ASSERT_TRUE(checkCalibration(CALIBRATION_MAX_CM, 6) == CalibrationProblem::None);
        // Nothing in front of the sensor on either press.
        TEST_ASSERT_TRUE(checkCalibration(22.05f, 22.05f) == CalibrationProblem::OutOfRange);
        TEST_ASSERT_TRUE(checkCalibration(21.0f, 22.05f) == CalibrationProblem::OutOfRange);
        TEST_ASSERT_TRUE(checkCalibration(16, 1) == CalibrationProblem::OutOfRange);
        // Deep first, then pulled out past the sensor's reach.
        TEST_ASSERT_TRUE(checkCalibration(6, 22.05f) == CalibrationProblem::Reversed);
        // A far tip still needs enough movement.
        TEST_ASSERT_TRUE(checkCalibration(22.05f, 20) == CalibrationProblem::TooShort);
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
}  // namespace

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
    return UNITY_END();
}
