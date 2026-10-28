#ifndef PLAY_PAGE_H
#define PLAY_PAGE_H

#include <Arduino.h>

#include <CircularBuffer.hpp>

// Sampled at 120 Hz: 15 positions average ~125 ms, matching the original
// firmware's 40-sample window at roughly 330 Hz.
#define DISTANCE_BUFFER_SIZE 15
#define SPEED_BUFFER_SIZE 9

extern CircularBuffer<float, DISTANCE_BUFFER_SIZE> distanceBuffer;
extern CircularBuffer<float, SPEED_BUFFER_SIZE> speedBuffer;

void drawPlayModeTask(void *pvParameters);
void getDistanceTask(void *pvParameters);
bool startTrainingTasks(uint32_t drawStackBytes, uint32_t sensorStackBytes);
void stopTrainingRun();

#endif
