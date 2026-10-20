#pragma once
#include <freertos/FreeRTOS.h>

namespace taskStacks {
// Staging/development V2 shares internal RAM with BLE and TLS. Keep generous margins over
// measured use (header 1956, button 580, LED 1036 bytes) without changing the
// production/V1 budgets. The state-monitor and network stacks stay unchanged.
#if (defined(RAD_HIL_VARIANT) || defined(VERSIONDEV)) && DTT_ENABLE_RAD_BLE
constexpr unsigned header = 4096;
constexpr unsigned button = 6144;
constexpr unsigned leds = 3072;
#else
constexpr unsigned header = 10 * configMINIMAL_STACK_SIZE;
constexpr unsigned button = 10 * configMINIMAL_STACK_SIZE;
constexpr unsigned leds = 5 * configMINIMAL_STACK_SIZE;
#endif
}
