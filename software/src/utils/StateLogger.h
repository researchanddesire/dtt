#ifndef STATELOGGER_H
#define STATELOGGER_H

#include <Arduino.h>

#include <boost/sml.hpp>
#include <cassert>

#include "esp_log.h"

namespace sml = boost::sml;
using namespace sml;

#define STATE_MACHINE_TAG "STATE_MACHINE"

/**
 * @brief Logs state machine events for the OSSM class.
 *
 * The StateLogger class is responsible for logging the events of the state
 * machine used in the OSSM class. The logging level can be adjusted according
 * to the project's needs. By default, only messages with a level of "LOG_DEBUG"
 * or above are shown. This can be modified in the platformio.ini file or by
 * adding one of the following build flags:
 */
struct StateLogger {
    template <class SM, class TEvent>
    [[gnu::used]] static void log_process_event(const TEvent &) {
        ESP_LOGV(STATE_MACHINE_TAG, "%s", sml::aux::get_type_name<SM>());
        const char *eventName = sml::aux::get_type_name<TEvent>();

        // Print boost::ext::sml internal events as verbose
        if (strstr(eventName, "boost::ext::sml") != nullptr) {
            // Special handling for on_entry/on_exit
            if (strstr(eventName, "on_entry") != nullptr) {
                ESP_LOGV(STATE_MACHINE_TAG, "[on_entry] %s", eventName);
            } else if (strstr(eventName, "on_exit") != nullptr) {
                ESP_LOGV(STATE_MACHINE_TAG, "[on_exit] %s", eventName);
            } else {
                ESP_LOGV(STATE_MACHINE_TAG, "%s", eventName);
            }
        } else {
            ESP_LOGD(STATE_MACHINE_TAG, "%s", eventName);
        }
    }

    template <class SM, class TGuard, class TEvent>
    [[gnu::used]] static void log_guard(const TGuard &, const TEvent &,
                                        bool result) {
        const char *resultString = result ? "[PASS]" : "[DO NOT PASS]";
        ESP_LOGV(STATE_MACHINE_TAG, "%s: %s", resultString,
                 sml::aux::get_type_name<SM>());
        ESP_LOGD(STATE_MACHINE_TAG, "%s: %s, %s", resultString,
                 sml::aux::get_type_name<TGuard>(),
                 sml::aux::get_type_name<TEvent>());
    }

    template <class SM, class TAction, class TEvent>
    [[gnu::used]] static void log_action(const TAction &, const TEvent &) {
        ESP_LOGV(STATE_MACHINE_TAG, "%s", sml::aux::get_type_name<SM>());
    }

    template <class SM, class TSrcState, class TDstState>
    [[gnu::used]] static void log_state_change(const TSrcState &src,
                                               const TDstState &dst) {
        ESP_LOGD(STATE_MACHINE_TAG, "%s: %s -> %s",
                 sml::aux::get_type_name<SM>(), src.c_str(), dst.c_str());
    }
};
#endif  // STATELOGGER_H
