#pragma once

#include <cmath>
#include <cstddef>
#include <cstdint>

// Compact training sample and segment events for Bluetooth clients.
//
// A stream frame is the sample JSON after RadBLE's 20-byte header. A central
// that negotiates ATT MTU 185 receives at most 182 bytes per notification, so
// the sample stays within TRAINING_FEED_SAMPLE_MAX_BYTES for every input.
// Numbers have bounded widths and use no floating-point formatting.
constexpr std::size_t TRAINING_FEED_SAMPLE_MAX_BYTES = 160;
constexpr std::size_t TRAINING_FEED_EVENT_MAX_BYTES = 96;

// Depth scale in thousandths: 0 is the tip position and 1000 the deep
// position. Readings beyond either end keep their value up to this limit.
constexpr int TRAINING_FEED_SCALE_LIMIT = 9999;
constexpr int TRAINING_FEED_NO_VALUE = INT32_MIN;

// Places a sensor distance on the depth scale. Returns TRAINING_FEED_NO_VALUE
// when the distance or the tip-to-deep range cannot be used.
inline int trainingFeedScale(const float distanceCm, const float tipCm,
                             const float deepCm) {
    const float range = tipCm - deepCm;
    if (!std::isfinite(distanceCm) || !std::isfinite(range) || range <= 0.0f)
        return TRAINING_FEED_NO_VALUE;
    const float scaled = (tipCm - distanceCm) * 1000.0f / range;
    if (scaled >= static_cast<float>(TRAINING_FEED_SCALE_LIMIT))
        return TRAINING_FEED_SCALE_LIMIT;
    if (scaled <= static_cast<float>(-TRAINING_FEED_SCALE_LIMIT))
        return -TRAINING_FEED_SCALE_LIMIT;
    return static_cast<int>(std::lround(scaled));
}

struct TrainingFeedSample {
    // Index of the segment the values describe.
    std::uint16_t segment = 0;
    // False when there is no segment to describe; the remaining fields are
    // then null.
    bool available = false;
    int depth = TRAINING_FEED_NO_VALUE;  // depth scale, thousandths
    int positionState = 0;               // TrainingPosition
    int trainingState = 0;               // TrainingState
    std::uint32_t strokes = 0;
    float progress = 0.0f;  // 0..1
    int grade = 0;          // 0..100
    // Target window edges on the depth scale, shallow edge first.
    // TRAINING_FEED_NO_VALUE when the segment has no positional window.
    int windowStart = TRAINING_FEED_NO_VALUE;
    int windowEnd = TRAINING_FEED_NO_VALUE;
};

struct TrainingFeedEvent {
    enum Kind : std::uint8_t { SegmentStarted, SegmentCompleted };
    Kind kind = SegmentStarted;
    std::uint16_t segment = 0;
    // SegmentStarted
    std::uint8_t type = 0;     // TrainingType
    std::uint32_t target = 0;  // repetitions or seconds, as defined
    // SegmentCompleted
    std::uint8_t grade = 0;   // 0..100
    std::int8_t passed = -1;  // -1 pass/fail not enabled, 0 failed, 1 passed
    std::uint8_t strikes = 0;
};

namespace trainingfeed {

    inline int limited(const int value, const int low, const int high) {
        return value < low ? low : value > high ? high : value;
    }

    // Bounded JSON writer. finish() returns 0 when the text did not fit.
    class Writer {
      public:
        Writer(char* out, const std::size_t capacity)
            : out_(out), capacity_(capacity) {}

        void text(const char* value) {
            while (*value != '\0') put(*value++);
        }

        void number(std::uint32_t value) {
            char digits[10];
            std::size_t count = 0;
            do {
                digits[count++] = static_cast<char>('0' + value % 10U);
                value /= 10U;
            } while (value != 0U);
            while (count > 0) put(digits[--count]);
        }

        // Writes thousandths as a decimal with three places, or null. Values
        // outside the scale limit are written at the limit.
        void thousandths(const int value) {
            if (value == TRAINING_FEED_NO_VALUE) return text("null");
            const int bounded = limited(value, -TRAINING_FEED_SCALE_LIMIT,
                                        TRAINING_FEED_SCALE_LIMIT);
            if (bounded < 0) put('-');
            const auto magnitude =
                static_cast<std::uint32_t>(bounded < 0 ? -bounded : bounded);
            number(magnitude / 1000U);
            put('.');
            put(static_cast<char>('0' + magnitude / 100U % 10U));
            put(static_cast<char>('0' + magnitude / 10U % 10U));
            put(static_cast<char>('0' + magnitude % 10U));
        }

        std::size_t finish() {
            if (capacity_ == 0) return 0;
            out_[length_] = '\0';
            return overflowed_ ? 0 : length_;
        }

      private:
        void put(const char value) {
            if (length_ + 1 < capacity_)
                out_[length_++] = value;
            else
                overflowed_ = true;
        }

        char* out_;
        std::size_t capacity_;
        std::size_t length_ = 0;
        bool overflowed_ = false;
    };

}  // namespace trainingfeed

// Writes the sample as JSON and returns its length without the terminator, or
// 0 when capacity is too small. TRAINING_FEED_SAMPLE_MAX_BYTES + 1 always fits.
inline std::size_t writeTrainingFeedSample(const TrainingFeedSample& sample,
                                           char* out,
                                           const std::size_t capacity) {
    trainingfeed::Writer json(out, capacity);
    json.text("{\"segment\":");
    json.number(sample.segment);
    if (!sample.available) {
        json.text(
            ",\"depth\":null,\"posState\":null,\"trainState\":null,"
            "\"strokes\":null,\"progress\":null,\"grade\":null,"
            "\"windowStart\":null,\"windowEnd\":null}");
        return json.finish();
    }
    int progress = 0;
    if (std::isfinite(sample.progress) && sample.progress > 0.0f)
        progress =
            sample.progress >= 1.0f
                ? 1000
                : static_cast<int>(std::lround(sample.progress * 1000.0f));
    json.text(",\"depth\":");
    json.thousandths(sample.depth);
    json.text(",\"posState\":");
    json.number(static_cast<std::uint32_t>(
        trainingfeed::limited(sample.positionState, 0, 9)));
    json.text(",\"trainState\":");
    json.number(static_cast<std::uint32_t>(
        trainingfeed::limited(sample.trainingState, 0, 9)));
    json.text(",\"strokes\":");
    json.number(sample.strokes);
    json.text(",\"progress\":");
    json.thousandths(progress);
    json.text(",\"grade\":");
    json.number(static_cast<std::uint32_t>(
        trainingfeed::limited(sample.grade, 0, 100)));
    json.text(",\"windowStart\":");
    json.thousandths(sample.windowStart);
    json.text(",\"windowEnd\":");
    json.thousandths(sample.windowEnd);
    json.text("}");
    return json.finish();
}

// Writes the event as JSON and returns its length without the terminator, or
// 0 when capacity is too small. TRAINING_FEED_EVENT_MAX_BYTES + 1 always fits.
inline std::size_t writeTrainingFeedEvent(const TrainingFeedEvent& event,
                                          char* out,
                                          const std::size_t capacity) {
    trainingfeed::Writer json(out, capacity);
    if (event.kind == TrainingFeedEvent::SegmentStarted) {
        json.text("{\"event\":\"segment.started\",\"segment\":");
        json.number(event.segment);
        json.text(",\"type\":");
        json.number(event.type);
        json.text(",\"target\":");
        json.number(event.target);
        json.text("}");
        return json.finish();
    }
    json.text("{\"event\":\"segment.completed\",\"segment\":");
    json.number(event.segment);
    json.text(",\"grade\":");
    json.number(
        static_cast<std::uint32_t>(trainingfeed::limited(event.grade, 0, 100)));
    json.text(",\"passed\":");
    json.text(event.passed < 0 ? "null" : event.passed == 0 ? "false" : "true");
    json.text(",\"strikes\":");
    json.number(event.strikes);
    json.text("}");
    return json.finish();
}
