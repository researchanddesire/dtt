#ifndef DISPLAY_H
#define DISPLAY_H

#include <U8g2lib.h>

#include "freertos/semphr.h"

#define SCREEN_WIDTH 128  // OLED display width, in pixels
#define SCREEN_HEIGHT 64  // OLED display height, in pixels
#define OLED_RESET U8X8_PIN_NONE

extern U8G2_SSD1306_128X64_NONAME_F_HW_I2C display;
extern SemaphoreHandle_t displayMutex;

extern long timeout;
extern bool showButton;

void initDisplay();

void clearTimeout();
void refreshTimeout();

void clearIcons();
void refreshIcons();

void clearHeader();
void clearFooter();
void clearPage(bool includeFooter = false, bool includeHeader = false);

void refreshHeader();

void refreshFooter();

void setHeader(String &text);
void setFooter(String &left, String &right);

void refreshPage(bool includeFooter = false, bool includeHeader = false);

int drawWrappedText(int x, int y, const String &text, bool center = false);
int calculateWrappedTextLines(int x, const String &text);

#endif  // DISPLAY_H