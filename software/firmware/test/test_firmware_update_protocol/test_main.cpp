#include <unity.h>

#include "DttMigrationPlan.h"
#include "FirmwareUpdateFlow.h"
#include "FirmwareUpdateProtocol.h"

namespace {

const char *VALID_RESPONSE = R"json({
  "protocolVersion": 1,
  "shouldUpdate": true,
  "updateAvailable": true,
  "reason": "update-available",
  "reportedTrack": "main",
  "assignedTrack": "staging",
  "detectedHardwareVariant": "v2",
  "selectedHardwareVariant": "v2",
  "trackChanged": true,
  "firmwareOrigin": "official",
  "currentProvenance": "current.jws.token",
  "currentVersion": "2.0.66",
  "targetVersion": "2.0.67",
  "nextHopVersion": "2.0.67",
  "update": {
    "provenance": "target.jws.token",
    "releaseId": "00000000-0000-4000-8000-000000000001",
    "buildSha": "0123456789abcdef",
    "kind": "firmware",
    "publishedAt": "2026-07-16T00:00:00.000Z",
    "artifacts": [
      {
        "role": "application",
        "url": "https://example.supabase.co/storage/v1/object/public/dtt-firmware/releases/2.0.67/0123456789abcdef/firmware.bin",
        "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "sizeBytes": 1024,
        "installOrder": 1
      }
    ]
  },
  "nextCheckSeconds": 60
})json";

const char *NO_UPDATE_RESPONSE = R"json({
  "protocolVersion": 1,
  "shouldUpdate": false,
  "updateAvailable": false,
  "reason": "already-current",
  "reportedTrack": "main",
  "assignedTrack": "main",
  "trackChanged": false,
  "currentVersion": "2.0.67",
  "targetVersion": null,
  "nextHopVersion": null,
  "update": null,
  "nextCheckSeconds": 3600
})json";

const char *MULTI_ARTIFACT_RESPONSE = R"json({
  "protocolVersion": 1,
  "shouldUpdate": true,
  "updateAvailable": true,
  "reason": "update-available",
  "reportedTrack": "main",
  "assignedTrack": "main",
  "trackChanged": false,
  "currentVersion": "2.0.66",
  "targetVersion": "2.0.67",
  "nextHopVersion": "2.0.67",
  "update": {
    "releaseId": "00000000-0000-4000-8000-000000000001",
    "buildSha": "fedcba9876543210",
    "kind": "firmware",
    "artifacts": [
      {
        "role": "filesystem",
        "url": "https://example.supabase.co/storage/v1/object/public/dtt-firmware/releases/2.0.67/0123456789abcdef/filesystem.bin",
        "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "sizeBytes": 2048,
        "installOrder": 1
      },
      {
        "role": "partitions",
        "url": "https://example.supabase.co/storage/v1/object/public/dtt-firmware/releases/2.0.67/0123456789abcdef/partitions.bin",
        "sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "sizeBytes": 3072,
        "installOrder": 0
      },
      {
        "role": "application",
        "url": "https://example.supabase.co/storage/v1/object/public/dtt-firmware/releases/2.0.67/0123456789abcdef/firmware.bin",
        "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "sizeBytes": 1024,
        "installOrder": 2
      },
      {
        "role": "bootloader",
        "url": "https://example.supabase.co/storage/v1/object/public/dtt-firmware/releases/2.0.67/0123456789abcdef/bootloader.bin",
        "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        "sizeBytes": 4096,
        "installOrder": 3
      }
    ]
  },
  "nextCheckSeconds": 60
})json";

void test_serializes_required_and_hardware_fields() {
    firmware::DeviceReport report{
        .deviceType = "dtt",
        .deviceId = "trainer-test-id",
        .reportedTrack = "main",
        .currentVersion = "2.0.66",
        .currentBuild = "0123456789abcdef",
        .firmwareHash =
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        .provenanceCapability = 1,
        .firmwareProvenance = "current.jws.token",
        .chip = "esp32",
        .chipRevision = 0,
        .chipCores = 2,
        .flashSizeBytes = 4194304,
        .otaSlotSizeBytes = 1310720,
        .psramSizeBytes = 0,
        .partitionLayout = "legacy-v1",
        .partitionTableHash =
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        .bootloaderHash =
            "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    };
    JsonDocument parsed;
    deserializeJson(parsed, firmware::serializeReport(report));
    TEST_ASSERT_EQUAL_STRING("dtt", parsed["deviceType"]);
    TEST_ASSERT_EQUAL_INT(1, parsed["protocolVersion"]);
    TEST_ASSERT_EQUAL_STRING("main", parsed["reportedTrack"]);
    TEST_ASSERT_EQUAL_INT(1, parsed["provenanceCapability"]);
    TEST_ASSERT_EQUAL_STRING("current.jws.token",
                             parsed["firmwareProvenance"]);
    TEST_ASSERT_EQUAL_UINT32(4194304, parsed["flashSizeBytes"]);
    TEST_ASSERT_EQUAL_UINT32(1310720, parsed["otaSlotSizeBytes"]);
    TEST_ASSERT_EQUAL_UINT32(0, parsed["chipRevision"]);
    TEST_ASSERT_EQUAL_UINT32(2, parsed["chipCores"]);
    TEST_ASSERT_EQUAL_UINT32(0, parsed["psramSizeBytes"]);
    TEST_ASSERT_EQUAL_STRING("legacy-v1", parsed["partitionLayout"]);
    TEST_ASSERT_EQUAL_STRING(
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        parsed["partitionTableHash"]);
    TEST_ASSERT_EQUAL_STRING(
        "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        parsed["bootloaderHash"]);

    report.chipCores = 0;
    JsonDocument withoutCoreCount;
    deserializeJson(withoutCoreCount, firmware::serializeReport(report));
    TEST_ASSERT_TRUE(withoutCoreCount["chipCores"].isNull());
    TEST_ASSERT_EQUAL_UINT32(0, withoutCoreCount["chipRevision"]);
    TEST_ASSERT_EQUAL_UINT32(0, withoutCoreCount["psramSizeBytes"]);
}

void test_http_transfer_policy_is_fail_closed() {
    TEST_ASSERT_TRUE(firmware::isRedirectStatus(301));
    TEST_ASSERT_TRUE(firmware::isRedirectStatus(308));
    TEST_ASSERT_FALSE(firmware::isRedirectStatus(200));
    TEST_ASSERT_FALSE(firmware::isResponseLengthAllowed(0, 32768));
    TEST_ASSERT_TRUE(firmware::isResponseLengthAllowed(-1, 32768));
    TEST_ASSERT_TRUE(firmware::isResponseLengthAllowed(32768, 32768));
    TEST_ASSERT_FALSE(firmware::isResponseLengthAllowed(32769, 32768));
    TEST_ASSERT_TRUE(firmware::knownContentLengthMatches(-1, 1024));
    TEST_ASSERT_TRUE(firmware::knownContentLengthMatches(1024, 1024));
    TEST_ASSERT_FALSE(firmware::knownContentLengthMatches(1023, 1024));
    TEST_ASSERT_FALSE(firmware::transferCompleted(1023, 1023, 1024));
    TEST_ASSERT_FALSE(firmware::transferCompleted(1024, 1023, 1024));
    TEST_ASSERT_FALSE(firmware::transferCompleted(-1, 0, 1024));
}

void test_chunked_transfer_requires_exact_final_byte_count() {
    TEST_ASSERT_TRUE(firmware::knownContentLengthMatches(-1, 1024));
    TEST_ASSERT_TRUE(firmware::transferCompleted(1024, 1024, 1024));
    TEST_ASSERT_FALSE(firmware::transferCompleted(1023, 1023, 1024));
    TEST_ASSERT_FALSE(firmware::transferCompleted(1025, 1024, 1024));
}

void test_parses_cross_track_update_and_orders_artifacts() {
    firmware::Decision decision;
    std::string error;
    TEST_ASSERT_TRUE(
        firmware::parseDecision(VALID_RESPONSE, "dtt", decision, error));
    TEST_ASSERT_TRUE(decision.updateAvailable);
    TEST_ASSERT_TRUE(decision.shouldUpdate);
    TEST_ASSERT_EQUAL_STRING("update-available", decision.reason.c_str());
    TEST_ASSERT_EQUAL_STRING("0123456789abcdef", decision.buildSha.c_str());
    TEST_ASSERT_EQUAL_STRING("staging", decision.assignedTrack.c_str());
    TEST_ASSERT_EQUAL_STRING("official", decision.firmwareOrigin.c_str());
    TEST_ASSERT_EQUAL_STRING("current.jws.token",
                             decision.currentProvenance.c_str());
    TEST_ASSERT_EQUAL_STRING("target.jws.token",
                             decision.provenance.c_str());
    TEST_ASSERT_TRUE(decision.trackChanged);
    TEST_ASSERT_EQUAL_STRING("2.0.67", decision.nextHopVersion.c_str());
    TEST_ASSERT_EQUAL_UINT32(1, decision.artifactCount);
    TEST_ASSERT_EQUAL_STRING("application", decision.artifacts[0].role.c_str());
}

void test_parses_no_update_response() {
    firmware::Decision decision;
    std::string error;
    TEST_ASSERT_TRUE(firmware::parseDecision(NO_UPDATE_RESPONSE, "dtt",
                                             decision, error));
    TEST_ASSERT_FALSE(decision.updateAvailable);
    TEST_ASSERT_FALSE(decision.shouldUpdate);
    TEST_ASSERT_FALSE(decision.trackChanged);
    TEST_ASSERT_EQUAL_UINT32(0, decision.artifactCount);
    TEST_ASSERT_TRUE(decision.targetVersion.empty());
    TEST_ASSERT_TRUE(decision.nextHopVersion.empty());
}

void test_update_flow_treats_already_current_as_complete() {
    TEST_ASSERT_EQUAL_INT(
        static_cast<int>(firmware::UpdateAction::resolve),
        static_cast<int>(firmware::selectUpdateAction(false, false)));
    TEST_ASSERT_EQUAL_INT(
        static_cast<int>(firmware::UpdateAction::complete),
        static_cast<int>(firmware::selectUpdateAction(true, false)));
    TEST_ASSERT_EQUAL_INT(
        static_cast<int>(firmware::UpdateAction::install),
        static_cast<int>(firmware::selectUpdateAction(true, true)));
    TEST_ASSERT_EQUAL_INT(
        static_cast<int>(firmware::UpdateAction::reject),
        static_cast<int>(firmware::selectUpdateAction(true, false, true)));
}

void test_accepts_legacy_boolean_and_rejects_conflicting_decisions() {
    std::string legacy = VALID_RESPONSE;
    const std::string canonical = "  \"shouldUpdate\": true,\n";
    legacy.erase(legacy.find(canonical), canonical.size());
    firmware::Decision decision;
    std::string error;
    TEST_ASSERT_TRUE(
        firmware::parseDecision(legacy, "dtt", decision, error));
    TEST_ASSERT_TRUE(decision.shouldUpdate);

    std::string conflicting = VALID_RESPONSE;
    const auto shouldUpdate = conflicting.find("\"shouldUpdate\": true");
    conflicting.replace(shouldUpdate, std::string("\"shouldUpdate\": true").size(),
                        "\"shouldUpdate\": false");
    TEST_ASSERT_FALSE(
        firmware::parseDecision(conflicting, "dtt", decision, error));

    std::string incoherentReason = VALID_RESPONSE;
    const auto reason = incoherentReason.find("update-available");
    incoherentReason.replace(reason, std::string("update-available").size(),
                             "already-current");
    TEST_ASSERT_FALSE(
        firmware::parseDecision(incoherentReason, "dtt", decision, error));
}

void test_requires_build_sha_for_canonical_updates_only() {
    std::string missingBuild = VALID_RESPONSE;
    const std::string buildLine =
        "    \"buildSha\": \"0123456789abcdef\",\n";
    missingBuild.erase(missingBuild.find(buildLine), buildLine.size());

    firmware::Decision decision;
    std::string error;
    TEST_ASSERT_FALSE(
        firmware::parseDecision(missingBuild, "dtt", decision, error));
    TEST_ASSERT_EQUAL_STRING(
        "canonical update response is missing build SHA", error.c_str());

    std::string legacy = missingBuild;
    const std::string protocolLine = "  \"protocolVersion\": 1,\n";
    const std::string canonicalLine = "  \"shouldUpdate\": true,\n";
    const std::string reasonLine =
        "  \"reason\": \"update-available\",\n";
    legacy.erase(legacy.find(protocolLine), protocolLine.size());
    legacy.erase(legacy.find(canonicalLine), canonicalLine.size());
    legacy.erase(legacy.find(reasonLine), reasonLine.size());
    TEST_ASSERT_TRUE(firmware::parseDecision(legacy, "dtt", decision, error));
    TEST_ASSERT_TRUE(decision.shouldUpdate);
    TEST_ASSERT_TRUE(decision.buildSha.empty());

    std::string invalidBuild = VALID_RESPONSE;
    const auto buildValue = invalidBuild.find("0123456789abcdef");
    invalidBuild.replace(buildValue, std::string("0123456789abcdef").size(),
                         "invalid");
    TEST_ASSERT_FALSE(
        firmware::parseDecision(invalidBuild, "dtt", decision, error));
    TEST_ASSERT_EQUAL_STRING("invalid update build identifier", error.c_str());
}

void test_rejects_repeat_build_on_same_track() {
    firmware::DeviceReport report{
        .deviceType = "dtt",
        .deviceId = "trainer-test-id",
        .reportedTrack = "main",
        .currentVersion = "2.0.66",
        .currentBuild = "0123456",
    };
    firmware::Decision decision;
    std::string error;
    TEST_ASSERT_TRUE(
        firmware::parseDecision(VALID_RESPONSE, "dtt", decision, error));
    decision.assignedTrack = "main";
    decision.trackChanged = false;
    TEST_ASSERT_FALSE(firmware::decisionMatchesReport(report, decision));

    decision.buildSha = "fedcba9";
    TEST_ASSERT_TRUE(firmware::decisionMatchesReport(report, decision));
    decision.assignedTrack = "staging";
    decision.trackChanged = true;
    decision.buildSha = "0123456789abcdef";
    TEST_ASSERT_TRUE(firmware::decisionMatchesReport(report, decision));
}

void test_orders_application_filesystem_and_metadata_artifacts() {
    firmware::Decision decision;
    std::string error;
    TEST_ASSERT_TRUE(firmware::parseDecision(MULTI_ARTIFACT_RESPONSE, "dtt",
                                             decision, error));
    TEST_ASSERT_EQUAL_UINT32(4, decision.artifactCount);
    TEST_ASSERT_EQUAL_STRING("partitions", decision.artifacts[0].role.c_str());
    TEST_ASSERT_EQUAL_STRING("filesystem", decision.artifacts[1].role.c_str());
    TEST_ASSERT_EQUAL_STRING("application", decision.artifacts[2].role.c_str());
    TEST_ASSERT_EQUAL_STRING("bootloader", decision.artifacts[3].role.c_str());
    TEST_ASSERT_TRUE(
        firmware::isInstallableArtifactRole(decision.artifacts[1].role));
    TEST_ASSERT_TRUE(
        firmware::isInstallableArtifactRole(decision.artifacts[2].role));
    TEST_ASSERT_TRUE(
        firmware::isMetadataArtifactRole(decision.artifacts[0].role));
    TEST_ASSERT_TRUE(
        firmware::isMetadataArtifactRole(decision.artifacts[3].role));
    TEST_ASSERT_TRUE(firmware::isMetadataArtifactRole("manifest"));
}

void test_rejects_wrong_bucket_and_non_https_urls() {
    std::string payload = VALID_RESPONSE;
    const auto bucket = payload.find("dtt-firmware");
    payload.replace(bucket, std::string("dtt-firmware").size(), "lkbx-firmware");
    firmware::Decision decision;
    std::string error;
    TEST_ASSERT_FALSE(
        firmware::parseDecision(payload, "dtt", decision, error));

    payload = VALID_RESPONSE;
    const auto scheme = payload.find("https://");
    payload.replace(scheme, std::string("https://").size(), "http://");
    TEST_ASSERT_FALSE(
        firmware::parseDecision(payload, "dtt", decision, error));

    payload = VALID_RESPONSE;
    const auto trustedHost = payload.find("example.supabase.co");
    payload.replace(trustedHost, std::string("example.supabase.co").size(),
                    "evil.example");
    TEST_ASSERT_FALSE(
        firmware::parseDecision(payload, "dtt", decision, error));

    payload = VALID_RESPONSE;
    const auto filename = payload.find("firmware.bin");
    payload.insert(filename + std::string("firmware.bin").size(),
                   "?redirect=https://evil.example/payload.bin");
    TEST_ASSERT_FALSE(
        firmware::parseDecision(payload, "dtt", decision, error));
}

void test_rejects_invalid_artifact_data_and_malformed_responses() {
    std::string payload = VALID_RESPONSE;
    const auto hash = payload.find(std::string(64, 'a'));
    payload.replace(hash, 64, "bad");
    firmware::Decision decision;
    std::string error;
    TEST_ASSERT_FALSE(
        firmware::parseDecision(payload, "dtt", decision, error));

    payload = VALID_RESPONSE;
    const auto role = payload.find("\"role\": \"application\"");
    payload.replace(role, std::string("\"role\": \"application\"").size(),
                    "\"role\": \"unknown\"");
    TEST_ASSERT_FALSE(
        firmware::parseDecision(payload, "dtt", decision, error));

    payload = MULTI_ARTIFACT_RESPONSE;
    const auto duplicateOrder = payload.find("\"installOrder\": 2");
    payload.replace(duplicateOrder, std::string("\"installOrder\": 2").size(),
                    "\"installOrder\": 1");
    TEST_ASSERT_FALSE(
        firmware::parseDecision(payload, "dtt", decision, error));

    payload = MULTI_ARTIFACT_RESPONSE;
    const auto filesystemOrder = payload.find("\"installOrder\": 1");
    payload.replace(filesystemOrder,
                    std::string("\"installOrder\": 1").size(),
                    "\"installOrder\": 4");
    TEST_ASSERT_FALSE(
        firmware::parseDecision(payload, "dtt", decision, error));

    payload = MULTI_ARTIFACT_RESPONSE;
    const auto filesystemRole = payload.find("\"role\": \"filesystem\"");
    payload.replace(filesystemRole,
                    std::string("\"role\": \"filesystem\"").size(),
                    "\"role\": \"application\"");
    TEST_ASSERT_FALSE(
        firmware::parseDecision(payload, "dtt", decision, error));

    payload = VALID_RESPONSE;
    const auto applicationRole = payload.find("\"role\": \"application\"");
    payload.replace(applicationRole,
                    std::string("\"role\": \"application\"").size(),
                    "\"role\": \"filesystem\"");
    TEST_ASSERT_FALSE(
        firmware::parseDecision(payload, "dtt", decision, error));

    TEST_ASSERT_FALSE(firmware::parseDecision("{", "dtt", decision, error));
    TEST_ASSERT_FALSE(firmware::parseDecision("{}", "dtt", decision, error));
}

void test_accepts_uppercase_sha_and_gates_migration() {
    std::uint8_t digest[32];
    std::fill(std::begin(digest), std::end(digest), 0xAA);
    TEST_ASSERT_TRUE(firmware::sha256Matches(std::string(64, 'A'), digest));
    TEST_ASSERT_TRUE(firmware::sha256Matches(std::string(64, 'a'), digest));
    TEST_ASSERT_FALSE(firmware::sha256Matches(std::string(64, 'B'), digest));

    std::string uppercasePayload = VALID_RESPONSE;
    const auto hash = uppercasePayload.find(std::string(64, 'a'));
    uppercasePayload.replace(hash, 64, std::string(64, 'A'));
    firmware::Decision decision;
    std::string error;
    TEST_ASSERT_TRUE(firmware::parseDecision(uppercasePayload, "dtt", decision,
                                             error));

    std::string payload = VALID_RESPONSE;
    const auto kind = payload.find("\"kind\": \"firmware\"");
    payload.replace(kind, std::string("\"kind\": \"firmware\"").size(),
                    "\"kind\": \"migration\"");
    TEST_ASSERT_TRUE(firmware::parseDecision(payload, "dtt", decision, error));

    firmware::DeviceReport report{
        .deviceType = "dtt",
        .deviceId = "trainer-test-id",
        .reportedTrack = "main",
        .currentVersion = "2.0.66",
        .currentBuild = "fedcba9876543210",
        .flashSizeBytes = 16U * 1024U * 1024U,
        .partitionLayout = "legacy-v1",
    };
    decision.reportedTrack = "main";
    decision.assignedTrack = "main";
    decision.trackChanged = false;
    TEST_ASSERT_TRUE(firmware::decisionMatchesReport(report, decision));

    report.flashSizeBytes = 4U * 1024U * 1024U;
    TEST_ASSERT_FALSE(firmware::decisionMatchesReport(report, decision));
    report.flashSizeBytes = 16U * 1024U * 1024U;
    report.partitionLayout = "unknown";
    TEST_ASSERT_FALSE(firmware::decisionMatchesReport(report, decision));
}

void test_rejects_direct_v2_firmware_on_legacy_layout() {
    firmware::Decision decision;
    std::string error;
    TEST_ASSERT_TRUE(
        firmware::parseDecision(VALID_RESPONSE, "dtt", decision, error));
    firmware::DeviceReport report{
        .deviceType = "dtt",
        .deviceId = "trainer-test-id",
        .reportedTrack = "main",
        .currentVersion = "2.0.66",
        .currentBuild = "fedcba9876543210",
        .flashSizeBytes = 16U * 1024U * 1024U,
        .partitionLayout = "legacy-v1",
    };
    decision.reportedTrack = "main";
    decision.assignedTrack = "main";
    decision.trackChanged = false;
    TEST_ASSERT_FALSE(firmware::decisionMatchesReport(report, decision));

    report.partitionLayout = "dtt-ota-16mb-v1";
    TEST_ASSERT_TRUE(firmware::decisionMatchesReport(report, decision));
}

void test_partition_migration_plan_fails_closed() {
    using firmware::dtt::BootloaderState;
    using firmware::dtt::MigrationAction;
    using firmware::dtt::SIXTEEN_MIB;
    TEST_ASSERT_EQUAL_INT(static_cast<int>(MigrationAction::relocateToApp0),
                          static_cast<int>(firmware::dtt::nextMigrationAction(
                              true, false, false, SIXTEEN_MIB, false,
                              BootloaderState::legacy4MiB)));
    TEST_ASSERT_EQUAL_INT(static_cast<int>(MigrationAction::writeBootloader),
                          static_cast<int>(firmware::dtt::nextMigrationAction(
                              true, false, true, SIXTEEN_MIB, false,
                              BootloaderState::legacy4MiB)));
    TEST_ASSERT_EQUAL_INT(
        static_cast<int>(MigrationAction::writePartitionTable),
        static_cast<int>(firmware::dtt::nextMigrationAction(
            true, false, true, SIXTEEN_MIB, false,
            BootloaderState::migrated16MiB)));
    TEST_ASSERT_EQUAL_INT(
        static_cast<int>(MigrationAction::resolveFinalFirmware),
        static_cast<int>(firmware::dtt::nextMigrationAction(
            false, true, true, SIXTEEN_MIB, false,
            BootloaderState::migrated16MiB)));
    TEST_ASSERT_EQUAL_INT(static_cast<int>(MigrationAction::failClosed),
                          static_cast<int>(firmware::dtt::nextMigrationAction(
                              false, true, true, SIXTEEN_MIB, false,
                              BootloaderState::legacy4MiB)));
    TEST_ASSERT_EQUAL_INT(static_cast<int>(MigrationAction::failClosed),
                          static_cast<int>(firmware::dtt::nextMigrationAction(
                              true, false, true, firmware::dtt::FOUR_MIB, false,
                              BootloaderState::legacy4MiB)));
    TEST_ASSERT_EQUAL_INT(static_cast<int>(MigrationAction::failClosed),
                          static_cast<int>(firmware::dtt::nextMigrationAction(
                              true, false, true, SIXTEEN_MIB, true,
                              BootloaderState::legacy4MiB)));
    TEST_ASSERT_EQUAL_INT(static_cast<int>(MigrationAction::failClosed),
                          static_cast<int>(firmware::dtt::nextMigrationAction(
                              true, false, true, SIXTEEN_MIB, false,
                              BootloaderState::unapproved)));
}

void test_migration_prepares_before_giving_up_previous_firmware() {
    using firmware::dtt::MigrationAction;
    using firmware::dtt::PreparationStep;
    const auto step = [](const MigrationAction action, const bool legacy,
                         const bool identity, const bool staged) {
        return static_cast<int>(firmware::dtt::nextPreparationStep(
            action, legacy, identity, staged));
    };
    const int refuse = static_cast<int>(PreparationStep::refuse);
    const int stage = static_cast<int>(PreparationStep::stageFinalFirmware);
    const int proceed = static_cast<int>(PreparationStep::proceed);

    // A device the bridge cannot migrate is handed back, whatever else holds.
    TEST_ASSERT_EQUAL_INT(
        refuse, step(MigrationAction::failClosed, true, true, true));
    TEST_ASSERT_EQUAL_INT(
        refuse, step(MigrationAction::failClosed, false, true, true));

    // Under the legacy table every destructive step waits for a usable
    // identity and a verified copy of the final firmware.
    for (const auto action :
         {MigrationAction::relocateToApp0, MigrationAction::writeBootloader,
          MigrationAction::writePartitionTable}) {
        TEST_ASSERT_EQUAL_INT(refuse, step(action, true, false, false));
        TEST_ASSERT_EQUAL_INT(refuse, step(action, true, false, true));
        TEST_ASSERT_EQUAL_INT(stage, step(action, true, true, false));
        TEST_ASSERT_EQUAL_INT(proceed, step(action, true, true, true));
    }

    // Once the 16 MiB table is installed only the final install is left.
    TEST_ASSERT_EQUAL_INT(
        proceed,
        step(MigrationAction::resolveFinalFirmware, false, false, false));
}

void test_staged_final_firmware_must_fit_below_bootloader_staging() {
    constexpr std::uint32_t limit = 0xF00000 - 0x790000;
    TEST_ASSERT_FALSE(firmware::dtt::stagedFinalFirmwareFits(0, limit));
    TEST_ASSERT_TRUE(firmware::dtt::stagedFinalFirmwareFits(1, limit));
    TEST_ASSERT_TRUE(firmware::dtt::stagedFinalFirmwareFits(limit, limit));
    TEST_ASSERT_FALSE(firmware::dtt::stagedFinalFirmwareFits(limit + 1, limit));
    TEST_ASSERT_FALSE(
        firmware::dtt::stagedFinalFirmwareFits(0xFFFFFFFF, limit));
}

void test_migration_accepts_deployed_trainer_id_formats() {
    TEST_ASSERT_TRUE(firmware::dtt::validTrainerId(
        "B1E57A229D22417E88B476977AF7226A"));
    TEST_ASSERT_TRUE(firmware::dtt::validTrainerId(
        "28C43291-9AE1-412C-B9F1-7DCFC9165AA7"));
    TEST_ASSERT_TRUE(firmware::dtt::validTrainerId(
        "28c43291-9ae1-412c-b9f1-7dcfc9165aa7"));
    TEST_ASSERT_FALSE(firmware::dtt::validTrainerId(
        "28C432919AE1412CB9F17DCFC9165AA"));
    TEST_ASSERT_FALSE(firmware::dtt::validTrainerId(
        "28C43291_9AE1-412C-B9F1-7DCFC9165AA7"));
    TEST_ASSERT_FALSE(firmware::dtt::validTrainerId(
        "28C43291-9AE1-412C-B9F1-7DCFC9165AAG"));
}

}  // namespace

int main(int, char **) {
    UNITY_BEGIN();
    RUN_TEST(test_serializes_required_and_hardware_fields);
    RUN_TEST(test_http_transfer_policy_is_fail_closed);
    RUN_TEST(test_chunked_transfer_requires_exact_final_byte_count);
    RUN_TEST(test_parses_cross_track_update_and_orders_artifacts);
    RUN_TEST(test_parses_no_update_response);
    RUN_TEST(test_update_flow_treats_already_current_as_complete);
    RUN_TEST(test_accepts_legacy_boolean_and_rejects_conflicting_decisions);
    RUN_TEST(test_requires_build_sha_for_canonical_updates_only);
    RUN_TEST(test_rejects_repeat_build_on_same_track);
    RUN_TEST(test_orders_application_filesystem_and_metadata_artifacts);
    RUN_TEST(test_rejects_wrong_bucket_and_non_https_urls);
    RUN_TEST(test_rejects_invalid_artifact_data_and_malformed_responses);
    RUN_TEST(test_accepts_uppercase_sha_and_gates_migration);
    RUN_TEST(test_rejects_direct_v2_firmware_on_legacy_layout);
    RUN_TEST(test_partition_migration_plan_fails_closed);
    RUN_TEST(test_migration_prepares_before_giving_up_previous_firmware);
    RUN_TEST(test_staged_final_firmware_must_fit_below_bootloader_staging);
    RUN_TEST(test_migration_accepts_deployed_trainer_id_formats);
    return UNITY_END();
}
