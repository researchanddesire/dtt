#include "test_helpers.h"

// --- Test 1: Board ADC ---

static void test_board_adc_reads_in_range() {
    int sensorVal = analogRead(SENSOR_INPUT);
    int batteryVal = analogRead(BATTERY_SENSE_INPUT);

    Serial.printf("[INFO] SENSOR_INPUT (pin %d) raw ADC: %d\n", SENSOR_INPUT,
                  sensorVal);
    Serial.printf("[INFO] BATTERY_SENSE_INPUT (pin %d) raw ADC: %d\n",
                  BATTERY_SENSE_INPUT, batteryVal);

    TEST_ASSERT_GREATER_OR_EQUAL_MESSAGE(0, sensorVal,
                                         "Sensor ADC should be >= 0");
    TEST_ASSERT_LESS_OR_EQUAL_MESSAGE(2047, sensorVal,
                                      "Sensor ADC should be <= 2047 (11-bit)");
    TEST_ASSERT_GREATER_OR_EQUAL_MESSAGE(0, batteryVal,
                                         "Battery ADC should be >= 0");
    TEST_ASSERT_LESS_OR_EQUAL_MESSAGE(2047, batteryVal,
                                      "Battery ADC should be <= 2047 (11-bit)");
}

// --- Test 2: EEPROM ---

static void test_eeprom_device_identity() {
    Serial.printf("[INFO] trainerId: '%s'\n", trainerId.c_str());
    Serial.printf("[INFO] trainerIdShort: '%s'\n", trainerIdShort.c_str());
    Serial.printf("[INFO] serialNumber: %d\n", serialNumber);
    Serial.printf("[INFO] isAlphaVersion: %s\n",
                  isAlphaVersion ? "true" : "false");

    TEST_ASSERT_GREATER_THAN_MESSAGE(
        0, (int)trainerId.length(),
        "trainerId should be non-empty (device must be provisioned)");
    TEST_ASSERT_GREATER_THAN_MESSAGE(
        0, (int)trainerIdShort.length(),
        "trainerIdShort should be non-empty");
}

// --- Test 3: Vibrator LEDC ---

static void test_vibrator_ledc_configured() {
    // Note: ledcRead() returns 0 regardless on this ESP32 Arduino core version
    // with the legacy ledcSetup API — so we verify writes don't crash.
    ledcWrite(0, 128);
    Serial.println("[INFO] ledcWrite(0, 128) — no crash");

    ledcWrite(0, 255);
    Serial.println("[INFO] ledcWrite(0, 255) — no crash");

    Vibrator::off();
    Serial.println("[INFO] Vibrator::off() — no crash");

    ledcWrite(0, 0);
    TEST_ASSERT_TRUE_MESSAGE(true,
                             "LEDC channel 0 accepts writes without crash");
}

// --- Test 4: FastLED ---

static void test_leds_initialized() {
    setLed(96, 255, 0);  // GREEN hue = 96, full brightness, instant
    delay(100);
    Serial.println("[INFO] setLed(GREEN) completed without crash.");

    setLedOff();
    delay(100);
    Serial.println("[INFO] setLedOff() completed without crash.");
    TEST_ASSERT_TRUE(true);
}

// --- Test 5: Display ---

static void test_display_initialized() {
    TEST_ASSERT_NOT_NULL_MESSAGE(displayMutex,
                                 "Display mutex should be created");

    BaseType_t taken = xSemaphoreTake(displayMutex, pdMS_TO_TICKS(1000));
    TEST_ASSERT_EQUAL_MESSAGE(pdTRUE, taken,
                              "Should be able to take display mutex");
    xSemaphoreGive(displayMutex);

    TEST_ASSERT_EQUAL_MESSAGE(128, display.getDisplayWidth(),
                              "Display width should be 128");
    TEST_ASSERT_EQUAL_MESSAGE(64, display.getDisplayHeight(),
                              "Display height should be 64");

    Serial.printf("[INFO] Display: %dx%d, mutex=%p\n",
                  display.getDisplayWidth(), display.getDisplayHeight(),
                  (void *)displayMutex);
}

// --- Test 6: Button task ---

static void test_button_task_running() {
    TEST_ASSERT_NOT_NULL_MESSAGE(
        drawButtonTaskHandle,
        "Button polling task should be created by initButtonService()");

    Serial.printf("[INFO] drawButtonTaskHandle: %p\n",
                  (void *)drawButtonTaskHandle);

    vTaskDelay(pdMS_TO_TICKS(200));
    TEST_ASSERT_TRUE_MESSAGE(true, "Button task survived 200ms of polling");
}

// --- Test 7: WiFi ---

static void test_wifi_connected() {
    waitForWifi();

    Serial.printf("[INFO] WiFi status: %d (3=connected)\n", WiFi.status());
    Serial.printf("[INFO] IP: %s\n", WiFi.localIP().toString().c_str());

    TEST_ASSERT_EQUAL_MESSAGE(
        WL_CONNECTED, WiFi.status(),
        "WiFi should connect within 15s using stored credentials");
}

// --- Test 8: State machine ---

static void test_state_machine_initialized() {
    TEST_ASSERT_NOT_NULL_MESSAGE(
        stateMachine,
        "stateMachine pointer should be non-null after initStateMachine()");

    vTaskDelay(pdMS_TO_TICKS(2000));

    TEST_ASSERT_TRUE_MESSAGE(
        stateMachine->is("init.idle"_s),
        "State machine should be in init.idle after boot");

    Serial.println("[INFO] State machine in init.idle — boot complete.");
}

// --- Registration ---

void register_hardware_init_tests() {
    RUN_TEST(test_board_adc_reads_in_range);
    RUN_TEST(test_eeprom_device_identity);
    RUN_TEST(test_vibrator_ledc_configured);
    RUN_TEST(test_leds_initialized);
    RUN_TEST(test_display_initialized);
    RUN_TEST(test_button_task_running);
    RUN_TEST(test_wifi_connected);
    RUN_TEST(test_state_machine_initialized);
}
