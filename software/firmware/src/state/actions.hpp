#pragma once

#ifndef ACTIONS_HPP
#define ACTIONS_HPP

#include <Arduino.h>
#include <esp_heap_caps.h>
#include <wifiSettings.h>

#include "pages/TextPages.h"
#include "services/display.h"
#include "services/wifi_service.h"
#include "state/events.hpp"
#include "state/utils.h"
#include "utils/update.hpp"

#ifndef PROVISION
#include <Calibration.h>
#include <SessionSnapshot.h>

#include "input.h"
#include "pages/play/page.h"
#include "services/leds.h"
#include "services/rad_ble_events.h"
#include "services/vibrator.h"
#include "utils.h"
#endif

#define ACTIONS_TAG "ACTIONS"

static constexpr uint8_t RUNTIME_TASK_STACK_MULTIPLIER = 8;
static constexpr uint8_t SENSOR_TASK_STACK_MULTIPLIER = 4;
#ifdef PROVISION
static constexpr uint8_t UPDATE_TASK_STACK_MULTIPLIER = 10;
#else
static constexpr uint8_t UPDATE_TASK_STACK_MULTIPLIER =
    RUNTIME_TASK_STACK_MULTIPLIER;
#endif

// Auto-advance timeouts for the detail and result screens. Hands-free mode
// shortens the wait so the session, each segment, and the score/failure screens
// advance without a button press; the manual flow keeps the longer reading time.
static constexpr long DETAIL_TIMEOUT_MS = 10000;
static constexpr long RESULT_TIMEOUT_MS = 30000;
static constexpr long DETAIL_TIMEOUT_HANDS_FREE_MS = 5000;
static constexpr long RESULT_TIMEOUT_HANDS_FREE_MS = 7000;

constexpr auto preflightCheck = []() {
    if (dashboardState.preflightPending) {
        return;
    }
    process_preflight_done();
};

constexpr auto startTask = [](auto task, const char *taskName,
                              TaskHandle_t *pHandle, uint8_t size = 10,
                              uint8_t core = 1) {
    return [task, taskName, pHandle, size, core]() mutable {
        const uint32_t stackBytes = size * configMINIMAL_STACK_SIZE;
        const size_t internalBefore =
            heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
        const size_t largestBefore = heap_caps_get_largest_free_block(
            MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
        ESP_LOGI(ACTIONS_TAG,
                 "Starting task %s stack=%lu core=%u internal=%u largest=%u "
                 "psram=%u freePsram=%u",
                 taskName, static_cast<unsigned long>(stackBytes), core,
                 static_cast<unsigned>(internalBefore),
                 static_cast<unsigned>(largestBefore),
                 static_cast<unsigned>(ESP.getPsramSize()),
                 static_cast<unsigned>(ESP.getFreePsram()));
        if (pHandle != nullptr) {
            *pHandle = nullptr;
        }
        const BaseType_t result = xTaskCreatePinnedToCore(
            task, taskName, stackBytes, nullptr, 1, pHandle, core);
        ESP_LOGI(
            ACTIONS_TAG, "Task %s create=%s internal=%u largest=%u handle=%p",
            taskName, result == pdPASS ? "ok" : "FAILED",
            static_cast<unsigned>(
                heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)),
            static_cast<unsigned>(heap_caps_get_largest_free_block(
                MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)),
            pHandle == nullptr ? nullptr : *pHandle);
    };
};

#ifdef PROVISION
constexpr auto clear = []() {
    timeout = 0;
    showButton = false;

    if (xSemaphoreTake(displayMutex, 100) == pdTRUE) {
        clearPage(true, true);
        refreshPage(true, true);
        clearTimeout();
        refreshTimeout();
        xSemaphoreGive(displayMutex);
    }
};
#else
constexpr auto clear = []() {
    setLedOff();
    timeout = 0;
    showButton = false;

    {
        TrainingGuard guard(trainingMutex);
        trainingLifecycle.stop();
        currentSegment.reset();
    }

    if (xSemaphoreTake(displayMutex, 100) == pdTRUE) {
        clearPage(true, true);
        refreshPage(true, true);
        clearTimeout();
        refreshTimeout();
        xSemaphoreGive(displayMutex);
    }
};
#endif  // PROVISION

constexpr auto disconnectWifi = []() {
    WiFi.disconnect(true);

    WiFi.setAutoReconnect(false);
    WiFi.setAutoConnect(false);
};

constexpr auto drawPage = [](const TextPage *page,
                             bool processDoneAfter = false) {
    return [page, processDoneAfter]() {
        ESP_LOGD(ACTIONS_TAG, "Drawing page");
        if (page->url.length() > 0) {
            drawQRCodePage(*page);
        } else {
            drawTextPage(*page);
        }

        if (processDoneAfter) {
            process_done();
        }
    };
};

// Picks copy from live state so the message is honest: a get-settings failure
// while still online (dashboard errored) is NOT the same as being offline.
constexpr auto drawLoadSettingsPage = []() {
    const bool online =
        (WiFiClass::status() == WL_CONNECTED) && healthCheckPassed;
    drawTextPage(TextPage{
        .icon = 297,
        .content = online ? PAGE_SETTINGS_STALE_CONTENT : PAGE_OFFLINE_CONTENT,
        .rightFooter = NEXT_HOLD_PLAY,
        .showButton = true,
        .timeout = 10000,
    });
};

constexpr auto espRestart = []() { esp_restart(); };

constexpr auto updateDevice = []() {
    if (updateTaskHandle != nullptr) {
        ESP_LOGW(ACTIONS_TAG, "Update task already active; ignoring duplicate start");
        return;
    }
    const BaseType_t result = xTaskCreatePinnedToCore(
        [](void *pvParameters) {
#ifdef PROVISION
            const bool success = updateSoftware();
            updateTaskHandle = nullptr;
            if (success) {
                process_update_complete();
            } else {
                process_update_failed();
            }
#else
            // A successful install reboots and never returns. Both a
            // no-update result and a recoverable error return through the
            // existing update -> preflight edge.
            updateSoftware();
            updateTaskHandle = nullptr;
            process_fail();
#endif
            vTaskDelete(nullptr);
        },
        updateTaskName, UPDATE_TASK_STACK_MULTIPLIER * configMINIMAL_STACK_SIZE,
        nullptr, 1, &updateTaskHandle, 1);
    if (result != pdPASS) {
        updateTaskHandle = nullptr;
        ESP_LOGE(ACTIONS_TAG, "Failed to create update task");
#ifdef PROVISION
        process_update_failed();
#else
        process_fail();
#endif
    }
};

constexpr auto provisionTimedOut = []() {
    provisionError = "Timed out";
};

constexpr auto drawProvisionError = []() {
    drawTextPage(TextPage{.header = "Provision Failed",
                          .icon = 483,
                          .content = provisionError,
                          .rightFooter = "Retry",
                          .showButton = true,
                          .timeout = 0,
                          .center = true});
};

#ifdef PROVISION
constexpr auto drawProvisionSuccess = []() {
    drawTextPage(TextPage{.header = "Provisioning",
                          .content = "ID: " + trainerIdShort + String("\n #") +
                                     String(serialNumber),
                          .rightFooter = "Update",
                          .showButton = true,
                          .timeout = 0,
                          .center = true,
                          .y = 10});
};

constexpr auto drawProvisionUpdateError = []() {
    drawTextPage(TextPage{.header = "Update Failed",
                          .icon = 483,
                          .content = "Update did not finish",
                          .rightFooter = "Retry",
                          .showButton = true,
                          .timeout = 0,
                          .center = true});
};
#endif

#ifndef PROVISION

constexpr auto next = []() { process_done(false); };
constexpr auto startTrainingRun = []() {
    startTrainingTasks(RUNTIME_TASK_STACK_MULTIPLIER * configMINIMAL_STACK_SIZE,
                       SENSOR_TASK_STACK_MULTIPLIER * configMINIMAL_STACK_SIZE);
};
constexpr auto stopTraining = []() { stopTrainingRun(); };
constexpr auto saveCompletedResult = []() { startSaveResultsTask(); };


inline bool sessionLoadComplete = false;
constexpr auto beginSessionLoad = []() { sessionLoadComplete = false; };
constexpr auto failSessionLoad = []() { process_fail(); };
constexpr auto applyLoadedSession = [](const session_load_ready &request) {
    TrainingGuard guard(trainingMutex);
    request.applied = request.apply();
    sessionLoadComplete = request.applied;
    if (request.applied)
        process_done(false);
    else
        process_fail();
};

constexpr auto incrementSegmentIdx = []() { TrainingGuard guard(trainingMutex); session.segmentIdx++; };

constexpr auto clearSegmentIndex = []() {
    TrainingGuard guard(trainingMutex);
    session.id = uuid();
    session.segmentIdx = 0;
    setLedOff();
};

// The tip reading waits for the deep reading to pass the range check, so a
// failed recalibration keeps the previous calibration.
static float pendingTipCm = 0.0f;
static CalibrationProblem calibrationProblem = CalibrationProblem::None;

constexpr auto captureMinPosition = []() {
    TrainingGuard guard(trainingMutex);
    pendingTipCm = getDistance(100);
};

constexpr auto captureMaxPosition = []() {
    {
        TrainingGuard guard(trainingMutex);
        const float deepCm = getDistance(100);
        calibrationProblem = checkCalibration(pendingTipCm, deepCm);
        if (calibrationProblem == CalibrationProblem::None) {
            session.calibratedMinPosition = pendingTipCm;
            session.calibratedMaxPosition = deepCm;

            for (auto &segment : session.segments) {
                segment.params.startPosition = session.calibratedMinPosition;
                segment.params.endPosition = session.calibratedMaxPosition;
            }

            session.isCalibrated = true;

            sendCalibrationToBackend(session.calibratedMaxPosition,
                                     session.calibratedMinPosition);
        } else {
            ESP_LOGW(ACTIONS_TAG, "Rejected calibration: tip %.2f cm, deep %.2f cm",
                     pendingTipCm, deepCm);
        }
    }
    // Outside the training lock: the next state draws a page, and the play
    // draw loop takes the display before the training lock.
    if (calibrationProblem == CalibrationProblem::None)
        process_done(false);
    else
        process_fail();
};

constexpr auto drawCalibrationProblem = []() {
    String content;
    switch (calibrationProblem) {
        case CalibrationProblem::OutOfRange:
            content = "Toy not detected. Check it faces the sensor and try again";
            break;
        case CalibrationProblem::Reversed:
            content = "Tip first, then as deep as you can. Try again";
            break;
        case CalibrationProblem::TooShort:
            content = "Not enough movement. Go deeper on the second press";
            break;
        default:
            content = "Sensor error. Try again";
            break;
    }
    const bool canKeepPrevious =
        (session.toy.has_value() && session.toy->calibration.isCalibrated) ||
        session.isCalibrated;
    drawTextPage(TextPage{
        .icon = 297,
        .content = content,
        .leftFooter = canKeepPrevious ? "Hold: keep" : EMPTY_STRING,
        .rightFooter = "Retry",
        .showButton = true,
        .center = true});
};

constexpr auto drawSessionDetails = []() {
    String leftFooter = EMPTY_STRING;

    leftFooter =
        String(session.segmentIdx + 1) + "/" + String(session.segmentCount);

    drawTextPage(TextPage{
        .header = SESSION_HEADER,
        .icon = session.iconId.value_or(249),
        .title = session.name,
        .tagline = session.tagline,
        .content = session.description,
        .leftFooter = leftFooter.c_str(),
        .rightFooter = session.hasSeenSessionDetails ? PLAY : NEXT_HOLD_PLAY,
        .timeout = session.handsFreeMode ? DETAIL_TIMEOUT_HANDS_FREE_MS
                                         : DETAIL_TIMEOUT_MS,
        .center = true,
    });
};

constexpr auto drawToyDetails = []() {
    String leftFooter = EMPTY_STRING;
    bool hasSeenSessionDetails = false;

    leftFooter =
        String(session.segmentIdx + 1) + "/" + String(session.segmentCount);

    hasSeenSessionDetails = session.hasSeenSessionDetails;

    drawTextPage(TextPage{
        .header = TOY_HEADER,
        .icon = 269,
        .title = session.toy.value().name,
        .content = session.toy.value().tagline,
        .leftFooter = leftFooter.c_str(),
        .rightFooter = hasSeenSessionDetails ? PLAY : NEXT_HOLD_PLAY,
        .timeout = session.handsFreeMode ? DETAIL_TIMEOUT_HANDS_FREE_MS
                                         : DETAIL_TIMEOUT_MS,
        .center = true,
    });
};

constexpr auto drawSegmentDetails = []() {
    TrainingGuard guard(trainingMutex);
    const Segment *segment = getSegmentByIdx(session.segmentIdx);
    if (segment == nullptr) {
        ESP_LOGD(ACTIONS_TAG, "Segment not found for idx %d", session.segmentIdx);
        process_fail();
        return;
    }
    session.hasSeenSessionDetails = true;

    const String leftFooter =
        String(session.segmentIdx + 1) + "/" + String(session.segmentCount);

    int icon = -1;

    const int target = segment->params.target;
    auto content = String(target);
    content += SPACE;

    if (segment->type == TrainingType::REPETITION) {
        icon = 362;
        content += REPETITIONS_SHORT;
    } else if (segment->type == TrainingType::BOUNCE) {
        icon = 362;
        content += REPETITIONS_SHORT;
    } else if (segment->type == TrainingType::ENDURANCE) {
        icon = 505;
        content += SECONDS_SHORT;
    } else if (segment->type == TrainingType::FREEFORM) {
        icon = 588;
        content += RPM_SHORT;
    }

    // Bluetooth sessions may leave difficulty out; show no "/ " then.
    if (segment->difficulty.length() > 0) content += SLASH + segment->difficulty;

    drawTextPage(TextPage{
        .header = SEGMENT_HEADER,
        .icon = icon,
        .title = segment->name,
        .content = content.c_str(),
        .leftFooter = leftFooter.c_str(),
        .rightFooter = NEXT_HOLD_PLAY,
        .timeout = session.handsFreeMode ? DETAIL_TIMEOUT_HANDS_FREE_MS
                                         : DETAIL_TIMEOUT_MS,
        .center = true,
    });
};

constexpr auto drawBegin = []() {
    const auto segment = copySegmentByIdx(session.segments, session.segmentIdx);
    if (!segment.has_value()) {
        ESP_LOGD(ACTIONS_TAG, "Segment not found for idx %d", session.segmentIdx);
        process_fail();
        return;
    }

    ESP_LOGD(ACTIONS_TAG, "Drawing begin 3");

    drawTextPage(TextPage{.header = segment->name,
                          .icon = 296,
                          .content = STARTING_IN_3,
                          .center = true,
                          .y = 15});
    vTaskDelay(1000 / portTICK_PERIOD_MS);

    ESP_LOGD(ACTIONS_TAG, "Drawing 2");
    drawTextPage(TextPage{
        .header = segment->name,
        .icon = 284,
        .content = STARTING_IN_2,
        .center = true,
        .y = 15,
    });
    vTaskDelay(1000 / portTICK_PERIOD_MS);

    ESP_LOGD(ACTIONS_TAG, "Drawing 1");
    drawTextPage(TextPage{
        .header = segment->name,
        .icon = 295,
        .content = STARTING_IN_1,
        .center = true,
        .y = 15,
    });
    vTaskDelay(1000 / portTICK_PERIOD_MS);
    drawTextPage(TextPage{
        .header = segment->name,
        .icon = 282,
        .content = STARTING_IN_0,
        .center = true,
        .y = 15,
    });
    vTaskDelay(1000 / portTICK_PERIOD_MS);
    process_done(false);
};

constexpr auto applyRequestedSession =
    [](const session_replace_requested &request) {
        TrainingGuard guard(trainingMutex);
        if (trainingLifecycle.active()) return;
        currentSegment.reset();
        request.applied = request.apply();
    };

constexpr auto recoverMissingSegment = []() {
    TrainingGuard guard(trainingMutex);
    // Recovery must not reload the same corrupt cache into a countdown loop.
    // A later preflight can fetch validated dashboard settings normally.
    session = Session{};
    sessionLoadComplete = true;
};

constexpr auto drawGrade = []() {
    TrainingGuard guard(trainingMutex);
    if (!currentSegment) return;
    int grade = currentSegment->grade();
    int icon = 482;
    String content = EMPTY_STRING;
    String title = String(grade) + "%";

    if (grade >= 100) {
        icon = 502;
        content = GRADE_100;
        setLed(LED_GREEN);
    } else if (grade >= 90) {
        icon = 658;
        content = GRADE_90;
        setLed(LED_GREEN);
    } else if (grade >= 80) {
        icon = 587;
        content = GRADE_80;
        setLed(LED_GREEN);
    } else if (grade >= 70) {
        icon = 228;
        content = GRADE_70;
        setLed(LED_GREEN);
    } else if (grade == 69) {
        icon = 269;
        content = GRADE_69;
        setLed(LED_GREEN);
    } else if (grade >= 60) {
        icon = 290;
        content = GRADE_60;
        setLed(LED_YELLOW);
    } else if (grade >= 50) {
        icon = 592;
        content = GRADE_50;
        setLed(LED_YELLOW);
    } else if (grade >= 40) {
        icon = 483;
        content = GRADE_40;
        setLed(LED_YELLOW);
    } else if (grade >= 30) {
        icon = 253;
        content = GRADE_30;
        setLed(LED_RED);
    } else if (grade >= 20) {
        icon = 241;
        content = GRADE_20;
        setLed(LED_RED);
    } else {
        icon = 323;
        content = GRADE_0;
        setLed(LED_RED);
    }

    const Segment *segment = getSegmentByIdx(session.segmentIdx);
    if (segment == nullptr) {
        ESP_LOGD(ACTIONS_TAG, "Segment not found for idx %d", session.segmentIdx);
        return;
    }

    drawTextPage(TextPage{.header = segment->name,
                          .icon = icon,
                          .title = title.c_str(),
                          .content = content.c_str(),
                          .rightFooter = NEXT,
                          .timeout = session.handsFreeMode
                                         ? RESULT_TIMEOUT_HANDS_FREE_MS
                                         : RESULT_TIMEOUT_MS,
                          .center = true});
};

constexpr auto evaluateAndIncrementFailure = []() {
    TrainingGuard guard(trainingMutex);
    if (!currentSegment) return;
    const Segment* segment = getSegmentByIdx(session.segmentIdx);
    if (segment == nullptr) {
        ESP_LOGD(ACTIONS_TAG, "Segment not found for idx %d", session.segmentIdx);
        return;
    }

    if (!segment->passFail.enabled) {
        ESP_LOGD(ACTIONS_TAG, "Pass/fail not enabled for segment");
        return;
    }

    int grade = currentSegment->grade();
    bool passed = (grade >= segment->passFail.threshold);

    ESP_LOGD(ACTIONS_TAG, "Pass/fail evaluation: grade=%d, threshold=%d, passed=%d",
             grade, segment->passFail.threshold, passed);

    if (passed) {
        session.segmentFailureCounts[segment->id] = 0;
        ESP_LOGD(ACTIONS_TAG, "Segment passed, reset failure counter");
    } else {
        session.segmentFailureCounts[segment->id]++;
        int failureCount = session.segmentFailureCounts[segment->id];
        ESP_LOGD(ACTIONS_TAG, "Segment failed, count=%d", failureCount);
    }
};

constexpr auto evaluatePassFail = []() {
    TrainingGuard guard(trainingMutex);
    if (!currentSegment) return;
    const Segment* segment = getSegmentByIdx(session.segmentIdx);
    if (segment == nullptr) {
        ESP_LOGD(ACTIONS_TAG, "Segment not found for idx %d", session.segmentIdx);
        process_done(false);
        return;
    }

    if (!segment->passFail.enabled) {
        ESP_LOGD(ACTIONS_TAG, "Pass/fail not enabled for segment");
        process_done(false);
        return;
    }

    int grade = currentSegment->grade();
    bool passed = (grade >= segment->passFail.threshold);
    int failureCount = session.segmentFailureCounts[segment->id];

    if (passed) {
        process_done(false);
    } else {
        if (failureCount >= 3) {
            process_three_strikes();
        } else {
            process_segment_failed();
        }
    }
};

constexpr auto drawFailureScreen = []() {
    TrainingGuard guard(trainingMutex);
    if (!currentSegment) return;
    const Segment* segment = getSegmentByIdx(session.segmentIdx);
    if (segment == nullptr) {
        ESP_LOGD(ACTIONS_TAG, "Segment not found for idx %d", session.segmentIdx);
        return;
    }
    int failureCount = session.segmentFailureCounts[segment->id];

    int grade = currentSegment->grade();

    String failureText = segment->passFail.failureText.length() > 0
        ? segment->passFail.failureText
        : String(FAILED_DEFAULT_TEXT);

    String attemptText = String(FAILED_ATTEMPT_PREFIX) +
                        String(failureCount) +
                        String(FAILED_ATTEMPT_SUFFIX);

    String title = String(grade) + "% - " + attemptText;

    drawTextPage(TextPage{
        .header = segment->name,
        .icon = 323,
        .title = title.c_str(),
        .content = failureText.c_str(),
        .rightFooter = FAILED_PRESS_TO_RETRY,
        .showButton = true,
        .timeout = session.handsFreeMode ? RESULT_TIMEOUT_HANDS_FREE_MS
                                         : RESULT_TIMEOUT_MS,
        .center = true
    });

    setLed(LED_RED);
};

constexpr auto drawGradeOrFailure = []() {
    TrainingGuard guard(trainingMutex);
    if (!currentSegment) return;
    evaluateAndIncrementFailure();

    const Segment* segment = getSegmentByIdx(session.segmentIdx);
    if (segment == nullptr) {
        ESP_LOGD(ACTIONS_TAG, "Segment not found for idx %d", session.segmentIdx);
        return;
    }
    int grade = currentSegment->grade();
    const bool failed =
        segment->passFail.enabled && grade < segment->passFail.threshold;
#if DTT_ENABLE_RAD_BLE
    // Builds without Bluetooth skip the lookup as well as the call.
    radBleSegmentCompleted(
        session.segmentIdx, grade,
        segment->passFail.enabled ? (failed ? 0 : 1) : -1,
        segment->passFail.enabled ? session.segmentFailureCounts[segment->id]
                                  : 0);
#endif

    if (failed) {
        drawFailureScreen();
    } else {
        drawGrade();
    }
};

constexpr auto drawFinalPage = []() {
    TextPage page = {
        .title = "Session Complete!",
        .rightFooter = PAGE_FINAL_RIGHT_FOOTER,
        .showButton = true,
        .timeout = 10000,
        .center = true
    };

    if (session.finalText.length() > 0) {
        page.tagline = session.finalText;
    }

    if (session.finalColor.has_value()) {
        setLed(session.finalColor.value());
    } else {
        setLed(LED_MAGENTA);
    }

    drawTextPage(page);
};

constexpr auto drawThreeStrikesScreen = []() {
    drawTextPage(TextPage{
        .header = THREE_STRIKES_HEADER,
        .icon = 483,
        .content = THREE_STRIKES_CONTENT,
        .leftFooter = THREE_STRIKES_FOOTER,
        .rightFooter = "Restart",
        .showButton = true,
        .timeout = 5000,
        .center = true
    });

    setLed(LED_RED);
};

constexpr auto restartTraining = []() {
    TrainingGuard guard(trainingMutex);
    session.id = uuid();
    session.segmentFailureCounts.clear();
    session.segmentIdx = 0;
    session.hasSeenSessionDetails = false;
    process_done(false);
};

constexpr auto retrySegment = []() {
    process_done(false);
};

#endif  // PROVISION

#endif  // ACTIONS_HPP
