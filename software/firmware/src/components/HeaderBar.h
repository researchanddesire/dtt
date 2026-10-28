#ifndef LOCKBOX_HEADERBAR_H
#define LOCKBOX_HEADERBAR_H

#pragma once

#include <Arduino.h>

#include "constants/iconFonts.h"

// Font glyph codes for icons
constexpr uint16_t GLYPH_BATTERY_LOW = 0xe236;
constexpr uint16_t GLYPH_BATTERY_MID = 0xe237;
constexpr uint16_t GLYPH_BATTERY_FULL = 0xe238;
constexpr uint16_t GLYPH_BATTERY_CHARGING = 0xe239;
constexpr uint16_t GLYPH_WIFI_OFF = 0xe218;
constexpr uint16_t GLYPH_WIFI_2_BARS = 0xe21a;

constexpr uint16_t GLYPH_TIMEOUT_100 = 9679;
constexpr uint16_t GLYPH_TIMEOUT_75 = 9685;
constexpr uint16_t GLYPH_TIMEOUT_50 = 9681;
constexpr uint16_t GLYPH_TIMEOUT_25 = 9684;
constexpr uint16_t GLYPH_TIMEOUT_0 = 9675;
constexpr uint16_t GLYPH_TIMEOUT_GHOST = 9676;

void headerBarTask(void* pvParameters);
void initHeaderBar();

#endif  // LOCKBOX_HEADERBAR_H
