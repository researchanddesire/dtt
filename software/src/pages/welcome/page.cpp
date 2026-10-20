#include "page.h"

#include "constants/Icons.h"
#include "services/display.h"
#include "services/eeprom_service.h"
#include "services/leds.h"
#include "state/state.h"
#include "structs/Version.h"

using namespace sml;
void drawWelcomeTask(void* pvParameters) {
    auto isInCorrectState = []() {
        return stateMachine->is("init.idle"_s) || stateMachine->is("init"_s);
    };
    if (isInCorrectState()) {
        auto left = "v" + String(currentVersion.major) + "." +
                    String(currentVersion.minor) + "." +
                    String(currentVersion.patch);

#ifdef VERSIONDEV
        left += ".DEV";
#endif
        auto right = String(serialNumber);

#ifdef AUTOPLAY_FOR_VIDEO
        left = "";
        right = "";
#endif

        setLed(LED_LOGO_BLUE, 255, 1500);

        if (xSemaphoreTake(displayMutex, 250) == pdTRUE) {
            setFooter(left, right);
            clearPage();
            const int logoWidth = 53;
            const int logoHeight = 48;
            const int x = (128 - logoWidth) / 2;
            const int y = 8;
            display.drawXBMP(x, y, logoWidth, logoHeight, bitmap_RDLogo);
            // footer content.
            refreshPage();
            xSemaphoreGive(displayMutex);
        }
#ifdef AUTOPLAY_FOR_VIDEO
        vTaskDelay(pdMS_TO_TICKS(10000));

        timeout = 100;
        vTaskDelete(nullptr);
        return;
#else
        vTaskDelay(pdMS_TO_TICKS(1500));
#endif

        if (xSemaphoreTake(displayMutex, 100) == pdTRUE) {
            left = EMPTY_STRING;
            right = String(SKIP) + String(SLASH) + String(HOLD) +
                    String(SPACE) + String(WIFI);
            setFooter(left, right);
            clearPage();
            // print "Trainer ID:" and then trainerIdShort on the next line,
            // centered
            display.setFont(u8g2_font_helvR08_tr);
            const char* label = TRAINER_ID_LABEL;
            int labelWidth = display.getStrWidth(label);
            int labelX = (128 - labelWidth) / 2;
            display.drawStr(labelX, 24, label);

            display.setFont(u8g2_font_helvB14_tr);
            const int idWidth = display.getStrWidth(trainerIdShort.c_str());
            const int idX = (128 - idWidth) / 2;
            display.drawStr(idX, 46, trainerIdShort.c_str());
            refreshPage();
            xSemaphoreGive(displayMutex);
        }
        timeout = 15000;
    }
    vTaskDelete(nullptr);
}
