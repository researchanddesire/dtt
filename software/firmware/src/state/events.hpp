#pragma once

#include <functional>
#include <cstdint>

struct timeout {};

struct button_pressed {};
struct button_double_pressed {};
struct button_long_pressed {};
struct button_multiple_pressed {
    unsigned char count = 0;
};

struct timeout_expired {};

struct done {};
struct fail {};
struct preflight_done {};
struct wifi_configured {};
struct provision_complete {};
struct provision_failed {};
struct update_complete {};
struct update_failed {};
struct recalibrate {};
struct segment_failed {};
struct three_strikes {};
struct restart_training {};
struct training_worker_finished { std::uint32_t generation; };
// outOfMemory: the run could not get memory or a task for itself. The
// session is fine, so it is kept; any other failure discards it.
struct training_worker_failed {
    std::uint32_t generation;
    bool outOfMemory = false;
};
struct request_pairing {};
struct force_update {};

// Synchronous application under the state machine's recursive lock. Only
// states without an active training task accept replacement requests.
struct session_replace_requested {
    std::function<bool()> apply;
    bool &applied;
};

struct session_load_ready {
    std::function<bool()> apply;
    bool &applied;
};

struct session_load_failed {};
