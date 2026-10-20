#include "page.h"

#include <input.h>
#include <math.h>
#include <services/leds.h>

#include <cstring>
#include <utils/getTiles.hpp>

#include "bounce.h"
#include "constants/iconFonts.h"
#include "endurance.h"
#include "freeform.h"
#include "repetition.h"
#include "services/vibrator.h"
#include "state/state.h"
#include "wifiSettings.h"

#define PLAY_TAG "PLAY"

CircularBuffer<float, DISTANCE_BUFFER_SIZE> distanceBuffer;
CircularBuffer<float, SPEED_BUFFER_SIZE> speedBuffer;
static float sum = 21.0 * DISTANCE_BUFFER_SIZE;
static float speedSum = 0;
static int radius = 1;

static int boxTiles[4] = {0, 0, 0, 0};
static int lastBoxTiles[4] = {0, 0, 0, 0};

static int glyphTiles[4] = {0, 0, 0, 0};
static int lastGlyphTiles[4] = {0, 0, 0, 0};

static bool firstDraw = true;

// Display change tracking - skip mutex if no visual change
static int lastDisplayX = -1;
static float lastRpm = -1.0f;
static float lastStartWindow = -1.0f;
static float lastEndWindow = -1.0f;

/**
 * Draws a simplified speedometer with N tick marks
 * @param currentValue - Current position value (not used in this
 * implementation)
 * @param numTicks - Number of tick marks (default: 5)
 *
 * The speedometer has:
 * - One tick always at 0 degrees (top)
 * - One tick always at 180 degrees (bottom)
 * - Remaining ticks distributed evenly between 0 and 180 degrees
 */
void drawArc() {
    constexpr int radius = 32;
    constexpr int centerX = radius;
    constexpr int centerY = 64;
    constexpr int N = 7;

    display.drawCircle(centerX, centerY, radius);

    for (int i = 0; i < N; ++i) {
        float t = static_cast<float>(i) / (N - 1);  // 0.0 to 1.0
        float angleRad = t * PI;                    // 0 to PI radians

        float sinA = sinf(angleRad + 3 * PI / 2);
        float cosA = cosf(angleRad + 3 * PI / 2);

        float tickStartXf = centerX + (radius - 4) * sinA;
        float tickStartYf = centerY - (radius - 4) * cosA;
        float tickEndXf = centerX + radius * sinA;
        float tickEndYf = centerY - radius * cosA;

        int tickStartX = static_cast<int>(tickStartXf + 0.5f);
        int tickStartY = static_cast<int>(tickStartYf + 0.5f);
        int tickEndX = static_cast<int>(tickEndXf + 0.5f);
        int tickEndY = static_cast<int>(tickEndYf + 0.5f);

        display.drawLine(tickStartX, tickStartY, tickEndX, tickEndY);
    }

    int glyphX = radius * 2 + (128 - (radius * 2)) / 2;
    int glyphY = 64;

    // Use configurable icon from session settings
    const uint8_t* iconFont = getFontByName(session.icon.set);
    int iconGlyph = session.icon.set_id;

    display.setFont(iconFont);
    display.drawGlyph(glyphX, glyphY, iconGlyph);
}

void drawArcWithArrow(const SegmentBase* segment) {
    String valueString = segment->valueString();
    setHeader(valueString);
    clearPage(true);

    if (firstDraw) {
        drawArc();
        refreshPage(true);
        firstDraw = false;
    }

    constexpr int radius = 32;
    constexpr int centerX = radius;
    constexpr int centerY = 64;

    // Draw a small center circle (speedometer hub)
    constexpr int hubRadius = 5;
    display.drawDisc(centerX, centerY, hubRadius);

    // Calculate the angle for the needle (triangle)
    float pct = map_Generic(segment->currentRpm, 0,
                            segment->params.trainingSpeed, 0.0f, 0.5f);
    float angle = max(0.0, min(pct * PI, PI));

    // Triangle parameters
    constexpr float needleLength = 16;
    constexpr float needleWidth = 10.0f;  // width of the base of the triangle

    // Tip of the triangle (needle point)
    float tipX = centerX + needleLength * sinf(angle + 3 * PI / 2);
    float tipY = centerY - needleLength * cosf(angle + 3 * PI / 2);

    // Base of the triangle (two points, perpendicular to the needle direction)
    float baseAngle = angle + 3 * PI / 2 + PI / 2;  // perpendicular to needle
    float base1X = centerX + (hubRadius + 1) * sinf(angle + 3 * PI / 2) +
                   (needleWidth / 2) * sinf(baseAngle);
    float base1Y = centerY - (hubRadius + 1) * cosf(angle + 3 * PI / 2) -
                   (needleWidth / 2) * cosf(baseAngle);

    float base2X = centerX + (hubRadius + 1) * sinf(angle + 3 * PI / 2) -
                   (needleWidth / 2) * sinf(baseAngle);
    float base2Y = centerY - (hubRadius + 1) * cosf(angle + 3 * PI / 2) +
                   (needleWidth / 2) * cosf(baseAngle);

    // Draw the filled triangle (needle)
    display.drawTriangle(
        static_cast<int>(tipX + 0.5f), static_cast<int>(tipY + 0.5f),
        static_cast<int>(base1X + 0.5f), static_cast<int>(base1Y + 0.5f),
        static_cast<int>(base2X + 0.5f), static_cast<int>(base2Y + 0.5f));

    // display.drawBox(0, 0, 128, 64);

    display.updateDisplayArea(10, 0, 4, 3);

    if (pct <= 0.5f) {
        setLed(LED_RED, 255, 0);
    } else {
        setLed(LED_GREEN, 255, 0);
    }
}

void drawBoxAndFollower(const SegmentBase* segment) {
    String valueString = segment->valueString();
    int currentValue = SegmentBase::toDisplayX(segment->currentPosition);

    const float left = min(segment->startWindow, segment->endWindow);
    const float right = max(segment->startWindow, segment->endWindow);
    const int leftBox = SegmentBase::toDisplayX(left);
    const int rightBox = SegmentBase::toDisplayX(right);
    const int boxWidth = rightBox - leftBox;

    setHeader(valueString);
    clearPage(true);

    // Add extra 3 pixels of spacing between header and content for repetition
    // mode
    const int contentY = (segment->type == TrainingType::REPETITION) ? 11 : 8;
    display.drawRFrame(leftBox, contentY, boxWidth, 22, 2 * radius);

    // Use configurable icon from session settings
    const uint8_t* iconFont = getFontByName(session.icon.set);
    int iconGlyph = session.icon.set_id;

    display.setFont(iconFont);
    display.drawGlyph(currentValue - 11, 64, iconGlyph);
    display.drawTriangle(currentValue, 32, currentValue + 3, 37,
                         currentValue - 3, 37);

    getTiles(leftBox, contentY, boxWidth, 22, boxTiles, lastBoxTiles);
    display.updateDisplayArea(boxTiles[0], boxTiles[1], boxTiles[2],
                              boxTiles[3]);

    getTiles(currentValue - 16, 32, 32, 32, glyphTiles, lastGlyphTiles);
    display.updateDisplayArea(glyphTiles[0], glyphTiles[1], glyphTiles[2],
                              glyphTiles[3]);

    if (currentSegment->isWaitingForReturn ||
        currentSegment->state == TrainingState::START) {
        setLed(LED_LOGO_BLUE);
    } else if (currentSegment->positionState == TrainingPosition::BEHIND) {
        setLed(LED_RED, 255, 0);
    } else if (currentSegment->positionState == TrainingPosition::AHEAD) {
        setLed(LED_YELLOW, 255, 0);
    } else if (currentSegment->positionState == TrainingPosition::IN_WINDOW) {
        setLed(LED_GREEN, 255, 0);
    }
}

void drawPlayModeTask(void* pvParameters) {
    const Segment* segment = getSegmentByIdx(session.segmentIdx);
    if (segment == nullptr) {
        ESP_LOGD(PLAY_TAG, "Segment not found for idx %d", session.segmentIdx);
        drawTextPage(TextPage{
            .header = ERROR_HEADER,
            .icon = 482,
            .content = ERROR_MESSAGE,
            .rightFooter = ERROR_RIGHT_FOOTER,
            .center = true,
            .y = 10,
        });
        stateMachine->process_event(done{});
        vTaskDelete(nullptr);
        return;
    }

    ESP_LOGD(PLAY_TAG, "Drawing play mode, type: %d", static_cast<int>(segment->type));

    auto isInCorrectState = []() { return stateMachine->is("play.idle"_s); };

    float currentPosition = 0;
    float speed = 0;
    firstDraw = true;

    // Reset display change tracking
    lastDisplayX = -1;
    lastRpm = -1.0f;
    lastStartWindow = -1.0f;
    lastEndWindow = -1.0f;

    switch (segment->type) {
        case TrainingType::REPETITION:
            currentSegment = new RepetitionSegment(segment->params);
            break;
        case TrainingType::BOUNCE:
            currentSegment = new BounceSegment(segment->params);
            break;
        case TrainingType::ENDURANCE:
            currentSegment = new EnduranceSegment(segment->params);
            break;
        case TrainingType::FREEFORM:
            currentSegment = new FreeformSegment(segment->params);
            break;
        default:
            currentSegment = nullptr;
            break;
    }
    if (currentSegment == nullptr) {
        ESP_LOGD(PLAY_TAG, "Segment is nullptr, exiting");
        drawTextPage(TextPage{
            .header = ERROR_HEADER,
            .icon = 482,
            .content = ERROR_MESSAGE,
            .rightFooter = ERROR_RIGHT_FOOTER,
            .center = true,
            .y = 10,
        });
        vTaskDelete(nullptr);
        return;
    }

    currentSegment->train(0);

    unsigned long lastTime = millis();

#ifdef AUTOPLAY_FOR_VIDEO
    currentPosition = 25;
#endif

    while (isInCorrectState() && currentSegment->state != TrainingState::END) {
        const long deltaTime = millis() - lastTime;
        lastTime = millis();

#ifdef AUTOPLAY_FOR_VIDEO
        // Move currentPosition slowly towards the target (midpoint between
        // startWindow and endWindow)
        {
            float targetPosition =
                (currentSegment->startWindow + currentSegment->endWindow) / 2;
            float step = 0.1;  // adjust this value for speed of movement
            if (abs(currentPosition - targetPosition) < step) {
                currentPosition = targetPosition;
            } else if (currentPosition < targetPosition) {
                currentPosition += step;
            } else {
                currentPosition -= step;
            }
        }
#else
        currentPosition = sum / DISTANCE_BUFFER_SIZE;
#endif

        speed = speedSum / SPEED_BUFFER_SIZE;

        currentSegment->setPositionSpeed(currentPosition, speed);
        currentSegment->train(deltaTime);
        vibratorInstance.tick();

        if (currentSegment->state == TrainingState::END) {
            ESP_LOGD(PLAY_TAG, "Segment in end state, exiting");
            break;
        }

        // Check if display needs updating
        bool needsUpdate = false;
        if (currentSegment->displayType == DisplayType::BOX) {
            int displayX =
                SegmentBase::toDisplayX(currentSegment->currentPosition);
            if (displayX != lastDisplayX ||
                currentSegment->startWindow != lastStartWindow ||
                currentSegment->endWindow != lastEndWindow) {
                needsUpdate = true;
                lastDisplayX = displayX;
                lastStartWindow = currentSegment->startWindow;
                lastEndWindow = currentSegment->endWindow;
            }
        } else if (currentSegment->displayType == DisplayType::ARC) {
            if (abs(currentSegment->currentRpm - lastRpm) > 0.5f) {
                needsUpdate = true;
                lastRpm = currentSegment->currentRpm;
            }
        }

        if (needsUpdate) {
            if (xSemaphoreTake(displayMutex, 100) == pdTRUE) {
                if (currentSegment->displayType == DisplayType::BOX) {
                    drawBoxAndFollower(currentSegment);
                } else if (currentSegment->displayType == DisplayType::ARC) {
                    drawArcWithArrow(currentSegment);
                }

                xSemaphoreGive(displayMutex);
            } else {
                ESP_LOGD(PLAY_TAG, "Failed to take display mutex");
            }
        }

        vTaskDelay(1);
    }

    ESP_LOGD(PLAY_TAG, "Exiting drawPlayModeTask");
    vibratorInstance.off();
    stateMachine->process_event(done{});

    vTaskDelete(nullptr);
}

void getDistanceTask(void* pvParameters) {
    ESP_LOGD(PLAY_TAG, "Starting getDistanceTask");
    auto isInCorrectState = []() { return stateMachine->is("play.idle"_s); };

    distanceBuffer.clear();
    // fill all values with 21.0
    for (int i = 0; i < DISTANCE_BUFFER_SIZE; i++) {
        distanceBuffer.push(21.0);
    }
    speedBuffer.clear();
    for (int i = 0; i < SPEED_BUFFER_SIZE; i++) {
        speedBuffer.push(0.0);
    }
    sum = 21.0 * DISTANCE_BUFFER_SIZE;

    float firstValue = 0;
    float nextValue = 0;
    float lastValue = 0;

    float firstSpeed = 0;
    float nextSpeed = 0;
    float lastSpeed = 0;

    unsigned long lastTime = micros();

    while (isInCorrectState()) {
        const long deltaTime = xTaskGetTickCount() * portTICK_PERIOD_MS;

        lastValue = distanceBuffer.last();
        firstValue = distanceBuffer.first();
        nextValue = getDistance(1);

        lastSpeed = speedBuffer.last();
        firstSpeed = speedBuffer.first();
        nextSpeed =
            10000.0 * (nextValue - lastValue) / static_cast<float>(deltaTime);

        // if is nan, set nextValue to 21

        if (isnan(nextValue)) {
            nextValue = 21.0;
            nextSpeed = lastSpeed;
        }

        distanceBuffer.push(nextValue);
        speedBuffer.push(nextSpeed);
        sum = sum - firstValue + nextValue;
        speedSum = speedSum - firstSpeed + nextSpeed;
        vTaskDelay(1);
    }

    ESP_LOGD(PLAY_TAG, "Exiting getDistanceTask");

    vTaskDelete(nullptr);
}
