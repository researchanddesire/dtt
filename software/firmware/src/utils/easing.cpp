#include "easing.h"

/**
 * Ease in-out sine function
 * Provides smooth acceleration and deceleration
 * @param t Progress value between 0.0 and 1.0
 * @return Eased progress value between 0.0 and 1.0
 */
double easeInOutSine(const double t) {
    return 0.5 * (1 + sin(3.1415926 * (t - 0.5)));
}

/**
 * Alias for easeInOutSine for backward compatibility
 * @param t Progress value between 0.0 and 1.0
 * @return Eased progress value between 0.0 and 1.0
 */
double ease(const double t) { return easeInOutSine(t); }
