#include "input.h"

#include <Arduino.h>

#include "services/board.hpp"
#include "wifiSettings.h"

float getDistance(const int samples) {
    // returns distance in cm
    constexpr float cal_slope = 5.022;
    constexpr float cal_exp = -1.229;
    double analog = 0;

    analog = static_cast<double>(getAnalog(SENSOR_INPUT, samples));
    analog = analog * 3.3 / pow(2, ADC_RESOLUTION) + 0.145;
    if (analog > 2.3) {
        analog = 2.3;
    }
    if (analog < 0.3) {
        analog = 0.3;
    }
    const double distance = cal_slope * (pow(analog, cal_exp));
    return static_cast<float>(distance);
}

float getAnalog(const int pin, const int samples) {
    double value = analogRead(pin);
    double last_value = value;
    const float weighting =
        2 /
        static_cast<float>(samples);  // weighting used for fake running average
    float analog_sum = 0;
    float number_samples = 0;
    const unsigned long startMillis = millis();
    int delta = static_cast<int>(millis() - startMillis);
    while (delta < samples) {
        const auto analog = static_cast<float>(analogRead(pin));
        analog_sum = analog + analog_sum;
        value = (1.0 - weighting) * last_value + weighting * analog;
        last_value = value;
        number_samples += 1;
        delta = static_cast<int>(millis() - startMillis);
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    value = analog_sum / number_samples;

    return static_cast<float>(value);
}

float global_voltageCalibrationInverseSlope = 630;
float global_voltageCalibrationOffset = 0.15;

float getAnalogVoltage(const int pin, const int samples) {
    float analogVoltage = 0;
    getAnalog(pin, samples);
    analogVoltage =
        getAnalog(pin, samples) / global_voltageCalibrationInverseSlope +
        global_voltageCalibrationOffset;

    delay(1);  // I honestly don't know why this is here, used to be 10ms.
    return analogVoltage;
}

float getBatteryVoltage() {
    float batteryVoltage = 0;
    batteryVoltage = 2 * getAnalogVoltage(BATTERY_SENSE_INPUT, 10);
    return batteryVoltage;
}

bool checkIfCharging() {
    pinMode(CHECK_5V_INPUT, INPUT_PULLDOWN);
    vTaskDelay(pdMS_TO_TICKS(100));

    const bool charging = digitalRead(CHECK_5V_INPUT) == HIGH;

    pinMode(CHECK_5V_INPUT, INPUT);
    pinMode(CHECK_5V_INPUT, OUTPUT);
    return charging;
}
