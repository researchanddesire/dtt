#ifndef GUARDS_HPP
#define GUARDS_HPP
#include "events.hpp"
#include "wifiSettings.h"

template <typename Event = done>
constexpr auto isWifiConnected =
    [](const Event &event) { return WiFiClass::status() == WL_CONNECTED; };

template <typename Event = done>
constexpr auto isHealthCheckPassed =
    [](const Event &event) { return healthCheckPassed == true; };

template <typename Event = done>
constexpr auto isOnline = [](const Event &event) {
    return isWifiConnected<Event>(event) && isHealthCheckPassed<Event>(event);
};

template <typename Event = done>
constexpr auto isPaired =
    [](const Event &) -> bool { return dashboardState.isPaired; };

template <typename Event = done>
constexpr auto hasUpdate =
    [](const Event &) -> bool { return dashboardState.hasUpdate; };

template <typename Event = done>
constexpr auto preflightPending =
    [](const Event &) -> bool { return dashboardState.preflightPending; };

#ifndef PROVISION

template <typename Event = done>
constexpr auto hasNext =
    [](const Event &) { return session.segmentIdx < session.segmentCount - 1; };

template <typename Event = done>
constexpr auto isNextLoaded = [](const Event &) {
    return isSegmentLoaded(session.segmentIdx + 1);
};

template <typename Event = done>
constexpr auto hasToy =
    [](const Event &) -> bool { return session.toy.has_value(); };

template <typename Event = done>
constexpr auto hasSeenSessionDetails =
    [](const Event &) -> bool { return session.hasSeenSessionDetails; };

template <typename Event = done>
constexpr auto isHandsFreeMode =
    [](const Event &) -> bool { return session.handsFreeMode; };

template <typename Event = done>
constexpr auto isCalibrated = [](const Event &) -> bool {
    if (session.toy.has_value() && session.toy->calibration.isCalibrated) {
        return true;
    }
    return session.isCalibrated;
};

template <typename Event = done>
constexpr auto isPassFailEnabled =
    [](const Event &) -> bool {
        const Segment* segment = getSegmentByIdx(session.segmentIdx);
        if (segment == nullptr) {
            return false;
        }
        return segment->passFail.enabled;
    };

#endif  // PROVISION

#endif  // GUARDS_HPP