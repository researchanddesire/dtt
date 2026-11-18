#pragma once

#include <cctype>
#include <cstddef>
#include <cstdint>
#include <string>

namespace firmware {
namespace dtt {

constexpr std::uint32_t FOUR_MIB = 4U * 1024U * 1024U;
constexpr std::uint32_t SIXTEEN_MIB = 16U * 1024U * 1024U;

enum class MigrationAction {
    failClosed,
    relocateToApp0,
    writeBootloader,
    writePartitionTable,
    resolveFinalFirmware,
};

enum class BootloaderState {
    unapproved,
    legacy4MiB,
    migrated16MiB,
};

inline bool validTrainerId(const std::string &value) {
    if (value.size() != 32 && value.size() != 36) return false;
    for (std::size_t index = 0; index < value.size(); ++index) {
        const bool uuidSeparator =
            value.size() == 36 &&
            (index == 8 || index == 13 || index == 18 || index == 23);
        if (uuidSeparator) {
            if (value[index] != '-') return false;
        } else if (!std::isxdigit(static_cast<unsigned char>(value[index]))) {
            return false;
        }
    }
    return true;
}

inline MigrationAction nextMigrationAction(const bool legacyLayout,
                                           const bool v2Layout,
                                           const bool runningFromApp0,
                                           const std::uint32_t physicalFlash,
                                           const bool securityFeaturesEnabled,
                                           const BootloaderState bootloader) {
    if (securityFeaturesEnabled || physicalFlash < SIXTEEN_MIB ||
        bootloader == BootloaderState::unapproved) {
        return MigrationAction::failClosed;
    }
    if (v2Layout) {
        return bootloader == BootloaderState::migrated16MiB
                   ? MigrationAction::resolveFinalFirmware
                   : MigrationAction::failClosed;
    }
    if (!legacyLayout) return MigrationAction::failClosed;
    if (!runningFromApp0) return MigrationAction::relocateToApp0;
    return bootloader == BootloaderState::legacy4MiB
               ? MigrationAction::writeBootloader
               : MigrationAction::writePartitionTable;
}

// What the bridge does before it gives up the firmware it replaced. Every
// step that can fail runs first, while that firmware can still be booted.
enum class PreparationStep {
    refuse,
    stageFinalFirmware,
    proceed,
};

inline PreparationStep nextPreparationStep(const MigrationAction action,
                                           const bool legacyLayout,
                                           const bool identityValid,
                                           const bool finalFirmwareStaged) {
    if (action == MigrationAction::failClosed) return PreparationStep::refuse;
    // Under the 16 MiB table the old firmware is already gone; only the final
    // install is left.
    if (!legacyLayout) return PreparationStep::proceed;
    if (!identityValid) return PreparationStep::refuse;
    return finalFirmwareStaged ? PreparationStep::proceed
                               : PreparationStep::stageFinalFirmware;
}

// The staged final image lives in the future second application slot, below
// the sectors the bridge uses to stage the bootloader.
inline bool stagedFinalFirmwareFits(const std::uint32_t sizeBytes,
                                    const std::uint32_t stagingLimitBytes) {
    return sizeBytes > 0 && sizeBytes <= stagingLimitBytes;
}

}  // namespace dtt
}  // namespace firmware
