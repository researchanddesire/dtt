#include "utils.h"

#include "events.hpp"
#include "state/state.h"

void process_done(const bool delay) {
    if (delay) {
        vTaskDelay(2000 / portTICK_PERIOD_MS);
    }
    stateMachine->process_event(done{});
}

void process_fail() {
    stateMachine->process_event(fail{});
}

void process_preflight_done(const bool delay) {
    if (delay) {
        vTaskDelay(2000 / portTICK_PERIOD_MS);
    }
    stateMachine->process_event(preflight_done{});
}

void process_update_complete() {
    stateMachine->process_event(update_complete{});
}

void process_update_failed() {
    stateMachine->process_event(update_failed{});
}

void process_segment_failed() {
    stateMachine->process_event(segment_failed{});
}

void process_three_strikes() {
    stateMachine->process_event(three_strikes{});
}
