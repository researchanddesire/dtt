#include <cassert>
#include <future>
#include <iostream>

#include "../../src/utils/RecusiveMutex.h"

int main() {
    ESP32RecursiveMutex mutex;
    mutex.lock();
    assert(mutex.try_lock());
    mutex.unlock();

    std::promise<void> attempting;
    auto started = attempting.get_future();
    auto competitor = std::async(std::launch::async, [&] {
        assert(!mutex.try_lock());
        attempting.set_value();
        mutex.lock();
        mutex.unlock();
    });
    started.wait();
    assert(competitor.wait_for(std::chrono::milliseconds(20)) ==
           std::future_status::timeout);
    mutex.unlock();
    competitor.get();
    assert(finiteBlockingCalls == 0);
    assert(mutex.try_lock());
    mutex.unlock();
    std::cout << "Recursive mutex ownership and contention checks passed\n";
}
