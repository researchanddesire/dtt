#ifndef LEDS_SERVICE_H
#define LEDS_SERVICE_H

#define LED_YELLOW 66
#define LED_RED 0
#define LED_GREEN 96
#define LED_LOGO_BLUE 150
#define LED_BLUE 160
#define LED_MAGENTA 224

#ifdef PROVISION

#include <stdint.h>
inline void initFastLEDs() {}
inline void setLed(uint8_t, uint8_t = 255, uint16_t = 250) {}
inline void setLedOff() {}

#else

#include <FastLED.h>

#include "handles.h"

#define LED_PIN 17

#define BRIGHTNESS 255
#define LED_TYPE WS2811
#define COLOR_ORDER GRB

#define NUM_LEDS 3

extern CRGB leds[NUM_LEDS];
extern float ledPaceSpeedRpm;

void initFastLEDs();

void setLed(uint8_t color_value, uint8_t brightness = 255,
            uint16_t duration_ms = 250);
void setLedOff();

#endif  // PROVISION

#endif  // LEDS_SERVICE_H
