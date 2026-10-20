#pragma once

#ifndef DTT_ENABLE_RAD_BLE
#define DTT_ENABLE_RAD_BLE 0
#endif

#ifndef DTT_HARDWARE_VARIANT
#define DTT_HARDWARE_VARIANT "v1"
#endif

namespace dtt {

inline constexpr const char *HARDWARE_VARIANT = DTT_HARDWARE_VARIANT;
inline constexpr bool RAD_BLE_ENABLED = DTT_ENABLE_RAD_BLE == 1;

static_assert(DTT_ENABLE_RAD_BLE == 0 || DTT_ENABLE_RAD_BLE == 1,
              "DTT_ENABLE_RAD_BLE must be 0 or 1");

}  // namespace dtt
