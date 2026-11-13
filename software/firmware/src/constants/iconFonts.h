#ifndef ICON_FONTS_H
#define ICON_FONTS_H

#include <U8g2lib.h>
#include <Arduino.h>

extern const uint8_t wifiFont[126];
extern const uint8_t timeoutFont[113];
extern const uint8_t funIconsFont[14593];

// Get font pointer by name (streamline, siji, unifont)
const uint8_t* getFontByName(const String& fontName);

#endif  // ICON_FONTS_H