#include "string.h"

// Arduino.h already provides abs(), floor(), ceil(), and pow() functions
// We'll use pow(10, exponent) instead of custom pow10()

String floatToScientificNotation(float value, int precision) {
    // Handle special cases
    if (value == 0.0f) {
        return "0.0e+00";
    }

    // Note: Arduino doesn't have isnan/isinf, so we'll handle these cases
    // differently For very large or very small values, we'll just process them
    // normally

    // Handle negative numbers
    bool isNegative = (value < 0);
    if (isNegative) {
        value = -value;
    }

    // Find the exponent
    int exponent = 0;
    if (value >= 10.0f) {
        while (value >= 10.0f) {
            value /= 10.0f;
            exponent++;
        }
    } else if (value < 1.0f && value > 0.0f) {
        while (value < 1.0f) {
            value *= 10.0f;
            exponent--;
        }
    }

    // Round to specified precision
    float multiplier = pow(10.0f, precision);
    value = value * multiplier;
    value = (value >= 0) ? (value + 0.5f) : (value - 0.5f);
    value = (float)((int)value);
    value = value / multiplier;

    // Handle rounding edge case that might push value to 10
    if (value >= 10.0f) {
        value /= 10.0f;
        exponent++;
    }

    // Convert to string
    String result = "";

    // Add negative sign if needed
    if (isNegative) {
        result += "-";
    }

    // Convert the mantissa to string
    // First, get the integer part
    int intPart = (int)value;
    result += String(intPart);

    // Add decimal point
    result += ".";

    // Get the fractional part
    float fractional = value - (float)intPart;

    // Convert fractional part to string with specified precision
    for (int i = 0; i < precision; i++) {
        fractional *= 10.0f;
        int digit = (int)fractional;
        result += String(digit);
        fractional -= (float)digit;
    }

    // Add exponent
    result += "e";
    if (exponent >= 0) {
        result += "+";
    }
    result += String(exponent);

    return result;
}

String testScientificNotation() {
    String result = "Scientific Notation Tests:\n";

    // Test various values
    float testValues[] = {123.456f,    0.00123f, 1000000.0f,
                          -0.0000456f, 1.0f,     0.0f};

    for (int i = 0; i < 6; i++) {
        result += String(testValues[i]) + " -> " +
                  floatToScientificNotation(testValues[i]) + "\n";
    }

    // Test with different precision
    result += "\nPrecision tests for 3.14159:\n";
    for (int p = 1; p <= 5; p++) {
        result += "Precision " + String(p) + ": " +
                  floatToScientificNotation(3.14159f, p) + "\n";
    }

    return result;
}
