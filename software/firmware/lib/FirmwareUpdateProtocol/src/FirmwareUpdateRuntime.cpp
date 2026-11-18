#include "FirmwareUpdateRuntime.h"

#if defined(ARDUINO_ARCH_ESP32)

#include <HTTPClient.h>
#include <NetworkRequestLock.h>
#include <Update.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>
#include <esp_partition.h>
#include <esp_sntp.h>
#include <esp_spi_flash.h>
#include <mbedtls/sha256.h>
#include <time.h>

#include "CertificateDateClient.h"

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <new>
#include <string>

namespace {

constexpr std::size_t MAX_RESOLVER_RESPONSE_BYTES = 32768;
constexpr time_t MINIMUM_VALID_TIME = 1704067200;  // 2024-01-01 UTC
constexpr unsigned long NTP_TIMEOUT_MS = 10000;

extern const std::uint8_t x509CrtBundleStart[]
    asm("_binary_x509_crt_bundle_start");

bool utcSynchronized = false;

bool waitForValidUtc(String &error) {
    if (utcSynchronized && time(nullptr) >= MINIMUM_VALID_TIME) return true;
    sntp_set_sync_status(SNTP_SYNC_STATUS_RESET);
    configTime(0, 0, "time.cloudflare.com", "pool.ntp.org");
    const unsigned long startedAt = millis();
    while (millis() - startedAt < NTP_TIMEOUT_MS) {
        if (sntp_get_sync_status() == SNTP_SYNC_STATUS_COMPLETED &&
            time(nullptr) >= MINIMUM_VALID_TIME) {
            utcSynchronized = true;
            return true;
        }
        delay(250);
    }
    error = "UTC synchronization timed out";
    return false;
}

bool beginFirmwareRequest(HTTPClient &http,
                          firmware::CertificateDateClient &secureClient,
                          WiFiClient &plainClient, const String &url,
                          const std::uint16_t timeoutMs, String &error) {
#if defined(DTT_MIGRATION_LAB_INSECURE_HTTP) && defined(RAD_SERVER)
    const String labOrigin = RAD_SERVER;
    if (url.startsWith("http://")) {
        if (!labOrigin.startsWith("http://") ||
            !url.startsWith(labOrigin + "/")) {
            error = "lab firmware request escaped configured origin";
            return false;
        }
        http.setConnectTimeout(timeoutMs);
        http.setTimeout(timeoutMs);
        http.setReuse(false);
        http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
        if (!http.begin(plainClient, url)) {
            error = "failed to initialize lab HTTP request";
            return false;
        }
        http.addHeader("Accept-Encoding", "identity");
        return true;
    }
#endif
    if (!url.startsWith("https://")) {
        error = "firmware request requires HTTPS";
        return false;
    }
    if (!waitForValidUtc(error)) return false;
    secureClient.setCACertBundle(x509CrtBundleStart);
    secureClient.setHandshakeTimeout((timeoutMs + 999) / 1000);
    http.setConnectTimeout(timeoutMs);
    http.setTimeout(timeoutMs);
    http.setReuse(false);
    http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
    if (!http.begin(secureClient, url)) {
        error = "failed to initialize verified HTTPS request";
        return false;
    }
    http.addHeader("Accept-Encoding", "identity");
    return true;
}

class BoundedStringSink final : public Stream {
   public:
    explicit BoundedStringSink(const std::size_t limit) : limit_(limit) {}

    bool reserve(const std::size_t size) {
        return value_.reserve(std::min(size, limit_));
    }
    std::size_t write(const std::uint8_t value) override {
        return write(&value, 1);
    }
    std::size_t write(const std::uint8_t *buffer,
                      const std::size_t size) override {
        if (value_.length() > limit_ || size > limit_ - value_.length()) {
            overflowed_ = true;
            setWriteError();
            return 0;
        }
        if (!value_.concat(reinterpret_cast<const char *>(buffer), size)) {
            allocationFailed_ = true;
            setWriteError();
            return 0;
        }
        return size;
    }
    int available() override { return 0; }
    int read() override { return -1; }
    int peek() override { return -1; }
    bool overflowed() const { return overflowed_; }
    bool allocationFailed() const { return allocationFailed_; }
    const String &value() const { return value_; }

   private:
    std::size_t limit_;
    String value_;
    bool overflowed_ = false;
    bool allocationFailed_ = false;
};

class UpdateHashSink final : public Stream {
   public:
    UpdateHashSink(const std::uint32_t expectedBytes, String &error)
        : expectedBytes_(expectedBytes), error_(error) {
        mbedtls_sha256_init(&sha_);
        initialized_ = mbedtls_sha256_starts_ret(&sha_, 0) == 0;
        if (!initialized_) error_ = "failed to initialize artifact SHA-256";
    }
    ~UpdateHashSink() override { mbedtls_sha256_free(&sha_); }
    std::size_t write(const std::uint8_t value) override {
        return write(&value, 1);
    }
    std::size_t write(const std::uint8_t *buffer,
                      const std::size_t size) override {
        if (!initialized_ || failed_) return 0;
        if (size > expectedBytes_ - totalBytes_) {
            fail("artifact exceeds declared size");
            return 0;
        }
        if (Update.write(const_cast<std::uint8_t *>(buffer), size) != size) {
            fail("artifact write failed");
            return 0;
        }
        if (mbedtls_sha256_update_ret(&sha_, buffer, size) != 0) {
            fail("artifact SHA-256 update failed");
            return 0;
        }
        totalBytes_ += size;
        return size;
    }
    int available() override { return 0; }
    int read() override { return -1; }
    int peek() override { return -1; }
    bool finish(const std::string &expectedSha256) {
        if (!initialized_ || failed_) return false;
        if (totalBytes_ != expectedBytes_) {
            error_ = "artifact download was incomplete";
            return false;
        }
        std::uint8_t digest[32] = {};
        if (mbedtls_sha256_finish_ret(&sha_, digest) != 0) {
            error_ = "artifact SHA-256 finalization failed";
            return false;
        }
        if (!firmware::sha256Matches(expectedSha256, digest)) {
            error_ = "artifact SHA-256 mismatch";
            return false;
        }
        return true;
    }
    std::uint32_t totalBytes() const { return totalBytes_; }
    bool initialized() const { return initialized_; }

   private:
    void fail(const char *message) {
        failed_ = true;
        error_ = message;
        setWriteError();
    }
    std::uint32_t expectedBytes_;
    std::uint32_t totalBytes_ = 0;
    String &error_;
    mbedtls_sha256_context sha_;
    bool initialized_ = false;
    bool failed_ = false;
};

// Buffers a download into whole flash sectors of a caller-owned region.
class PartitionSink final : public Stream {
   public:
    PartitionSink(const esp_partition_t *destination,
                  const std::uint32_t expectedBytes, String &error)
        : destination_(destination),
          expectedBytes_(expectedBytes),
          error_(error),
          sector_(new (std::nothrow) std::uint8_t[SPI_FLASH_SEC_SIZE]) {
        if (!sector_) fail("artifact buffer allocation failed");
    }
    ~PartitionSink() override { delete[] sector_; }
    std::size_t write(const std::uint8_t value) override {
        return write(&value, 1);
    }
    std::size_t write(const std::uint8_t *buffer,
                      const std::size_t size) override {
        if (failed_) return 0;
        if (size > expectedBytes_ - totalBytes_) {
            fail("artifact exceeds declared size");
            return 0;
        }
        std::size_t consumed = 0;
        while (consumed < size) {
            const std::size_t count = std::min<std::size_t>(
                size - consumed, SPI_FLASH_SEC_SIZE - buffered_);
            memcpy(sector_ + buffered_, buffer + consumed, count);
            buffered_ += count;
            consumed += count;
            if (buffered_ == SPI_FLASH_SEC_SIZE && !writeSector()) return 0;
        }
        totalBytes_ += size;
        return size;
    }
    int available() override { return 0; }
    int read() override { return -1; }
    int peek() override { return -1; }
    bool finish() {
        if (failed_) return false;
        if (totalBytes_ != expectedBytes_) {
            error_ = "artifact download was incomplete";
            return false;
        }
        return buffered_ == 0 || writeSector();
    }
    std::uint32_t totalBytes() const { return totalBytes_; }

   private:
    bool writeSector() {
        if (esp_partition_write(destination_, flushedBytes_, sector_,
                                buffered_) != ESP_OK) {
            fail("artifact write failed");
            return false;
        }
        flushedBytes_ += buffered_;
        buffered_ = 0;
        return true;
    }
    void fail(const char *message) {
        failed_ = true;
        error_ = message;
        setWriteError();
    }
    const esp_partition_t *destination_;
    std::uint32_t expectedBytes_;
    std::uint32_t totalBytes_ = 0;
    std::uint32_t flushedBytes_ = 0;
    std::size_t buffered_ = 0;
    String &error_;
    bool failed_ = false;
    std::uint8_t *sector_;
};

bool partitionSha256Matches(const esp_partition_t *partition,
                            const std::uint32_t sizeBytes,
                            const std::string &expectedSha256) {
    mbedtls_sha256_context sha;
    mbedtls_sha256_init(&sha);
    bool hashed = mbedtls_sha256_starts_ret(&sha, 0) == 0;
    std::uint8_t buffer[1024];
    for (std::uint32_t offset = 0; hashed && offset < sizeBytes;
         offset += sizeof(buffer)) {
        const std::uint32_t count =
            std::min<std::uint32_t>(sizeof(buffer), sizeBytes - offset);
        hashed = esp_partition_read(partition, offset, buffer, count) ==
                     ESP_OK &&
                 mbedtls_sha256_update_ret(&sha, buffer, count) == 0;
    }
    std::uint8_t digest[32] = {};
    hashed = hashed && mbedtls_sha256_finish_ret(&sha, digest) == 0;
    mbedtls_sha256_free(&sha);
    return hashed && firmware::sha256Matches(expectedSha256, digest);
}

}  // namespace

namespace firmware {

bool postCheck(const char *apiBaseUrl, const DeviceReport &report,
               Decision &decision, String &error) {
    NetworkRequestLock requestLock;
    String url = apiBaseUrl;
    if (url.endsWith("/")) url.remove(url.length() - 1);
    url += "/api/firmware/v1/check";

    firmware::CertificateDateClient secureClient;
    WiFiClient plainClient;
    HTTPClient http;
    if (!beginFirmwareRequest(http, secureClient, plainClient, url, 30000,
                              error)) {
        return false;
    }
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-RAD-Firmware-Provenance-Capability", "1");
    if (!report.firmwareProvenance.empty()) {
        http.addHeader("X-RAD-Firmware-Provenance",
                       report.firmwareProvenance.c_str());
        http.addHeader("X-RAD-Firmware-Provenance-ID",
                       provenance::tokenId(report.firmwareProvenance).c_str());
    }
    if (!report.firmwareHash.empty())
        http.addHeader("X-RAD-Firmware-Image-SHA256",
                       report.firmwareHash.c_str());
    std::string body = serializeReport(report);
    const int status = http.POST(
        reinterpret_cast<std::uint8_t *>(body.data()), body.size());
    if (status <= 0) {
        error = "firmware check connection failed: " +
                HTTPClient::errorToString(status);
        http.end();
        return false;
    }
    if (isRedirectStatus(status)) {
        error = "firmware check redirect rejected";
        http.end();
        return false;
    }
    if (status != HTTP_CODE_OK) {
        error = "firmware check returned HTTP " + String(status);
        http.end();
        return false;
    }

    const int contentLength = http.getSize();
    if (!isResponseLengthAllowed(contentLength,
                                 MAX_RESOLVER_RESPONSE_BYTES)) {
        error = contentLength == 0 ? "firmware response is empty"
                                   : "firmware response is too large";
        http.end();
        return false;
    }
    BoundedStringSink response(MAX_RESOLVER_RESPONSE_BYTES);
    if (contentLength > 0 && !response.reserve(contentLength)) {
        error = "firmware response allocation failed";
        http.end();
        return false;
    }
    const int received = http.writeToStream(&response);
    http.end();
    if (response.overflowed()) {
        error = "firmware response is too large";
        return false;
    }
    if (response.allocationFailed()) {
        error = "firmware response allocation failed";
        return false;
    }
    if (received < 0) {
        error = "firmware response read failed: " +
                HTTPClient::errorToString(received);
        return false;
    }
    if (response.value().isEmpty()) {
        error = "firmware response is empty";
        return false;
    }
    const std::size_t responseBytes = response.value().length();
    const std::size_t expectedResponseBytes =
        contentLength < 0 ? responseBytes
                          : static_cast<std::size_t>(contentLength);
    if (!transferCompleted(received, responseBytes, expectedResponseBytes)) {
        error = "firmware response content length mismatch";
        return false;
    }
    std::string parseError;
    if (!parseDecision(response.value().c_str(), report.deviceType, decision,
                       parseError)) {
        error = parseError.c_str();
        return false;
    }
    if (!decisionMatchesReport(report, decision)) {
        error = "firmware response does not match device report";
        return false;
    }
    return true;
}

bool installStreamedArtifact(const Artifact &artifact, const int updateCommand,
                             String &error) {
    NetworkRequestLock requestLock;
    firmware::CertificateDateClient secureClient;
    WiFiClient plainClient;
    HTTPClient http;
    if (!beginFirmwareRequest(http, secureClient, plainClient,
                              artifact.url.c_str(), 60000, error)) {
        return false;
    }
    const int status = http.GET();
    if (status <= 0) {
        error = "artifact connection failed: " +
                HTTPClient::errorToString(status);
        http.end();
        return false;
    }
    if (isRedirectStatus(status)) {
        error = "artifact redirect rejected";
        http.end();
        return false;
    }
    if (status != HTTP_CODE_OK) {
        error = "artifact returned HTTP " + String(status);
        http.end();
        return false;
    }
    const int contentLength = http.getSize();
    if (!knownContentLengthMatches(contentLength, artifact.sizeBytes)) {
        error = "artifact content length mismatch";
        http.end();
        return false;
    }
    if (!Update.begin(artifact.sizeBytes, updateCommand)) {
        error = "update partition rejected artifact";
        http.end();
        return false;
    }
    UpdateHashSink sink(artifact.sizeBytes, error);
    if (!sink.initialized()) {
        Update.abort();
        http.end();
        return false;
    }
    const int received = http.writeToStream(&sink);
    http.end();
    if (!transferCompleted(received, sink.totalBytes(), artifact.sizeBytes)) {
        if (error.isEmpty()) {
            error = received < 0
                        ? "artifact download failed: " +
                              HTTPClient::errorToString(received)
                        : "artifact download was incomplete";
        }
        Update.abort();
        return false;
    }
    if (!sink.finish(artifact.sha256)) {
        Update.abort();
        return false;
    }
    if (!Update.end(true)) {
        error = "artifact finalization failed";
        Update.abort();
        return false;
    }
    return true;
}

bool downloadArtifactToPartition(const Artifact &artifact,
                                 const esp_partition_t *destination,
                                 String &error) {
    if (destination == nullptr || artifact.sizeBytes == 0 ||
        artifact.sizeBytes > destination->size) {
        error = "artifact does not fit its destination";
        return false;
    }
    NetworkRequestLock requestLock;
    firmware::CertificateDateClient secureClient;
    WiFiClient plainClient;
    HTTPClient http;
    if (!beginFirmwareRequest(http, secureClient, plainClient,
                              artifact.url.c_str(), 60000, error)) {
        return false;
    }
    const int status = http.GET();
    if (status <= 0) {
        error = "artifact connection failed: " +
                HTTPClient::errorToString(status);
        http.end();
        return false;
    }
    if (isRedirectStatus(status)) {
        error = "artifact redirect rejected";
        http.end();
        return false;
    }
    if (status != HTTP_CODE_OK) {
        error = "artifact returned HTTP " + String(status);
        http.end();
        return false;
    }
    if (!knownContentLengthMatches(http.getSize(), artifact.sizeBytes)) {
        error = "artifact content length mismatch";
        http.end();
        return false;
    }
    const std::uint32_t eraseBytes =
        (artifact.sizeBytes + SPI_FLASH_SEC_SIZE - 1U) &
        ~(SPI_FLASH_SEC_SIZE - 1U);
    if (esp_partition_erase_range(destination, 0, eraseBytes) != ESP_OK) {
        error = "artifact destination erase failed";
        http.end();
        return false;
    }
    PartitionSink sink(destination, artifact.sizeBytes, error);
    const int received = http.writeToStream(&sink);
    http.end();
    if (!transferCompleted(received, sink.totalBytes(), artifact.sizeBytes)) {
        if (error.isEmpty()) {
            error = received < 0
                        ? "artifact download failed: " +
                              HTTPClient::errorToString(received)
                        : "artifact download was incomplete";
        }
        return false;
    }
    if (!sink.finish()) return false;
    // Trust what the flash holds, not what was sent to it.
    if (!partitionSha256Matches(destination, artifact.sizeBytes,
                                artifact.sha256)) {
        error = "artifact SHA-256 mismatch";
        return false;
    }
    return true;
}

bool installApplicationAndFilesystem(const Decision &decision, String &error) {
    if (decision.kind != "firmware" && decision.kind != "migration") {
        error = "unsupported release kind";
        return false;
    }
    const Artifact *application = nullptr;
    const Artifact *filesystem = nullptr;
    for (std::size_t index = 0; index < decision.artifactCount; ++index) {
        const Artifact &artifact = decision.artifacts[index];
        if (artifact.role == "filesystem") {
            if (filesystem != nullptr) {
                error = "release has duplicate filesystem artifacts";
                return false;
            }
            filesystem = &artifact;
        } else if (artifact.role == "application") {
            if (application != nullptr) {
                error = "release has duplicate application artifacts";
                return false;
            }
            application = &artifact;
        } else if (!isMetadataArtifactRole(artifact.role)) {
            error =
                ("unsupported installable artifact role: " + artifact.role)
                    .c_str();
            return false;
        }
    }
    if (application == nullptr) {
        error = "release has no application artifact";
        return false;
    }
    if (decision.kind == "migration" && filesystem != nullptr) {
        error = "migration release cannot replace the filesystem";
        return false;
    }
    if (filesystem != nullptr &&
        !installStreamedArtifact(*filesystem, U_SPIFFS, error)) {
        return false;
    }
    return installStreamedArtifact(*application, U_FLASH, error);
}

}  // namespace firmware

#endif
