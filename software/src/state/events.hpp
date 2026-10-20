#pragma once

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
struct request_pairing {};
struct force_update {};
