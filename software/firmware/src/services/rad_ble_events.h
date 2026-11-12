#pragma once

#include <DttHardwareVariant.h>

#include <cstdint>

// Segment milestones for Bluetooth clients.
//
// Both calls record the milestone and return. The RadBLE worker publishes it
// on the event characteristic from its own task, so they are safe from any
// task and never touch the BLE server. Builds without Bluetooth compile them
// away.
#if DTT_ENABLE_RAD_BLE

// A segment began training. tipCm and deepCm are the segment's start and end
// positions; the live feed reports depth on that range until the next segment
// starts.
void radBleSegmentStarted(uint16_t segment, int type, int target, float tipCm,
                          float deepCm);

// A segment finished and was graded. passed is -1 when pass/fail is not
// enabled for the segment, otherwise 0 or 1. strikes is the segment's failure
// count after this attempt.
void radBleSegmentCompleted(uint16_t segment, int grade, int passed,
                            int strikes);

#else

inline void radBleSegmentStarted(uint16_t, int, int, float, float) {}
inline void radBleSegmentCompleted(uint16_t, int, int, int) {}

#endif
