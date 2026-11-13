#pragma once

#include <DttHardwareVariant.h>

#if DTT_ENABLE_RAD_BLE
#include <RadBle.h>

extern radble::Server radBleServer;
#endif

bool initRadBle();
