#pragma once

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

// The ESP32 TLS buffers need contiguous RAM. Share one request slot between
// application preflight, pairing, firmware updates and the staging observer.
class NetworkRequestLock {
  public:
    explicit NetworkRequestLock(TickType_t wait = portMAX_DELAY)
        : held_(xSemaphoreTake(semaphore_, wait) == pdTRUE) {}
    ~NetworkRequestLock() { if (held_) xSemaphoreGive(semaphore_); }
    explicit operator bool() const { return held_; }
    NetworkRequestLock(const NetworkRequestLock&) = delete;
    NetworkRequestLock& operator=(const NetworkRequestLock&) = delete;

  private:
    // Construct once before setup starts worker tasks; no allocation or lazy
    // initialization race between simultaneous callers.
    inline static StaticSemaphore_t storage_{};
    inline static const SemaphoreHandle_t semaphore_ = xSemaphoreCreateMutexStatic(&storage_);
    bool held_;
};
