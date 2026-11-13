#pragma once

#include <cstdint>
#include <optional>
#include <vector>

// Call while the session is stable. The returned value owns its strings and
// remains valid after the source vector is replaced or reallocated.
template <typename SegmentType>
std::optional<SegmentType> copySegmentByIdx(
    const std::vector<SegmentType> &segments, uint16_t index) {
    for (const auto &segment : segments)
        if (segment.idx == index) return segment;
    return std::nullopt;
}
