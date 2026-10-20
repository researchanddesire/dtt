#include "test_helpers.h"

// Layer 7: Error Paths
//
// Tests verify the device handles connectivity failures gracefully by
// disconnecting WiFi and calling HTTP functions directly. This simulates
// the real-world scenario of WiFi dropping mid-session.
//
// WiFi is reconnected at the end so subsequent test runs are not affected.

// --- Test 1: Health check fails without WiFi ---

static void test_health_check_no_wifi() {
    WiFi.disconnect(true);
    vTaskDelay(pdMS_TO_TICKS(1000));

    Serial.printf("[INFO] WiFi status after disconnect: %d\n", WiFi.status());

    healthCheckPassed = true;  // set true so we can verify it flips
    healthCheckWifi();

    Serial.printf("[INFO] healthCheckPassed: %s\n",
                  healthCheckPassed ? "true" : "false");

    TEST_ASSERT_FALSE_MESSAGE(
        healthCheckPassed,
        "healthCheckPassed should be false when WiFi is disconnected");
}

// --- Test 2: Pairing check assumes paired without WiFi ---
// The firmware intentionally assumes paired when offline so the user can
// still train with cached data. getIsPaired() sets isPaired = true when
// WiFi is disconnected.

static void test_pairing_check_no_wifi() {
    dashboardState.isPaired = false;  // set false so we can verify it flips
    getIsPaired();

    Serial.printf("[INFO] isPaired (no WiFi): %s\n",
                  dashboardState.isPaired ? "true" : "false");

    TEST_ASSERT_TRUE_MESSAGE(
        dashboardState.isPaired,
        "isPaired should be true when WiFi is disconnected (firmware "
        "assumes paired for offline training)");
}

// --- Test 3: postJson fails without WiFi ---

static void test_post_json_no_wifi() {
    JsonDocument doc;
    doc["trainerId"] = trainerId;
    doc["pageIdx"] = 0;
    doc["sessionId"] = session.id;

    String payload;
    int code = postJson("/get-settings", doc, &payload);

    Serial.printf("[INFO] postJson response code (no WiFi): %d\n", code);

    TEST_ASSERT_NOT_EQUAL_MESSAGE(
        200, code,
        "postJson should not return 200 when WiFi is disconnected");
}

// --- Test 4: Calibration upload fails without WiFi ---

static void test_calibration_upload_no_wifi() {
    bool calibratedBefore = session.isCalibrated;

    sendCalibrationToBackend(3.0f, 15.0f);

    Serial.println(
        "[INFO] sendCalibrationToBackend with no WiFi — no crash");

    TEST_ASSERT_EQUAL_MESSAGE(
        calibratedBefore, session.isCalibrated,
        "Local calibration state should be unaffected by upload failure");
}

// --- Test 5: Results save fails without WiFi ---

static void test_results_save_no_wifi() {
    JsonDocument doc;
    doc["trainerId"] = trainerId;
    doc["test"] = true;

    String payload;
    int code = postJson("/training-completed", doc, &payload);

    Serial.printf("[INFO] training-completed response code (no WiFi): %d\n",
                  code);

    TEST_ASSERT_NOT_EQUAL_MESSAGE(
        200, code,
        "postJson should not return 200 when WiFi is disconnected");
}

// --- Test 6: WiFi reconnects after disconnect ---

static void test_wifi_reconnects() {
#ifdef WIFI_SSID
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
#else
    WiFi.begin();
#endif

    int elapsed = 0;
    while (WiFi.status() != WL_CONNECTED && elapsed < 15000) {
        vTaskDelay(pdMS_TO_TICKS(500));
        elapsed += 500;
    }

    Serial.printf("[INFO] WiFi status after reconnect: %d, waited %dms\n",
                  WiFi.status(), elapsed);

    TEST_ASSERT_EQUAL_MESSAGE(
        WL_CONNECTED, WiFi.status(),
        "WiFi should reconnect within 15s after disconnect");
}

// --- Test 7: Health check recovers after WiFi reconnect ---

static void test_health_check_recovers() {
    healthCheckPassed = false;
    healthCheckWifi();

    Serial.printf("[INFO] healthCheckPassed after recovery: %s\n",
                  healthCheckPassed ? "true" : "false");

    TEST_ASSERT_TRUE_MESSAGE(
        healthCheckPassed,
        "healthCheckPassed should be true after WiFi reconnects");
}

// --- Registration ---

void register_error_path_tests() {
    RUN_TEST(test_health_check_no_wifi);
    RUN_TEST(test_pairing_check_no_wifi);
    RUN_TEST(test_post_json_no_wifi);
    RUN_TEST(test_calibration_upload_no_wifi);
    RUN_TEST(test_results_save_no_wifi);
    RUN_TEST(test_wifi_reconnects);
    RUN_TEST(test_health_check_recovers);
}
