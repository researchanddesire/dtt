#pragma once

#include "FirmwareUpdateProtocol.h"
#include "FirmwareProvenance.h"

#if defined(ARDUINO_ARCH_ESP32)

#include <Arduino.h>
#include <esp_partition.h>

namespace firmware {

bool postCheck(const char *apiBaseUrl, const DeviceReport &report,
               Decision &decision, String &error);

bool installStreamedArtifact(const Artifact &artifact, int updateCommand,
                             String &error);

bool installApplicationAndFilesystem(const Decision &decision, String &error);

// Downloads an artifact into a flash region the caller owns instead of the
// active OTA slot, and verifies its size and SHA-256 from flash afterwards.
// The caller decides when, and whether, that region becomes bootable.
bool downloadArtifactToPartition(const Artifact &artifact,
                                 const esp_partition_t *destination,
                                 String &error);

}  // namespace firmware

#endif
