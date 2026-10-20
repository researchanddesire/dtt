#ifndef HANDLES_H
#define HANDLES_H

// clang-format off
#include "freertos/FreeRTOS.h"
#include <freertos/task.h>
// clang-format on

#include "Arduino.h"

extern TaskHandle_t processWifiTaskHandle;
extern TaskHandle_t preflightChecksTaskHandle;
extern TaskHandle_t drawBatteryTaskHandle;
extern TaskHandle_t drawButtonTaskHandle;
extern TaskHandle_t updateTaskHandle;

constexpr char updateTaskName PROGMEM[] = "updateTask";
constexpr char processWifiTaskName PROGMEM[] = "processWifiTask";
constexpr char preflightChecksTaskName PROGMEM[] = "preflightChecksTask";
constexpr char drawBatteryTaskName PROGMEM[] = "drawBatteryTask";
constexpr char drawButtonTaskName PROGMEM[] = "drawButtonTask";

extern TaskHandle_t provisionTaskHandle;
constexpr char provisionTaskName PROGMEM[] = "provisionTask";

#ifndef PROVISION
extern TaskHandle_t getDistanceTaskHandle;
extern TaskHandle_t drawPlayModeTaskHandle;
extern TaskHandle_t saveResultsTaskHandle;
extern TaskHandle_t welcomeTaskHandle;
extern TaskHandle_t fetchSettingsTaskHandle;
extern TaskHandle_t loadSessionTaskHandle;
extern TaskHandle_t checkIfPairedTaskHandle;
extern TaskHandle_t notifyTrainingTaskHandle;

constexpr char ledsTaskName PROGMEM[] = "ledsTask";
constexpr char distanceTaskName PROGMEM[] = "distanceTask";
constexpr char drawPlayModeTaskName PROGMEM[] = "drawPlayModeTask";
constexpr char saveResultsTaskName PROGMEM[] = "saveResultsTask";
constexpr char welcomeTaskName PROGMEM[] = "welcomeTask";
constexpr char fetchSettingsTaskName PROGMEM[] = "fetchSettingsTask";
constexpr char loadSessionTaskName PROGMEM[] = "loadSessionTask";
constexpr char checkIfPairedTaskName PROGMEM[] = "checkIfPairedTask";
constexpr char notifyTrainingTaskName PROGMEM[] = "notifyTrainingTask";
#endif  // PROVISION

#endif  // HANDLES_H
