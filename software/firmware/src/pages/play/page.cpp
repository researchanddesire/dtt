#include "page.h"

#include <input.h>
#include <math.h>
#include <services/leds.h>

#include <cstring>

#include "bounce.h"
#include "constants/iconFonts.h"
#include "endurance.h"
#include "freeform.h"
#include "repetition.h"
#include "services/rad_ble_events.h"
#include "services/vibrator.h"
#include "state/state.h"
#include "wifiSettings.h"
#include <SessionSnapshot.h>
#include <algorithm>
#include <atomic>
#ifdef VERSIONDEV
#include <Wire.h>
#endif
#include <memory>
#include <new>

#define PLAY_TAG "PLAY"

CircularBuffer<float, DISTANCE_BUFFER_SIZE> distanceBuffer;
CircularBuffer<float, SPEED_BUFFER_SIZE> speedBuffer;
static float sum = 21.0 * DISTANCE_BUFFER_SIZE;
static float speedSum = 0;
static int radius = 1;

namespace {
// A rectangle of 8x8 tiles in controller coordinates: the display is rotated
// 180 degrees, so tile (0, 0) is the bottom-right corner. Width 0 is empty.
struct TileArea {
    int x = 0, y = 0, w = 0, h = 0;
};

TileArea tileArea(const int x, const int y, const int w, const int h) {
    const int left = std::max(0, x), top = std::max(0, y);
    const int right = std::min(128, x + w), bottom = std::min(64, y + h);
    if (right <= left || bottom <= top) return {};
    const int firstColumn = left / 8, lastColumn = (right - 1) / 8;
    const int firstRow = top / 8, lastRow = (bottom - 1) / 8;
    return {15 - lastColumn, 7 - lastRow, lastColumn - firstColumn + 1,
            lastRow - firstRow + 1};
}

TileArea unite(const TileArea& a, const TileArea& b) {
    if (a.w == 0) return b;
    if (b.w == 0) return a;
    const int x = std::min(a.x, b.x), y = std::min(a.y, b.y);
    return {x, y, std::max(a.x + a.w, b.x + b.w) - x,
            std::max(a.y + a.h, b.y + b.h) - y};
}

void sendArea(const TileArea& area) {
    if (area.w > 0) display.updateDisplayArea(area.x, area.y, area.w, area.h);
}

// What the box page last sent, so a frame sends only what moved.
struct BoxFrame {
    int left = -1, right = -1, top = -1, followerX = -1;
    TileArea box, follower;
};
BoxFrame sentBoxFrame;
}  // namespace

static bool firstDraw = true;

// Display change tracking - skip mutex if no visual change
static int lastDisplayX = -1;
static float lastRpm = -1.0f;
static int lastStartX = -1;
static int lastEndX = -1;
static String lastValueText;
static float needleRpm = 0.0f;
// Time constant for the freeform needle's glide toward the measured RPM.
static constexpr float NEEDLE_SMOOTHING_MS = 200.0f;

#ifdef VERSIONDEV
// Development builds report the play loop, redraw and sensor rates once per
// second on serial, so a regression below the 120 Hz target is visible.
static std::atomic<uint32_t> sensorSamples{0};
#endif

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

void drawArcWithArrow(const SegmentBase* segment, const float needleRpm) {
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

    // The needle follows the smoothed RPM so it glides between stroke-sized
    // steps; the LED (updatePlayLed) reflects the measured RPM without delay.
    float pct = map_Generic(needleRpm, 0, segment->params.trainingSpeed, 0.0f,
                            0.5f);
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
    const int glyphLeft = currentValue - 11;
    display.drawGlyph(glyphLeft, 64, iconGlyph);
    display.drawTriangle(currentValue, 32, currentValue + 3, 37,
                         currentValue - 3, 37);

    // The display bus moves about 50 bytes per millisecond, so send only what
    // moved: the box when its window changes and the follower when it moves.
    // Each area also covers where it was last drawn, clearing old pixels.
    BoxFrame& sent = sentBoxFrame;
    if (leftBox != sent.left || rightBox != sent.right || contentY != sent.top) {
        const TileArea box = tileArea(leftBox, contentY, boxWidth, 22);
        sendArea(unite(sent.box, box));
        sent.box = box;
        sent.left = leftBox; sent.right = rightBox; sent.top = contentY;
    }
    if (currentValue != sent.followerX) {
        // The glyph is at most one font cell wide; the arrow spans +/-3 px.
        const int glyphRight = glyphLeft + display.getMaxCharWidth() + 1;
        const int followerLeft = std::min(glyphLeft - 1, currentValue - 3);
        const int followerRight = std::max(glyphRight, currentValue + 4);
        const TileArea follower =
            tileArea(followerLeft, 32, followerRight - followerLeft, 32);
        sendArea(unite(sent.follower, follower));
        sent.follower = follower;
        sent.followerX = currentValue;
    }
}

// Runs every loop iteration rather than per frame, so the LED follows zone
// changes even when the follower has not moved a whole pixel.
void updatePlayLed(const SegmentBase* segment) {
    if (segment->displayType == DisplayType::ARC) {
        const float measuredPct = map_Generic(
            segment->currentRpm, 0, segment->params.trainingSpeed, 0.0f, 0.5f);
        if (measuredPct <= 0.5f) {
            setLed(LED_RED, 255, 0);
        } else {
            setLed(LED_GREEN, 255, 0);
        }
    } else if (segment->isWaitingForReturn ||
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
// Paces the play loops at 120 Hz on the 1 kHz tick (8, 8 and 9 ms periods).
// Training maths is tuned to this cadence: the RPM history holds 256 loop
// iterations (~2.1 s) and the position average DISTANCE_BUFFER_SIZE samples.
// An iteration that overruns (a slow frame) yields once and restarts the
// schedule instead of bursting to catch up.
struct PlayPacer {
    TickType_t wake = xTaskGetTickCount();
    uint8_t phase = 0;

    void wait() {
        phase = (phase + 1) % 3;
        const TickType_t period = pdMS_TO_TICKS(phase == 0 ? 9 : 8);
        if (xTaskGetTickCount() - wake >= period) {
            wake = xTaskGetTickCount();
            vTaskDelay(1);
            return;
        }
        vTaskDelayUntil(&wake, period);
    }
};

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
        const Segment& definition = context->definition;
        radBleSegmentStarted(definition.idx, static_cast<int>(definition.type),
                             definition.params.target,
                             definition.params.startPosition,
                             definition.params.endPosition);
        running->train(0);
        notify = trainingLifecycle.reserveNotification(generation, context->sessionId.c_str());
        firstDraw = true;
        lastDisplayX = -1; lastRpm = -1.0f; lastStartX = -1; lastEndX = -1;
        lastValueText = ""; needleRpm = running->currentRpm;
        sentBoxFrame = {};
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
#ifdef VERSIONDEV
    uint32_t rateSince = millis(), loops = 0, draws = 0;
    uint32_t drawUs = 0, drawUsMax = 0, waitUsMax = 0;
    sensorSamples = 0;
#endif
    PlayPacer pacer;
    while (true) {
        bool needsUpdate = false;
        bool headerChanged = false;
        String headerText;
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
            updatePlayLed(running.get());
            if (running->state == TrainingState::END) {
                naturalEnd = true;
                break;
            }
            if (running->displayType == DisplayType::BOX) {
                // Compare in pixels: the windows move continuously in some
                // modes, but a frame only changes when an edge crosses a pixel.
                const int displayX = SegmentBase::toDisplayX(running->currentPosition);
                const int startX = SegmentBase::toDisplayX(running->startWindow);
                const int endX = SegmentBase::toDisplayX(running->endWindow);
                if (displayX != lastDisplayX || startX != lastStartX || endX != lastEndX) {
                    needsUpdate = true; lastDisplayX = displayX;
                    lastStartX = startX; lastEndX = endX;
                }
            } else if (running->displayType == DisplayType::ARC) {
                // RPM steps once per stroke entering or leaving its window;
                // ease the needle toward it so the dial glides between steps.
                needleRpm += (running->currentRpm - needleRpm) *
                             (1.0f - expf(-static_cast<float>(deltaTime) / NEEDLE_SMOOTHING_MS));
                if (abs(needleRpm - lastRpm) > 0.1f) {
                    needsUpdate = true; lastRpm = needleRpm;
                }
            }
            // Countdowns change every 10 ms; redraw the header with them
            // instead of waiting for the next movement.
            headerText = running->valueString();
            headerChanged = headerText != lastValueText;
            if (headerChanged) lastValueText = headerText;
        }
        // Draw outside the training lock: the sensor task takes it for every
        // sample, and a frame occupies the display bus for milliseconds. Only
        // this task mutates `running`. Re-check the generation while holding
        // the display so a stopped run never draws over the page that replaced
        // it (page changes stop the run before taking the display).
#ifdef VERSIONDEV
        const uint32_t waitStart = micros();
#endif
        if ((needsUpdate || headerChanged) && xSemaphoreTake(displayMutex, 100) == pdTRUE) {
#ifdef VERSIONDEV
            const uint32_t drawStart = micros();
            waitUsMax = std::max(waitUsMax, drawStart - waitStart);
#endif
            bool live;
            {
                TrainingGuard guard(trainingMutex);
                live = trainingLifecycle.current(generation);
            }
            if (live && needsUpdate) {
                if (running->displayType == DisplayType::BOX) drawBoxAndFollower(running.get());
                else drawArcWithArrow(running.get(), needleRpm);
            } else if (live) {
                setHeader(headerText);
            }
            xSemaphoreGive(displayMutex);
            if (!live) break;
#ifdef VERSIONDEV
            ++draws;
            const uint32_t elapsed = micros() - drawStart;
            drawUs += elapsed;
            drawUsMax = std::max(drawUsMax, elapsed);
#endif
        }
#ifdef VERSIONDEV
        ++loops;
        if (millis() - rateSince >= 1000) {
            Serial.printf("PLAY_RATE loop=%lu draw=%lu sensor=%lu draw_us_avg=%lu draw_us_max=%lu wait_us_max=%lu i2c=%lu\n",
                          static_cast<unsigned long>(loops), static_cast<unsigned long>(draws),
                          static_cast<unsigned long>(sensorSamples.exchange(0)),
                          static_cast<unsigned long>(draws ? drawUs / draws : 0),
                          static_cast<unsigned long>(drawUsMax), static_cast<unsigned long>(waitUsMax),
                          static_cast<unsigned long>(Wire.getClock()));
            rateSince = millis(); loops = 0; draws = 0;
            drawUs = 0; drawUsMax = 0; waitUsMax = 0;
        }
#endif
        pacer.wait();
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
    PlayPacer pacer;
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
#ifdef VERSIONDEV
        ++sensorSamples;
#endif
        pacer.wait();
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
