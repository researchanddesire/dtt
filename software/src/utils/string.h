#ifndef STRING_UTILS_H
#define STRING_UTILS_H

#include <Arduino.h>

/**
 * Converts a float to scientific notation string
 * Uses only C++17 Arduino-compatible methods, no external libraries
 *
 * @param value The float value to convert
 * @param precision Number of decimal places (default: 6)
 * @return String in scientific notation (e.g., "1.23e+04")
 */
String floatToScientificNotation(float value, int precision = 6);

/**
 * Test function to demonstrate the scientific notation conversion
 * @return String containing test results
 */
String testScientificNotation();

#endif  // STRING_UTILS_H
