#ifndef BOARD_HPP
#define BOARD_HPP

#include <Arduino.h>

static auto TAG = "BOARD";

// Pin definitions
constexpr int BUTTON_IN = 35;
constexpr int TEST_BUTTON_IN = 35;
constexpr int SENSOR_INPUT = 32;
constexpr int BATTERY_SENSE_INPUT = 34;
constexpr int PUNISHMENT_OUTPUT = 25;
constexpr int REWARD_OUTPUT = 26;
constexpr int CHECK_5V_INPUT = 14;

// ADC resolution
constexpr int ADC_RESOLUTION = 11;

// Board initialization function
inline void initBoard() {
    ESP_LOGI(TAG, "Initializing board pins...");
    // gpio_config logs every pinMode at INFO; the 5 V probe reconfigures its
    // pin each check, and each line holds the console for ~9 ms.
    esp_log_level_set("gpio", ESP_LOG_WARN);
    pinMode(SENSOR_INPUT, INPUT);
    adcAttachPin(SENSOR_INPUT);
    analogReadResolution(
        ADC_RESOLUTION);  // Default of 12 is not very linear. Recommended to
    // use 10 or 11 depending on needed resolution.
    analogSetAttenuation(ADC_11db);  // Default is 11db which is very noisy.
    // Recommended to use 2.5 or 6.

    pinMode(BATTERY_SENSE_INPUT, INPUT);
    adcAttachPin(BATTERY_SENSE_INPUT);
    analogReadResolution(
        ADC_RESOLUTION);  // Default of 12 is not very linear. Recommended to
    // use 10 or 11 depending on needed resolution.
    analogSetAttenuation(ADC_11db);

    delay(20);

    pinMode(PUNISHMENT_OUTPUT, OUTPUT);
    pinMode(REWARD_OUTPUT, OUTPUT);
    pinMode(CHECK_5V_INPUT, INPUT_PULLDOWN);
    pinMode(CHECK_5V_INPUT, INPUT);
    pinMode(CHECK_5V_INPUT, OUTPUT);
    ESP_LOGI(TAG, "Board initialization complete.");
}

#endif  // BOARD_HPP
