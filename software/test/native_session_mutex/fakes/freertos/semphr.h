#pragma once

#include <atomic>
#include <chrono>
#include <mutex>
#include <thread>

#include "FreeRTOS.h"

struct NativeSemaphore {
    std::recursive_timed_mutex lock;
    std::mutex metadata;
    std::thread::id owner;
    unsigned depth = 0;
};
using SemaphoreHandle_t = NativeSemaphore *;
inline std::atomic<unsigned> finiteBlockingCalls{0};

inline SemaphoreHandle_t xSemaphoreCreateRecursiveMutex() {
    return new NativeSemaphore;
}
inline void vSemaphoreDelete(SemaphoreHandle_t value) { delete value; }
inline int xSemaphoreTakeRecursive(SemaphoreHandle_t value, TickType_t wait) {
    bool acquired;
    if (wait == portMAX_DELAY) {
        value->lock.lock();
        acquired = true;
    } else if (wait == 0) {
        acquired = value->lock.try_lock();
    } else {
        // Accelerate finite timeout expiry while retaining the FreeRTOS
        // contract: failure must not transfer mutex ownership to the caller.
        ++finiteBlockingCalls;
        acquired = value->lock.try_lock_for(std::chrono::milliseconds(1));
    }
    if (!acquired) return pdFALSE;
    std::lock_guard<std::mutex> guard(value->metadata);
    value->owner = std::this_thread::get_id();
    ++value->depth;
    return pdTRUE;
}
inline int xSemaphoreGiveRecursive(SemaphoreHandle_t value) {
    {
        std::lock_guard<std::mutex> guard(value->metadata);
        if (value->depth == 0 || value->owner != std::this_thread::get_id())
            return pdFALSE;
        if (--value->depth == 0) value->owner = {};
    }
    value->lock.unlock();
    return pdTRUE;
}
