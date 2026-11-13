#pragma once

#include <cmath>
#include <cstdint>
#include <string>

// Access is serialized by the firmware's training mutex. Generation tokens
// distinguish cooperative workers from later attempts of the same segment.
class TrainingLifecycle {
    std::uint32_t generation_ = 0;
    bool enabled_ = false;
    bool active_ = false;
    bool sensorReady_ = false;
    std::string notifiedSession_;

  public:
    std::uint32_t begin() {
        if (++generation_ == 0) ++generation_;
        enabled_ = true;
        active_ = false;
        sensorReady_ = false;
        return generation_;
    }
    bool current(std::uint32_t generation) const {
        return enabled_ && generation == generation_;
    }
    bool activate(std::uint32_t generation) {
        if (!current(generation) || !sensorReady_) return false;
        active_ = true;
        return true;
    }
    void stop() { enabled_ = active_ = sensorReady_ = false; }
    bool prepareSensor(std::uint32_t generation) {
        if (!current(generation)) return false;
        sensorReady_ = true;
        return true;
    }
    bool sensorReady(std::uint32_t generation) const {
        return current(generation) && sensorReady_;
    }
    bool active() const { return enabled_ && active_; }
    bool mayComplete(std::uint32_t generation, bool naturalEnd) const {
        return current(generation) && active() && naturalEnd;
    }
    bool reserveNotification(std::uint32_t generation, const std::string& session) {
        if (!current(generation) || !active() || session.empty() || session == notifiedSession_)
            return false;
        // Reserve before spawning/posting: an ambiguous POST is never retried.
        notifiedSession_ = session;
        return true;
    }
};

inline float trainingSpeedCmPerSecond(float previous, float next,
                                      std::uint32_t elapsedMicros) {
    if (!elapsedMicros || !std::isfinite(previous) || !std::isfinite(next)) return 0;
    return (next - previous) * 1000000.0f / static_cast<float>(elapsedMicros);
}
