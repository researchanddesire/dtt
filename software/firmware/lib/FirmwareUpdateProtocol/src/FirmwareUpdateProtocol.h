#pragma once

#include <ArduinoJson.h>

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <string>

namespace firmware {

constexpr int PROTOCOL_VERSION = 1;
constexpr std::size_t MAX_ARTIFACTS = 8;

inline bool isRedirectStatus(const int status) {
    return status >= 300 && status < 400;
}

inline bool isResponseLengthAllowed(const int contentLength,
                                    const std::size_t maximumBytes) {
    return contentLength != 0 &&
           (contentLength < 0 ||
            static_cast<std::size_t>(contentLength) <= maximumBytes);
}

inline bool knownContentLengthMatches(const int contentLength,
                                      const std::size_t expectedBytes) {
    return contentLength < 0 ||
           static_cast<std::size_t>(contentLength) == expectedBytes;
}

inline bool transferCompleted(const int receivedBytes,
                              const std::size_t writtenBytes,
                              const std::size_t expectedBytes) {
    return receivedBytes >= 0 &&
           static_cast<std::size_t>(receivedBytes) == writtenBytes &&
           writtenBytes == expectedBytes;
}

struct DeviceReport {
    int protocolVersion = PROTOCOL_VERSION;
    std::string deviceType;
    std::string deviceId;
    std::string reportedTrack;
    std::string currentVersion;
    std::string currentBuild;
    std::string firmwareHash;
    int provenanceCapability = 1;
    std::string firmwareProvenance;
    std::string chip;
    std::uint32_t chipRevision = 0;
    std::uint32_t chipCores = 0;
    std::string hardwareRevision;
    std::uint32_t flashSizeBytes = 0;
    std::uint32_t otaSlotSizeBytes = 0;
    std::uint32_t psramSizeBytes = 0;
    std::string partitionLayout;
    std::string partitionTableHash;
    std::string bootloaderHash;
};

struct Artifact {
    std::string role;
    std::string url;
    std::string sha256;
    std::uint32_t sizeBytes = 0;
    int installOrder = 0;
};

struct Decision {
    int protocolVersion = PROTOCOL_VERSION;
    bool shouldUpdate = false;
    // Compatibility mirror for firmware deployed before shouldUpdate became
    // the canonical decision field.
    bool updateAvailable = false;
    std::string reason;
    std::string reportedTrack;
    std::string assignedTrack;
    bool trackChanged = false;
    std::string currentVersion;
    std::string targetVersion;
    std::string nextHopVersion;
    std::string releaseId;
    std::string buildSha;
    std::string firmwareOrigin;
    std::string currentProvenance;
    std::string provenance;
    std::string kind;
    std::string detectedHardwareVariant;
    std::string selectedHardwareVariant;
    std::array<Artifact, MAX_ARTIFACTS> artifacts{};
    std::size_t artifactCount = 0;
    std::uint32_t nextCheckSeconds = 0;
};

inline bool isTrack(const std::string &value) {
    return value == "main" || value == "staging";
}

inline bool isHardwareVariant(const std::string &value) {
    return value == "v1" || value == "v2";
}

inline bool isDecisionReason(const std::string &value) {
    return value == "update-available" || value == "already-current" ||
           value == "no-target" || value == "updates-disabled" ||
           value == "release-paused" || value == "rollout-denied" ||
           value == "incompatible-device";
}

inline bool isSemver(const std::string &value) {
    int dots = 0;
    bool digitInPart = false;
    for (const char character : value) {
        if (character == '.') {
            if (!digitInPart || ++dots > 2) return false;
            digitInPart = false;
        } else if (character == '+' || character == '-') {
            break;
        } else if (std::isdigit(static_cast<unsigned char>(character))) {
            digitInPart = true;
        } else {
            return false;
        }
    }
    return dots == 2 && digitInPart;
}

inline bool isSha256(const std::string &value) {
    return value.size() == 64 &&
           std::all_of(value.begin(), value.end(), [](const char character) {
               return std::isxdigit(static_cast<unsigned char>(character));
           });
}

inline bool isBuildIdentifier(const std::string &value) {
    return value.size() >= 7 && value.size() <= 64 &&
           std::all_of(value.begin(), value.end(), [](const char character) {
               return std::isxdigit(static_cast<unsigned char>(character));
           });
}

inline bool buildIdentifiersMatch(const std::string &left,
                                  const std::string &right) {
    if (!isBuildIdentifier(left) || !isBuildIdentifier(right)) return false;
    const auto sharedLength = std::min(left.size(), right.size());
    for (std::size_t index = 0; index < sharedLength; ++index) {
        if (std::tolower(static_cast<unsigned char>(left[index])) !=
            std::tolower(static_cast<unsigned char>(right[index]))) {
            return false;
        }
    }
    return true;
}

inline bool sha256Matches(const std::string &expected,
                          const std::uint8_t digest[32]) {
    if (!isSha256(expected)) return false;
    for (std::size_t index = 0; index < 32; ++index) {
        const auto high = static_cast<unsigned char>(expected[index * 2]);
        const auto low = static_cast<unsigned char>(expected[index * 2 + 1]);
        const int highNibble = std::isdigit(high) ? high - '0'
                                                  : std::tolower(high) - 'a' + 10;
        const int lowNibble = std::isdigit(low) ? low - '0'
                                                : std::tolower(low) - 'a' + 10;
        if (digest[index] !=
            static_cast<std::uint8_t>((highNibble << 4) | lowNibble)) {
            return false;
        }
    }
    return true;
}

inline bool isInstallableArtifactRole(const std::string &role) {
    return role == "application" || role == "filesystem";
}

inline bool isMetadataArtifactRole(const std::string &role) {
    return role == "bootloader" || role == "partitions" || role == "manifest";
}

inline bool isArtifactRole(const std::string &role) {
    return isInstallableArtifactRole(role) || isMetadataArtifactRole(role);
}

inline bool isHttpsArtifactUrl(const std::string &url,
                               const std::string &expectedBucket) {
    const std::string prefix = "https://";
    const std::string hostSuffix = ".supabase.co";
    const std::string storagePath =
        "/storage/v1/object/public/" + expectedBucket +
        "/releases/";
    if (url.find('@') != std::string::npos ||
        url.find('#') != std::string::npos ||
        url.find('?') != std::string::npos) {
        return false;
    }
#if defined(DTT_MIGRATION_LAB_INSECURE_HTTP) && defined(RAD_SERVER)
    // Lab builds may use only the exact resolver origin and production-shaped
    // bucket path. Release environments never define this flag.
    const std::string labPrefix = std::string(RAD_SERVER) + storagePath;
    if (url.rfind("http://", 0) == 0) {
        return url.rfind(labPrefix, 0) == 0 && url.size() > labPrefix.size();
    }
#endif
    if (url.rfind(prefix, 0) != 0) return false;
    const auto hostEnd = url.find('/', prefix.size());
    if (hostEnd == std::string::npos) return false;
    const std::string host = url.substr(prefix.size(), hostEnd - prefix.size());
    if (host.size() <= hostSuffix.size() ||
        host.compare(host.size() - hostSuffix.size(), hostSuffix.size(),
                     hostSuffix) != 0 ||
        host.find(':') != std::string::npos) {
        return false;
    }
    return url.compare(hostEnd, storagePath.size(), storagePath) == 0;
}

inline std::string serializeReport(const DeviceReport &report) {
    JsonDocument document;
    document["protocolVersion"] = report.protocolVersion;
    document["deviceType"] = report.deviceType;
    document["deviceId"] = report.deviceId;
    document["reportedTrack"] = report.reportedTrack;
    document["currentVersion"] = report.currentVersion;
    if (!report.currentBuild.empty())
        document["currentBuild"] = report.currentBuild;
    if (!report.firmwareHash.empty())
        document["firmwareHash"] = report.firmwareHash;
    document["provenanceCapability"] = report.provenanceCapability;
    if (!report.firmwareProvenance.empty())
        document["firmwareProvenance"] = report.firmwareProvenance;
    if (!report.chip.empty()) document["chip"] = report.chip;
    document["chipRevision"] = report.chipRevision;
    if (report.chipCores > 0) document["chipCores"] = report.chipCores;
    if (!report.hardwareRevision.empty())
        document["hardwareRevision"] = report.hardwareRevision;
    if (report.flashSizeBytes > 0)
        document["flashSizeBytes"] = report.flashSizeBytes;
    if (report.otaSlotSizeBytes > 0)
        document["otaSlotSizeBytes"] = report.otaSlotSizeBytes;
    document["psramSizeBytes"] = report.psramSizeBytes;
    if (!report.partitionLayout.empty())
        document["partitionLayout"] = report.partitionLayout;
    if (!report.partitionTableHash.empty())
        document["partitionTableHash"] = report.partitionTableHash;
    if (!report.bootloaderHash.empty())
        document["bootloaderHash"] = report.bootloaderHash;
    std::string output;
    serializeJson(document, output);
    return output;
}

inline bool readRequiredString(JsonVariantConst value, std::string &output) {
    if (!value.is<const char *>()) return false;
    output = value.as<const char *>();
    return !output.empty();
}

inline bool readNullableVersion(JsonVariantConst value, std::string &output) {
    if (value.isNull()) {
        output.clear();
        return true;
    }
    return readRequiredString(value, output) && isSemver(output);
}

inline bool parseDecision(const std::string &payload,
                          const std::string &expectedDeviceType,
                          Decision &decision, std::string &error) {
    JsonDocument document;
    const auto jsonError = deserializeJson(document, payload);
    if (jsonError) {
        error = "invalid JSON";
        return false;
    }

    Decision parsed;
    if ((!document["protocolVersion"].isNull() &&
         (!document["protocolVersion"].is<int>() ||
          document["protocolVersion"].as<int>() != PROTOCOL_VERSION)) ||
        (!document["shouldUpdate"].is<bool>() &&
         !document["updateAvailable"].is<bool>()) ||
        !document["trackChanged"].is<bool>() ||
        !document["nextCheckSeconds"].is<std::uint32_t>() ||
        !readRequiredString(document["reportedTrack"], parsed.reportedTrack) ||
        !readRequiredString(document["assignedTrack"], parsed.assignedTrack) ||
        !readRequiredString(document["currentVersion"], parsed.currentVersion) ||
        !readNullableVersion(document["targetVersion"], parsed.targetVersion) ||
        !readNullableVersion(document["nextHopVersion"], parsed.nextHopVersion) ||
        !isTrack(parsed.reportedTrack) || !isTrack(parsed.assignedTrack) ||
        !isSemver(parsed.currentVersion)) {
        error = "missing or invalid response fields";
        return false;
    }

    if (!document["protocolVersion"].isNull()) {
        parsed.protocolVersion = document["protocolVersion"].as<int>();
    }
    const bool hasCanonicalDecision = document["shouldUpdate"].is<bool>();
    const bool hasLegacyDecision = document["updateAvailable"].is<bool>();
    const bool canonicalResponse =
        !document["protocolVersion"].isNull() || hasCanonicalDecision ||
        !document["reason"].isNull();
    if (hasCanonicalDecision && hasLegacyDecision &&
        document["shouldUpdate"].as<bool>() !=
            document["updateAvailable"].as<bool>()) {
        error = "conflicting update decision fields";
        return false;
    }
    parsed.shouldUpdate = hasCanonicalDecision
                              ? document["shouldUpdate"].as<bool>()
                              : document["updateAvailable"].as<bool>();
    parsed.updateAvailable = parsed.shouldUpdate;
    if (hasCanonicalDecision) {
        if (!readRequiredString(document["reason"], parsed.reason) ||
            !isDecisionReason(parsed.reason) ||
            (parsed.shouldUpdate !=
             (parsed.reason == "update-available"))) {
            error = "invalid update decision reason";
            return false;
        }
    } else if (document["reason"].is<const char *>()) {
        parsed.reason = document["reason"].as<const char *>();
    }
    parsed.trackChanged = document["trackChanged"].as<bool>();
    parsed.nextCheckSeconds = document["nextCheckSeconds"].as<std::uint32_t>();
    if (!document["firmwareOrigin"].isNull() &&
        !readRequiredString(document["firmwareOrigin"], parsed.firmwareOrigin)) {
        error = "invalid firmware origin";
        return false;
    }
    if (!document["currentProvenance"].isNull() &&
        !readRequiredString(document["currentProvenance"], parsed.currentProvenance)) {
        error = "invalid current firmware provenance";
        return false;
    }
    if (!document["detectedHardwareVariant"].isNull() &&
        (!readRequiredString(document["detectedHardwareVariant"],
                             parsed.detectedHardwareVariant) ||
         !isHardwareVariant(parsed.detectedHardwareVariant))) {
        error = "invalid detected hardware variant";
        return false;
    }
    if (!document["selectedHardwareVariant"].isNull() &&
        (!readRequiredString(document["selectedHardwareVariant"],
                             parsed.selectedHardwareVariant) ||
         !isHardwareVariant(parsed.selectedHardwareVariant))) {
        error = "invalid selected hardware variant";
        return false;
    }
    if (!parsed.shouldUpdate) {
        if (!document["update"].isNull() || !parsed.nextHopVersion.empty()) {
            error = "no-update response contains update data";
            return false;
        }
        decision = parsed;
        return true;
    }

    JsonObjectConst update = document["update"].as<JsonObjectConst>();
    JsonArrayConst artifacts = update["artifacts"].as<JsonArrayConst>();
    if (update.isNull() || artifacts.isNull() || artifacts.size() == 0 ||
        artifacts.size() > MAX_ARTIFACTS ||
        !readRequiredString(update["releaseId"], parsed.releaseId) ||
        !readRequiredString(update["kind"], parsed.kind) ||
        (parsed.kind != "firmware" && parsed.kind != "migration") ||
        parsed.nextHopVersion.empty()) {
        error = "invalid update metadata";
        return false;
    }
    if (!update["buildSha"].isNull() &&
        (!readRequiredString(update["buildSha"], parsed.buildSha) ||
         !isBuildIdentifier(parsed.buildSha))) {
        error = "invalid update build identifier";
        return false;
    } else if (canonicalResponse && parsed.buildSha.empty()) {
        error = "canonical update response is missing build SHA";
        return false;
    }
    if (!update["provenance"].isNull() &&
        !readRequiredString(update["provenance"], parsed.provenance)) {
        error = "invalid update firmware provenance";
        return false;
    }

    const std::string expectedBucket = expectedDeviceType + "-firmware";
    std::array<bool, MAX_ARTIFACTS> seenOrders{};
    bool seenApplication = false;
    bool seenFilesystem = false;
    int applicationOrder = -1;
    int filesystemOrder = -1;
    for (JsonObjectConst item : artifacts) {
        Artifact artifact;
        if (!readRequiredString(item["role"], artifact.role) ||
            !readRequiredString(item["url"], artifact.url) ||
            !readRequiredString(item["sha256"], artifact.sha256) ||
            !item["sizeBytes"].is<std::uint32_t>() ||
            !item["installOrder"].is<int>() ||
            !isArtifactRole(artifact.role) || !isSha256(artifact.sha256) ||
            !isHttpsArtifactUrl(artifact.url, expectedBucket)) {
            error = "invalid artifact";
            return false;
        }
        artifact.sizeBytes = item["sizeBytes"].as<std::uint32_t>();
        artifact.installOrder = item["installOrder"].as<int>();
        if (artifact.sizeBytes == 0 || artifact.installOrder < 0 ||
            artifact.installOrder >= static_cast<int>(MAX_ARTIFACTS) ||
            seenOrders[artifact.installOrder]) {
            error = "invalid artifact size or order";
            return false;
        }
        if ((artifact.role == "application" && seenApplication) ||
            (artifact.role == "filesystem" && seenFilesystem)) {
            error = "duplicate installable artifact role";
            return false;
        }
        seenApplication = seenApplication || artifact.role == "application";
        seenFilesystem = seenFilesystem || artifact.role == "filesystem";
        if (artifact.role == "application") {
            applicationOrder = artifact.installOrder;
        } else if (artifact.role == "filesystem") {
            filesystemOrder = artifact.installOrder;
        }
        seenOrders[artifact.installOrder] = true;
        parsed.artifacts[parsed.artifactCount++] = artifact;
    }
    if (!seenApplication) {
        error = "release has no application artifact";
        return false;
    }
    if (parsed.kind == "migration" && seenFilesystem) {
        error = "migration release cannot replace the filesystem";
        return false;
    }
    if (seenFilesystem && filesystemOrder >= applicationOrder) {
        error = "filesystem must be installed before application";
        return false;
    }

    std::sort(parsed.artifacts.begin(),
              parsed.artifacts.begin() + parsed.artifactCount,
              [](const Artifact &left, const Artifact &right) {
                  return left.installOrder < right.installOrder;
              });
    decision = parsed;
    return true;
}

inline bool decisionMatchesReport(const DeviceReport &report,
                                  const Decision &decision) {
    if (decision.reportedTrack != report.reportedTrack ||
        decision.currentVersion != report.currentVersion ||
        decision.trackChanged !=
            (decision.reportedTrack != decision.assignedTrack)) {
        return false;
    }
    if (!decision.shouldUpdate) return true;
    if (decision.assignedTrack == report.reportedTrack &&
        buildIdentifiersMatch(report.currentBuild, decision.buildSha)) {
        return false;
    }

    constexpr std::uint32_t SIXTEEN_MIB = 16U * 1024U * 1024U;
    const bool legacyLayout = report.partitionLayout == "legacy-v1";
    const bool v2Layout = report.partitionLayout == "dtt-ota-16mb-v1";
    if (decision.kind == "migration") {
        return legacyLayout && report.flashSizeBytes >= SIXTEEN_MIB &&
               decision.selectedHardwareVariant == "v2";
    }
    if (v2Layout) {
        return report.flashSizeBytes >= SIXTEEN_MIB &&
               decision.selectedHardwareVariant == "v2";
    }
    if (legacyLayout && decision.selectedHardwareVariant == "v2") {
        return false;
    }
    return decision.kind == "firmware";
}

}  // namespace firmware
