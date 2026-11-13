#include "input.h"

#include <Arduino.h>
#include <driver/adc.h>

#include <mutex>

#include "services/board.hpp"
#include "wifiSettings.h"

// Arduino 2's analogRead() re-attaches and reconfigures the pin on every call,
// which takes 13-18 ms per read in this build (a direct read takes ~0.2 ms)
// and capped play sampling near 20 Hz. board.hpp attaches the ADC pins once
// with their width and attenuation, so read the configured ADC1 channel.
int readAdc(const int pin) {
    const int8_t channel = digitalPinToAnalogChannel(pin);
    if (channel < 0 || channel >= SOC_ADC_MAX_CHANNEL_NUM) return analogRead(pin);
    return adc1_get_raw(static_cast<adc1_channel_t>(channel));
}

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
    double value = readAdc(pin);
    double last_value = value;
    const float weighting =
        2 /
        static_cast<float>(samples);  // weighting used for fake running average
    float analog_sum = 0;
    float number_samples = 0;
    const unsigned long startMillis = millis();
    int delta = static_cast<int>(millis() - startMillis);
    while (delta < samples) {
        const auto analog = static_cast<float>(readAdc(pin));
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

namespace {
// The header bar and RAD BLE both poll battery and 5 V state. A battery read
// samples for ~20 ms and a 5 V probe takes 100 ms, so callers share one
// reading per second. The probe reconfigures its pin: two at once corrupted
// each other's result, flipping the charging icon and holding the display.
constexpr uint32_t POWER_READING_MAX_AGE_MS = 1000;
std::mutex batteryMutex;
std::mutex chargingMutex;
bool batteryValid = false;
uint32_t batteryReadAt = 0;
float batteryAnalog = 0;
bool chargingValid = false;
uint32_t chargingReadAt = 0;
bool charging = false;
}  // namespace

float getBatteryVoltage() {
    std::lock_guard<std::mutex> lock(batteryMutex);
    if (!batteryValid || millis() - batteryReadAt >= POWER_READING_MAX_AGE_MS) {
        getAnalog(BATTERY_SENSE_INPUT, 10);  // settle, as getAnalogVoltage does
        batteryAnalog = getAnalog(BATTERY_SENSE_INPUT, 10);
        batteryReadAt = millis();
        batteryValid = true;
    }
    // Calibration can change at runtime; apply it to every cached reading.
    return 2 * (batteryAnalog / global_voltageCalibrationInverseSlope +
                global_voltageCalibrationOffset);
}

bool checkIfCharging() {
    std::lock_guard<std::mutex> lock(chargingMutex);
    if (chargingValid && millis() - chargingReadAt < POWER_READING_MAX_AGE_MS)
        return charging;

    pinMode(CHECK_5V_INPUT, INPUT_PULLDOWN);
    vTaskDelay(pdMS_TO_TICKS(100));

    charging = digitalRead(CHECK_5V_INPUT) == HIGH;

    pinMode(CHECK_5V_INPUT, INPUT);
    pinMode(CHECK_5V_INPUT, OUTPUT);
    chargingReadAt = millis();
    chargingValid = true;
    return charging;
}
