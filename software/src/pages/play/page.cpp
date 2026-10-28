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
#include <SessionSnapshot.h>
#include <memory>
#include <new>

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

    if (segment->isWaitingForReturn ||
        segment->state == TrainingState::START) {
        setLed(LED_LOGO_BLUE);
    } else if (segment->positionState == TrainingPosition::BEHIND) {
        setLed(LED_RED, 255, 0);
    } else if (segment->positionState == TrainingPosition::AHEAD) {
        setLed(LED_YELLOW, 255, 0);
    } else if (segment->positionState == TrainingPosition::IN_WINDOW) {
        setLed(LED_GREEN, 255, 0);
    }
}


namespace {
struct TrainingWorkerContext {
    uint32_t generation;
    Segment definition;
    String trainerId;
    String sessionId;
};

void runDrawPlayModeTask(std::unique_ptr<TrainingWorkerContext> context) {
    const auto generation = context->generation;
    std::shared_ptr<SegmentBase> running;
    switch (context->definition.type) {
        case TrainingType::REPETITION: running = std::make_shared<RepetitionSegment>(context->definition.params); break;
        case TrainingType::BOUNCE: running = std::make_shared<BounceSegment>(context->definition.params); break;
        case TrainingType::ENDURANCE: running = std::make_shared<EnduranceSegment>(context->definition.params); break;
        case TrainingType::FREEFORM: running = std::make_shared<FreeformSegment>(context->definition.params); break;
        default: break;
    }
    if (!running) {
        stateMachine->process_event(training_worker_failed{generation});
        return;
    }
    const auto waitingSince = millis();
    while (true) {
        bool ready;
        {
            TrainingGuard guard(trainingMutex);
            if (!trainingLifecycle.current(generation)) return;
            ready = trainingLifecycle.sensorReady(generation);
        }
        if (ready) break;
        if (millis() - waitingSince >= 5000) {
            stateMachine->process_event(training_worker_failed{generation});
            return;
        }
        vTaskDelay(1);
    }
    bool notify = false;
    {
        TrainingGuard guard(trainingMutex);
        if (!trainingLifecycle.activate(generation)) return;
        currentSegment = running;
        running->train(0);
        notify = trainingLifecycle.reserveNotification(generation, context->sessionId.c_str());
        firstDraw = true;
        lastDisplayX = -1; lastRpm = -1.0f; lastStartWindow = -1.0f; lastEndWindow = -1.0f;
    }
    // One best-effort attempt on first genuine play, reserved before scheduling.
    // Recalibration, segment retries and subsequent segments do not retry an
    // ambiguous POST for the same bound session.
    if (notify) {
        auto* trainer = new (std::nothrow) String(context->trainerId);
        if (trainer && xTaskCreatePinnedToCore(notifyTrainingTask, notifyTrainingTaskName,
                8 * configMINIMAL_STACK_SIZE, trainer, 1, &notifyTrainingTaskHandle, 1) != pdPASS) {
            delete trainer;
        }
    }
    auto lastTime = millis();
    float currentPosition = 0;
    bool naturalEnd = false;
#ifdef AUTOPLAY_FOR_VIDEO
    currentPosition = 25;
#endif
    while (true) {
        {
            TrainingGuard guard(trainingMutex);
            if (!trainingLifecycle.current(generation)) break;
            const uint32_t now = millis();
            const uint32_t deltaTime = now - lastTime;
            lastTime = now;
#ifdef AUTOPLAY_FOR_VIDEO
            const float target = (running->startWindow + running->endWindow) / 2;
            currentPosition += std::max(-0.1f, std::min(0.1f, target - currentPosition));
#else
            currentPosition = sum / DISTANCE_BUFFER_SIZE;
#endif
            running->setPositionSpeed(currentPosition, speedSum / SPEED_BUFFER_SIZE);
            running->train(deltaTime);
            vibratorInstance.tick(*running);
            if (running->state == TrainingState::END) {
                naturalEnd = true;
                break;
            }
            bool needsUpdate = false;
            if (running->displayType == DisplayType::BOX) {
                const int displayX = SegmentBase::toDisplayX(running->currentPosition);
                if (displayX != lastDisplayX || running->startWindow != lastStartWindow || running->endWindow != lastEndWindow) {
                    needsUpdate = true; lastDisplayX = displayX;
                    lastStartWindow = running->startWindow; lastEndWindow = running->endWindow;
                }
            } else if (running->displayType == DisplayType::ARC && abs(running->currentRpm - lastRpm) > 0.5f) {
                needsUpdate = true; lastRpm = running->currentRpm;
            }
            if (needsUpdate && xSemaphoreTake(displayMutex, 100) == pdTRUE) {
                if (running->displayType == DisplayType::BOX) drawBoxAndFollower(running.get());
                else drawArcWithArrow(running.get());
                xSemaphoreGive(displayMutex);
            }
        }
        vTaskDelay(1);
    }
    // Never emit generic done on cooperative cancellation. The generation and
    // natural END are rechecked under the state-machine lock before grading.
    if (naturalEnd) stateMachine->process_event(training_worker_finished{generation});
}

void runDistanceTask(uint32_t generation) {
    float initial = getDistance(1);
    if (!std::isfinite(initial)) initial = 21.0f;
    {
        TrainingGuard guard(trainingMutex);
        if (!trainingLifecycle.current(generation)) return;
        distanceBuffer.clear(); speedBuffer.clear();
        for (int i = 0; i < DISTANCE_BUFFER_SIZE; ++i) distanceBuffer.push(initial);
        for (int i = 0; i < SPEED_BUFFER_SIZE; ++i) speedBuffer.push(0.0f);
        sum = initial * DISTANCE_BUFFER_SIZE; speedSum = 0;
        trainingLifecycle.prepareSensor(generation);
    }
    uint32_t lastTime = micros();
    while (true) {
        float nextValue = getDistance(1);
        const uint32_t now = micros();
        const uint32_t deltaTime = now - lastTime;
        lastTime = now;
        {
            TrainingGuard guard(trainingMutex);
            if (!trainingLifecycle.current(generation)) return;
            const float lastValue = distanceBuffer.last();
            const float firstValue = distanceBuffer.first();
            const float firstSpeed = speedBuffer.first();
            float nextSpeed;
            if (!std::isfinite(nextValue)) {
                nextValue = lastValue; nextSpeed = speedBuffer.last();
            } else {
                nextSpeed = trainingSpeedCmPerSecond(lastValue, nextValue, deltaTime);
            }
            distanceBuffer.push(nextValue); speedBuffer.push(nextSpeed);
            sum += nextValue - firstValue; speedSum += nextSpeed - firstSpeed;
        }
        vTaskDelay(1);
    }
}
}  // namespace

void stopTrainingRun() {
    TrainingGuard guard(trainingMutex);
    trainingLifecycle.stop();
    vibratorInstance.off();
}

bool startTrainingTasks(uint32_t drawStackBytes, uint32_t sensorStackBytes) {
    // Invoked synchronously by SML: definition/identity are copied before any
    // asynchronous worker can outlive or be confused with this bound session.
    uint32_t generation;
    {
        TrainingGuard guard(trainingMutex);
        generation = trainingLifecycle.begin();
    }
    const auto definition = copySegmentByIdx(session.segments, session.segmentIdx);
    auto* draw = definition ? new (std::nothrow) TrainingWorkerContext{generation, *definition, trainerId, session.id} : nullptr;
    auto* sensor = new (std::nothrow) uint32_t(generation);
    if (!draw || !sensor) {
        delete draw; delete sensor;
        stateMachine->process_event(training_worker_failed{generation});
        return false;
    }
    if (xTaskCreatePinnedToCore(getDistanceTask, distanceTaskName, sensorStackBytes,
            sensor, 1, &getDistanceTaskHandle, 0) != pdPASS) {
        delete draw; delete sensor;
        stateMachine->process_event(training_worker_failed{generation});
        return false;
    }
    if (xTaskCreatePinnedToCore(drawPlayModeTask, drawPlayModeTaskName, drawStackBytes,
            draw, 1, &drawPlayModeTaskHandle, 1) != pdPASS) {
        delete draw;
        stateMachine->process_event(training_worker_failed{generation});
        return false;
    }
    return true;
}

void drawPlayModeTask(void* parameter) {
    runDrawPlayModeTask(std::unique_ptr<TrainingWorkerContext>(static_cast<TrainingWorkerContext*>(parameter)));
    // Inner function returns normally so C++ ownership is released before the
    // FreeRTOS task deletes its stack (vTaskDelete does not unwind destructors).
    vTaskDelete(nullptr);
}

void getDistanceTask(void* parameter) {
    const auto generation = *static_cast<uint32_t*>(parameter);
    delete static_cast<uint32_t*>(parameter);
    runDistanceTask(generation);
    vTaskDelete(nullptr);
}
