#pragma once

#include "FirmwareUpdateProtocol.h"
#include "FirmwareProvenance.h"

#if defined(ARDUINO_ARCH_ESP32)

#include <Arduino.h>

namespace firmware {

bool postCheck(const char *apiBaseUrl, const DeviceReport &report,
               Decision &decision, String &error);

bool installStreamedArtifact(const Artifact &artifact, int updateCommand,
                             String &error);

bool installApplicationAndFilesystem(const Decision &decision, String &error);

}  // namespace firmware

#endif
