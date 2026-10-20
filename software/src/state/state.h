#ifndef STATE_H
#define STATE_H

#include <utils/RecusiveMutex.h>

#include "machine.h"
#include "utils/StateLogger.h"

extern ESP32RecursiveMutex mutex;
extern StateLogger stateLogger;

extern sml::sm<dtt_state_machine, sml::thread_safe<ESP32RecursiveMutex>,
               sml::logger<StateLogger>> *stateMachine;

// Initialize the state machine
void initStateMachine();

#endif  // STATE_H