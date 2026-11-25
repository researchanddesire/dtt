#include "state.h"
#include "services/radHil.h"
#include "services/hardwareHealth.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

StateLogger stateLogger;
// Static pointer to hold the state machine instance
sml::sm<dtt_state_machine, sml::thread_safe<ESP32RecursiveMutex>,
        sml::logger<StateLogger>> *stateMachine = nullptr;

[[noreturn]] void stateMonitorTask(void *pvParameters) {
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(500));
        // Pairing and session-detail pages wait for user input without running
        // training. Querying the ordinary state monitor also exercises its mutex.
        const bool idleAndReady = stateMachine->is("pairing"_s) ||
                                  stateMachine->is("play.details.session"_s) ||
                                  stateMachine->is("play.details.segment"_s) ||
                                  stateMachine->is("play.details.toy"_s);
        radHilProgress(idleAndReady);
        hardwareHealthHeartbeat(idleAndReady);
#ifdef RAD_HIL_VARIANT
        // Emit only constant state names, never session or calibration values.
        // This makes startup failures diagnosable in quiet staging builds.
        static const char* previous = nullptr;
        stateMachine->visit_current_states([&](auto state) {
            const char* current = state.c_str();
            if (previous != current) {
                printf("RAD_STATE %s\n", current);
                previous = current;
            }
        });
#endif

#ifndef PROVISION
        if (stateMachine->is("play.preflight"_s)) {
            stateMachine->process_event(done{});
        }
#endif
    }
}

void initStateMachine() {
    if (stateMachine == nullptr) {
        stateMachine = new sml::sm<dtt_state_machine,
                                   sml::thread_safe<ESP32RecursiveMutex>,
                                   sml::logger<StateLogger>>(stateLogger);

        // Start state monitor task
        xTaskCreatePinnedToCore(stateMonitorTask, "stateMonitor",
                                4 * configMINIMAL_STACK_SIZE, nullptr,
                                tskIDLE_PRIORITY, nullptr, 1);

#ifdef PROVISION
        delay(5000);
#else
        stateMachine->process_event(done{});
#endif
    }
}
