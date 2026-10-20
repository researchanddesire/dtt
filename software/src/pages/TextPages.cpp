#include "TextPages.h"

#include "qrcode.h"
#include "services/display.h"
#include "services/eeprom_service.h"

#define TEXT_PAGES_TAG "TEXT_PAGES"

/**
 * Calculate the total height of all content elements in a TextPage.
 * This simulates the layout to determine how much vertical space the content will occupy.
 * 
 * @param page The TextPage to calculate height for
 * @param hasIcon Whether the page has an icon
 * @return Total height in pixels
 */
static int calculateContentHeight(const TextPage& page, bool hasIcon) {
    int calcY = 0;  // Track cumulative height as we simulate each element
    
    // Calculate icon height if present
    if (hasIcon) {
        display.setFont(funIconsFont);
        calcY += display.getFontAscent();  // Icon glyph height
        calcY += 4;  // Spacing after icon
    }
    
    // Calculate title height if present
    if (page.title.length() > 0) {
        display.setFont(u8g2_font_helvB08_tr);
        const int titleLines = calculateWrappedTextLines(0, page.title.c_str());
        // Title spacing: 4px gap + height of all wrapped lines
        calcY += 4 + titleLines * display.getFontAscent();
    }
    
    // Calculate tagline height if present
    if (page.tagline.length() > 0) {
        display.setFont(u8g2_font_helvR08_tr);
        const int taglineLines = calculateWrappedTextLines(0, page.tagline.c_str());
        // Tagline spacing: 2px gap + height of all wrapped lines
        calcY += 2 + taglineLines * display.getFontAscent();
    }
    
    // Calculate content height if present
    if (page.content.length() > 0) {
        display.setFont(u8g2_font_helvR08_tr);
        const int contentLines = calculateWrappedTextLines(page.x, page.content.c_str());
        // Content uses different spacing: first line uses fontHeight offset,
        // subsequent lines use lineHeight spacing
        const int contentFontHeight = display.getFontAscent();
        const int contentLineHeight = display.getMaxCharHeight();
        if (contentLines > 0) {
            calcY += contentFontHeight;  // First line baseline offset
            if (contentLines > 1) {
                calcY += (contentLines - 1) * contentLineHeight;  // Additional lines
            }
        }
    }
    
    return calcY;
}

/**
 * Calculate the starting Y position for vertically centered content.
 * 
 * @param totalHeight Total height of all content elements
 * @param defaultY Default Y position (when not centering)
 * @return Starting Y position for drawing content
 */
static int calculateCenteredStartY(int totalHeight, int defaultY) {
    // Available content area: y=8 (below header) to y=56 (above footer) = 48 pixels
    // Center point is at y=32, so we start drawing at center - half total height
    const int contentAreaCenter = 32;  // (8 + 56) / 2
    int startY = contentAreaCenter - (totalHeight / 2);
    
    // Safety check: ensure content doesn't go above header area
    if (startY < 8) {
        startY = 8;
    }
    
    return startY;
}

void drawTextPage(TextPage page) {
#ifdef AUTOPLAY_FOR_VIDEO
    page.timeout = 1000;
#else
    timeout = page.timeout;
#endif

    showButton = page.showButton;

    if (xSemaphoreTake(displayMutex, 100) == pdTRUE) {
        if (page.showTrainerId) {
            const String leftFooterStr = "ID: " + trainerIdShort;
            page.leftFooter = leftFooterStr.c_str();
        }

        setHeader(page.header);
        setFooter(page.leftFooter, page.rightFooter);

        clearPage();
        display.setFont(u8g2_font_helvR08_tr);

        const bool hasIcon = page.icon > -1;
        
        // Calculate starting Y position (centered if requested)
        int startY = 8 + page.y;  // Default starting position (below header)
        if (page.center) {
            const int totalHeight = calculateContentHeight(page, hasIcon);
            startY = calculateCenteredStartY(totalHeight, startY);
        }
        
        // Draw all content elements starting from calculated position
        int iconY = startY;

        if (hasIcon) {
            display.setFont(funIconsFont);
            iconY += display.getFontAscent();
            display.drawGlyph((128 - 21) / 2, iconY, page.icon);
            iconY += 4;
        }

        if (page.title.length() > 0) {
            display.setFont(u8g2_font_helvB08_tr);
            display.getStrWidth(page.title.c_str());
            const int lines =
                drawWrappedText(0, iconY, page.title.c_str(), true);
            iconY += 4 + lines * display.getFontAscent();
        }

        if (page.tagline.length() > 0) {
            display.setFont(u8g2_font_helvR08_tr);
            const int taglineLines =
                drawWrappedText(0, iconY, page.tagline.c_str(), true);
            iconY += 2 + taglineLines * display.getFontAscent();
        }

        if (page.content.length() > 0) {
            display.setFont(u8g2_font_helvR08_tr);
            drawWrappedText(page.x, iconY, page.content.c_str(), page.center);
        }

        refreshPage();
        xSemaphoreGive(displayMutex);
    }
}

void drawQRCodePage(TextPage page) {
    showButton = page.showButton;

    if (xSemaphoreTake(displayMutex, 100) == pdTRUE) {
        setFooter(page.leftFooter, page.rightFooter);
        clearPage(true, true);

        static QRCode qrcode;
        constexpr int scale = 2;
        constexpr int version = 3;
        // This Version of QR Codes can handle ~61 alphanumeric characters with
        // ECC LEVEL M

        // NOLINTBEGIN(modernize-avoid-c-arrays)
        uint8_t qrcodeData[qrcode_getBufferSize(version)];
        // NOLINTEND(modernize-avoid-c-arrays)

        String url = (page.url.length() > 0)
                         ? page.url
                         : "https://docs.researchanddesire.com";

        if (page.url.length() > 0 && page.url.indexOf("dashboard") >= 0) {
            url += "?dtt=" + trainerIdShort;
        }

        qrcode_initText(&qrcode, qrcodeData, version, ECC_LOW, url.c_str());

        const int yOffset = constrain((64 - qrcode.size * scale) / 2, 0, 64);

        // Draw the QR code
        for (uint8_t y = 0; y < qrcode.size; y++) {
            for (uint8_t x = 0; x < qrcode.size; x++) {
                if (qrcode_getModule(&qrcode, x, y)) {
                    constexpr int xOffset = 0;
                    display.drawBox(xOffset + x * scale, yOffset + y * scale,
                                    scale, scale);
                }
            }
        }

        const int codeWidth = qrcode.size * scale;

        const bool hasIcon = page.icon > -1;
        int textY = 8;

        if (page.showTrainerId) {
            display.setFont(u8g2_font_helvB14_tr);
            textY += display.getFontAscent() + 4;
            const int idWidth = display.getStrWidth(trainerIdShort.c_str());
            const int idX = (128 - codeWidth - idWidth) / 2 + codeWidth;
            display.drawStr(idX, textY, trainerIdShort.c_str());
            textY += 6;
        } else if (hasIcon) {
            display.setFont(funIconsFont);
            textY += display.getFontAscent();
            display.drawGlyph((128 - codeWidth - 21) / 2 + codeWidth, 30,
                              page.icon);
            display.setFont(u8g2_font_helvR08_tr);
            textY += 4;
        } else {
            // just a little more y padding if no icon or trainer id
            textY += 2;
        }

        if (page.title.length() > 0) {
            display.setFont(u8g2_font_helvB08_tr);
            display.getStrWidth(page.title.c_str());
            const int lines =
                drawWrappedText(codeWidth + 4, textY, page.title.c_str(), true);
            textY += 4 + lines * display.getFontAscent();
        }

        if (page.content.length() > 0) {
            display.setFont(u8g2_font_helvR08_tr);
            drawWrappedText(codeWidth + 2, textY, page.content.c_str(),
                            page.center);
        }
        refreshPage(true, true);
        xSemaphoreGive(displayMutex);
    }
}