#include "handles.h"

TaskHandle_t processWifiTaskHandle;
TaskHandle_t preflightChecksTaskHandle;
TaskHandle_t drawBatteryTaskHandle;
TaskHandle_t drawButtonTaskHandle;
TaskHandle_t updateTaskHandle;

#ifdef PROVISION
TaskHandle_t provisionTaskHandle;
#endif

#ifndef PROVISION
TaskHandle_t getDistanceTaskHandle;
TaskHandle_t drawPlayModeTaskHandle;
TaskHandle_t saveResultsTaskHandle;
TaskHandle_t welcomeTaskHandle;
TaskHandle_t fetchSettingsTaskHandle;
TaskHandle_t loadSessionTaskHandle;
TaskHandle_t checkIfPairedTaskHandle;
TaskHandle_t notifyTrainingTaskHandle;
#endif  // PROVISION
