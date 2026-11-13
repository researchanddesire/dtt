#ifndef INPUT_H_
#define INPUT_H_

/**
 * @brief Returns distance sensor value in cm
 * @param samples time in ms to measure for
 */
float getDistance(int samples);
int readAdc(int pin);
float getAnalog(int pin, int samples);
float getAnalogVoltage(int pin, int samples);
float getBatteryVoltage();
bool checkIfCharging();
extern float global_voltageCalibrationInverseSlope;
extern float global_voltageCalibrationOffset;
#endif
