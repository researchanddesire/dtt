#ifndef TEXT_PAGES_H
#define TEXT_PAGES_H

#include <Arduino.h>

#include "constants/iconFonts.h"
#include "constants/strings.h"
#include "services/eeprom_service.h"
struct TextPage {
    String header = EMPTY_STRING;
    // https://github.com/olikraus/u8g2/wiki/fntgrpstreamline
    int icon = -1;
    String url = EMPTY_STRING;
    bool showTrainerId = false;
    String title = EMPTY_STRING;
    String tagline = EMPTY_STRING;
    String content = EMPTY_STRING;
    String leftFooter = EMPTY_STRING;
    String rightFooter = EMPTY_STRING;
    bool showButton = false;
    long timeout = 0;
    bool center = false;
    int x = 0;
    int y = 0;
};

// Wi-Fi Setup Page

static const TextPage wifiSetupPage = {.header = WIFI,
                                       .url = PAGE_WIFI_URL,
                                       .content = PAGE_WIFI_CONTENT,
                                       .rightFooter = PAGE_WIFI_RIGHT_FOOTER,
                                       .showButton = true,
                                       .center = true};

// Update Device Page

static const TextPage updateDevicePage = {.header = PAGE_UPDATING_HEADER,
                                          .icon = 282,
                                          .content = PAGE_UPDATING_CONTENT};

// Pairing Page

static const TextPage pairingPage = {.header = TRAINER_ID_LABEL,
                                     .url = PAGE_PAIRING_URL,
                                     .showTrainerId = true,
                                     .content = PAGE_PAIRING_CONTENT,
                                     .rightFooter = PAGE_PAIRING_RIGHT_FOOTER,
                                     .showButton = true,
                                     .center = true};

// Preflight Page
static const TextPage preflightPage = {
    .icon = 185, .content = PAGE_PREFLIGHT_CONTENT, .center = true, .y = 10};

// Fetching Settings Page
static const TextPage fetchingSettingsPage = {
    .icon = 297, .content = PAGE_FETCHING_CONTENT, .timeout = 60000};

// Bad Health Check Page
static const TextPage badHealthCheckPage = {
    .url = PAGE_BAD_HEALTH_CHECK_URL,
    .title = PAGE_BAD_HEALTH_CHECK_TITLE,
    .content = PAGE_BAD_HEALTH_CHECK_CONTENT,
    .rightFooter = OK_BUTTON,
    .showButton = true};

// Calibration Pages
static const TextPage calibrationMinPage = {
    .icon = 297,
    .content = "Put the tip in your mouth and press the button",
    .rightFooter = "Press",
    .showButton = true,
    .center = true};

static const TextPage calibrationMaxPage = {
    .icon = 297,
    .content = "Go as deep as you can and press the button",
    .rightFooter = "Press",
    .showButton = true,
    .center = true};

// Final Page
static const TextPage finalPage = {.icon = 297,
                                   .content = PAGE_FINAL_CONTENT,
                                   .rightFooter = PAGE_FINAL_RIGHT_FOOTER,
                                   .showButton = true,
                                   .timeout = 10000};

void drawTextPage(TextPage page);
void drawQRCodePage(TextPage page);

// Provisioning Page
static const TextPage provisioningPage = {
    .header = "Provisioning",
    .content = "Getting your trainer ID...",
    .timeout = 45000,
    .center = true,
    .y = 10};

#endif  // TEXT_PAGES_H