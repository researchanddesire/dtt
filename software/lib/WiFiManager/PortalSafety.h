#pragma once

#include <cstdint>
#include <memory>

namespace portal_safety {
    // Unsigned elapsed time remains correct when the millisecond clock wraps.
    inline uint32_t remaining(uint32_t start, uint32_t duration, uint32_t now) {
        const uint32_t elapsed = now - start;
        return elapsed >= duration ? 0 : duration - elapsed;
    }

    template <typename Server, typename Address>
    std::unique_ptr<Server> makeServer(bool captive, const Address &apAddress,
                                       uint16_t port) {
        if (captive)
            return std::unique_ptr<Server>(new Server(apAddress, port));
        return std::unique_ptr<Server>(new Server(port));
    }
}  // namespace portal_safety
