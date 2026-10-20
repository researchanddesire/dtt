#ifndef EASING_H
#define EASING_H

#include <Arduino.h>

/**
 * Easing functions for smooth animations and transitions
 */

/**
 * Ease in-out sine function
 * Provides smooth acceleration and deceleration
 * @param t Progress value between 0.0 and 1.0
 * @return Eased progress value between 0.0 and 1.0
 */
double easeInOutSine(const double t);

/**
 * Alias for easeInOutSine for backward compatibility
 * @param t Progress value between 0.0 and 1.0
 * @return Eased progress value between 0.0 and 1.0
 */
double ease(const double t);

#endif  // EASING_H
