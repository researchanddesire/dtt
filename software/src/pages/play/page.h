#ifndef PLAY_PAGE_H
#define PLAY_PAGE_H

#include <Arduino.h>

#include <CircularBuffer.hpp>

#define DISTANCE_BUFFER_SIZE 40
#define SPEED_BUFFER_SIZE 9

extern CircularBuffer<float, DISTANCE_BUFFER_SIZE> distanceBuffer;
extern CircularBuffer<float, SPEED_BUFFER_SIZE> speedBuffer;

void drawPlayModeTask(void *pvParameters);
void getDistanceTask(void *pvParameters);

#endif