#include "wifiSettings.h"
#include <NetworkRequestLock.h>

#include <errno.h>
#include <stdlib.h>
#include <time.h>
#include <algorithm>
#include <memory>

#include "SPIFFS.h"
#include "CertificateDateClient.h"
#include "FirmwareProvenance.h"
#include "esp_flash.h"
#include "services/upload_queue.h"
#include "state/state.h"
#include "utils/update.hpp"

#ifndef RAD_PUBLIC_KEY
#define RAD_PUBLIC_KEY "DEV_KEY_123"
#endif
#include "constants/strings.h"
#ifndef PROVISION
#include "uuid.hpp"
#include <SessionValidation.h>
#endif

#define WIFI_TAG "WIFI"

DashboardState dashboardState = {
    .isPaired = true,
    .hasUpdate = false,
    .preflightPending = true,
};

#ifndef PROVISION
#define SESSION_FILE "/session.json"

namespace {
    void addPhysicalFlashSize(JsonDocument &doc) {
        uint32_t physicalFlashSizeBytes = 0;
        const esp_err_t result =
            esp_flash_get_physical_size(nullptr, &physicalFlashSizeBytes);

        if (result != ESP_OK) {
            ESP_LOGW(WIFI_TAG, "failed to detect physical flash size: %d",
                     result);
            return;
        }

        doc["physicalFlashSizeBytes"] = physicalFlashSizeBytes;
    }
}  // namespace

std::shared_ptr<SegmentBase> currentSegment;
ESP32RecursiveMutex trainingMutex;
TrainingLifecycle trainingLifecycle;

Session session = {
    .id = uuid(),
};

#ifdef PIO_UNIT_TESTING
// Test observability hooks — see wifiSettings.h
bool trainingStartedNotified = false;
int trainingStartedHttpCode = -1;

bool calibrationUploaded = false;
int calibrationHttpCode = -1;

bool resultsUploaded = false;
int resultsHttpCode = -1;
#endif
#endif  // PROVISION

namespace {
constexpr size_t MAX_DASHBOARD_RESPONSE_BYTES = 64 * 1024;
constexpr size_t MAX_DASHBOARD_WIRE_BYTES =
    MAX_DASHBOARD_RESPONSE_BYTES + 8 * 1024;
constexpr time_t MINIMUM_DASHBOARD_UTC = 1704067200;  // 2024-01-01 UTC
extern const uint8_t dashboardCaBundle[] asm("_binary_x509_crt_bundle_start");

bool dashboardUtcReady() {
    // OTA uses the same system clock and CA bundle. Reuse its synchronized
    // clock when available; never disable certificate checks to recover.
    if (time(nullptr) >= MINIMUM_DASHBOARD_UTC) return true;
    configTime(0, 0, "time.cloudflare.com", "pool.ntp.org");
    const uint32_t startedAt = millis();
    while (millis() - startedAt < 10000) {
        if (time(nullptr) >= MINIMUM_DASHBOARD_UTC) return true;
        delay(250);
    }
    return false;
}

// HTTPClient's body reader has no timeout while a connected peer sends no
// bytes. Enforce a total deadline and a wire budget below both its header and
// body parsers, including unknown-length and chunked responses.
template <typename ClientType>
class DashboardClient final : public ClientType {
   public:
    explicit DashboardClient(uint32_t timeoutMs)
        : startedAt_(millis()), timeoutMs_(timeoutMs) {}

    bool failed() { return !withinBudget(); }
    int available() override {
        if (!withinBudget()) return 0;
        return ClientType::available();
    }
    uint8_t connected() override {
        return withinBudget() ? ClientType::connected() : 0;
    }
    int read() override {
        uint8_t value;
        return read(&value, 1) == 1 ? value : -1;
    }
    int read(uint8_t *buffer, size_t size) override {
        if (!withinBudget()) return -1;
        const int result = ClientType::read(
            buffer, std::min(size, MAX_DASHBOARD_WIRE_BYTES - received_));
        if (result > 0) received_ += result;
        return result;
    }
    size_t write(uint8_t value) override { return write(&value, 1); }
    size_t write(const uint8_t *buffer, size_t size) override {
        return withinBudget() ? ClientType::write(buffer, size) : 0;
    }

   private:
    bool withinBudget() {
        if (failed_ || millis() - startedAt_ >= timeoutMs_ ||
            received_ >= MAX_DASHBOARD_WIRE_BYTES) {
            failed_ = true;
            // Stream::timedRead also needs to stop immediately if it is
            // waiting for a delimiter when the deadline/budget is reached.
            this->Stream::setTimeout(0);
            ClientType::stop();
            return false;
        }
        return true;
    }
    const uint32_t startedAt_;
    const uint32_t timeoutMs_;
    size_t received_ = 0;
    bool failed_ = false;
};

class DashboardResponseSink final : public Stream {
   public:
    explicit DashboardResponseSink(String *output) : output_(output) {}
    size_t write(uint8_t value) override { return write(&value, 1); }
    size_t write(const uint8_t *buffer, size_t size) override {
        if (failed_ || size > MAX_DASHBOARD_RESPONSE_BYTES - received_ ||
            (output_ && !output_->concat(
                            reinterpret_cast<const char *>(buffer), size))) {
            failed_ = true;
            setWriteError();
            return 0;
        }
        received_ += size;
        return size;
    }
    int available() override { return 0; }
    int read() override { return -1; }
    int peek() override { return -1; }
    void flush() override {}
    bool failed() const { return failed_; }
    size_t receivedBytes() const { return received_; }

   private:
    String *output_;
    size_t received_ = 0;
    bool failed_ = false;
};
}  // namespace

// All dashboard credentials remain scoped to the configured API origin.
int postJson(const String &endpoint, const JsonDocument &doc,
             String *responsePayload, const int timeoutMs,
             DashboardResponseMetrics *metrics) {
    NetworkRequestLock requestLock;
    if (metrics) *metrics = DashboardResponseMetrics{};
    if (responsePayload) *responsePayload = "";
    if (timeoutMs <= 0 || timeoutMs > 30000 || doc.overflowed())
        return HTTPC_ERROR_TOO_LESS_RAM;

    String origin = RAD_SERVER;
    while (origin.endsWith("/")) origin.remove(origin.length() - 1);
    const String apiRoot = origin + "/api/dtt/v2";
    String url = endpoint;
    if (endpoint.startsWith("/") && !endpoint.startsWith("//")) {
        url = apiRoot + endpoint;
    }
    if (!url.startsWith(apiRoot + "/"))
        return HTTPC_ERROR_CONNECTION_REFUSED;
    const bool secure = url.startsWith("https://");
    bool allowPlaintext = false;
#if defined(VERSIONDEV) || defined(DTT_ALLOW_LOCAL_HTTP) || \
    defined(DTT_MIGRATION_LAB_INSECURE_HTTP)
    allowPlaintext = origin.startsWith("http://");
#endif
    if (!secure && !allowPlaintext) return HTTPC_ERROR_CONNECTION_REFUSED;
    if (secure && !dashboardUtcReady()) {
        ESP_LOGE(WIFI_TAG, "verified dashboard transport needs a valid clock");
        return HTTPC_ERROR_CONNECTION_REFUSED;
    }

    int memRetries = 0;

    // Wait for enough memory, up to 10 times
    while (ESP.getFreeHeap() < 20000 && memRetries < 10) {
        ESP_LOGD(WIFI_TAG, "not enough memory, retrying... (%d/10)",
                 memRetries + 1);
        memRetries++;
        vTaskDelay(1000 / portTICK_PERIOD_MS);
    }
    if (ESP.getFreeHeap() < 20000) return HTTPC_ERROR_TOO_LESS_RAM;

    // HTTPClient retains a borrowed pointer even after some end()/begin()
    // paths. Declare the owners first so the transport outlives HTTP cleanup,
    // including early returns after a failed setup or request.
    std::unique_ptr<DashboardClient<firmware::CertificateDateClient>> secureClient;
    std::unique_ptr<DashboardClient<WiFiClient>> plainClient;
    WiFiClient *currentClient;
    HTTPClient http;
    bool began = false;
    http.setTimeout(timeoutMs);
    http.setConnectTimeout(timeoutMs);
    http.setReuse(false);
    http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
    if (secure) {
        secureClient.reset(
            new DashboardClient<firmware::CertificateDateClient>(timeoutMs));
        secureClient->setCACertBundle(dashboardCaBundle);
        secureClient->setHandshakeTimeout((timeoutMs + 999) / 1000);
        currentClient = secureClient.get();
        began = http.begin(*secureClient, url);
    } else {
        plainClient.reset(new DashboardClient<WiFiClient>(timeoutMs));
        currentClient = plainClient.get();
        began = http.begin(*plainClient, url);
    }

    if (!began) {
        ESP_LOGE(WIFI_TAG, "dashboard HTTP setup failed");
        currentClient->stop();
        return HTTPC_ERROR_CONNECTION_REFUSED;
    }
    const char *responseHeaders[] = {"Content-Encoding"};
    http.collectHeaders(responseHeaders, 1);
    http.addHeader("Accept-Encoding", "identity");
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Authorization", "Bearer " + String(RAD_PUBLIC_KEY));
    http.addHeader("ngrok-skip-browser-warning", "true");
    http.addHeader("X-RAD-Firmware-Provenance-Capability", "1");
    const auto provenanceToken = firmware::provenance::currentToken();
    if (!provenanceToken.empty()) {
        http.addHeader("X-RAD-Firmware-Provenance", provenanceToken.c_str());
        http.addHeader("X-RAD-Firmware-Provenance-ID",
                       firmware::provenance::currentTokenId().c_str());
        http.addHeader("X-RAD-Firmware-Image-SHA256",
                       firmware::provenance::currentImageSha256().c_str());
    }

    String requestBody;
    const size_t requestSize = measureJson(doc);
    if (!requestBody.reserve(requestSize) ||
        serializeJson(doc, requestBody) != requestSize) {
        http.end();
        currentClient->stop();
        return HTTPC_ERROR_TOO_LESS_RAM;
    }
    int httpResponseCode = -1;

#if defined(RAD_HIL_VARIANT)
    Serial.printf("\nRAD_DIAG tls_begin_heap=%u max_alloc=%u\n",
                  ESP.getFreeHeap(), ESP.getMaxAllocHeap());
#endif
    httpResponseCode = http.POST(requestBody);
    if (metrics && httpResponseCode > 0) metrics->httpStatus = httpResponseCode;

    if (httpResponseCode < 0) {
        const String transportError =
            HTTPClient::errorToString(httpResponseCode);
        ESP_LOGE(WIFI_TAG, "dashboard POST failed: %d (%s)",
                 httpResponseCode, transportError.c_str());

        // Avoid linking the full TLS error-string table when error logs are
        // compiled out. The BLE staging diagnostic still records its TLS code.
#if ARDUHAL_LOG_LEVEL >= ARDUHAL_LOG_LEVEL_ERROR || (defined(RAD_HIL_VARIANT) && DTT_ENABLE_RAD_BLE)
        if (secureClient != nullptr) {
            char sslErrorText[128] = {};
            const int sslError =
                secureClient->lastError(sslErrorText, sizeof(sslErrorText));
#if defined(RAD_HIL_VARIANT)
            Serial.printf("\nRAD_DIAG http_error=%d tls_error=%d heap=%u max_alloc=%u\n",
                          httpResponseCode, sslError, ESP.getFreeHeap(), ESP.getMaxAllocHeap());
#endif
            if (sslError != 0) {
                ESP_LOGE(WIFI_TAG, "TLS error %d: %s", sslError,
                         sslErrorText);
            }
        }
#endif
    }

    if (httpResponseCode > 0) {
        const String encoding = http.header("Content-Encoding");
        const int responseSize = http.getSize();
        DashboardResponseSink sink(responsePayload);
        if (responseSize > static_cast<int>(MAX_DASHBOARD_RESPONSE_BYTES) ||
            (!encoding.isEmpty() && !encoding.equalsIgnoreCase("identity"))) {
            httpResponseCode = HTTPC_ERROR_TOO_LESS_RAM;
        } else if (responseSize != 0) {
            const int received = http.writeToStream(&sink);
            if (received < 0 || sink.failed())
                httpResponseCode = received < 0 ? received
                                               : HTTPC_ERROR_TOO_LESS_RAM;
        }
        if (metrics) metrics->responseBytes = sink.receivedBytes();
    }
    if ((secureClient && secureClient->failed()) ||
        (plainClient && plainClient->failed()))
        httpResponseCode = HTTPC_ERROR_READ_TIMEOUT;
    // Never let partial or rejected bodies reach a settings/provision parser.
    if (httpResponseCode < 0 && responsePayload) *responsePayload = "";
    http.end();
    currentClient->stop();
    return httpResponseCode;
}

#ifndef PROVISION
void checkIfPairedTask(void *pvParameters) {
    auto isInCorrectState = []() { return stateMachine->is("pairing"_s); };

    while (isInCorrectState()) {
        getIsPaired();
        if (dashboardState.isPaired) {
            break;
        }
        vTaskDelay(2000 / portTICK_PERIOD_MS);
    }

    if (dashboardState.isPaired) {
        stateMachine->process_event(done{});
    }
    vTaskDelete(nullptr);
}

namespace {
void notifyActualTraining(const String& boundTrainer) {
    // Best effort only: no retry after an ambiguous POST, and no SML events.
    if (WiFiClass::status() != WL_CONNECTED || boundTrainer.isEmpty()) return;
    JsonDocument doc;
    doc["trainerId"] = boundTrainer;
    const int code = postJson("/training-started", doc);
    ESP_LOGD(WIFI_TAG, "training-started HTTP %d", code);
#ifdef PIO_UNIT_TESTING
    trainingStartedHttpCode = code;
    trainingStartedNotified = code == 200;
#endif
}
}  // namespace

void notifyTrainingTask(void* parameter) {
    {
        std::unique_ptr<String> boundTrainer(static_cast<String*>(parameter));
        notifyActualTraining(boundTrainer ? *boundTrainer : trainerId);
    }
    vTaskDelete(nullptr);
}

#endif  // PROVISION

String provisionError = "";

void provisionTask(void *pvParameters) {
    provisionError = "";
    // Production arrives here already online; only the factory image may
    // need to wait for Wi-Fi to settle.
    if (WiFiClass::status() != WL_CONNECTED) {
        vTaskDelay(5000 / portTICK_PERIOD_MS);
    }

    int retries = 0;
    while (WiFiClass::status() != WL_CONNECTED && retries < 10) {
        ESP_LOGD(WIFI_TAG, "WiFi not connected, retrying... (%d/10)",
                 retries + 1);
        vTaskDelay(5000 / portTICK_PERIOD_MS);
        retries++;
    }
    if (WiFiClass::status() != WL_CONNECTED) {
        ESP_LOGD(WIFI_TAG, "WiFi connection failed after 10 retries");
        provisionError = "WiFi failed after 10 retries";
        stateMachine->process_event(provision_failed{});
        vTaskDelete(nullptr);
        return;
    }

    auto result = getTrainerIdAndSerial();
    if (result) {
        stateMachine->process_event(provision_complete{});
    } else {
        stateMachine->process_event(provision_failed{});
    }
    vTaskDelete(nullptr);
};

bool getTrainerIdAndSerial() {
    ESP_LOGD(WIFI_TAG, "about to get trainerID");
    int timeout = 0;
    while (WiFiClass::status() != WL_CONNECTED && timeout < 10) {
        delay(1000);
        timeout++;
    }
    if (WiFiClass::status() != WL_CONNECTED) {
        provisionError = "WiFi disconnected";
        return false;
    }

    JsonDocument doc;
    doc["macAddress"] = WiFi.macAddress();

    String payload = "{}";
    const int httpResponseCode = postJson("/provision", doc, &payload, 15000);
    ESP_LOGD(WIFI_TAG, "provision HTTP %d", httpResponseCode);

    if (httpResponseCode != 200) {
        if (httpResponseCode < 0) {
            provisionError = "Network error: " +
                             HTTPClient::errorToString(httpResponseCode);
        } else {
            provisionError = "HTTP " + String(httpResponseCode);
        }
        return false;
    }

    JsonDocument respDoc;
    DeserializationError err = deserializeJson(respDoc, payload);

    if (err) {
        provisionError = "Bad response from server";
        return false;
    }

    const char *trainerIdFromJson = respDoc["trainerId"] | "";
    int serialNumberFromJson = respDoc["serialNumber"] | 0;

    if (strlen(trainerIdFromJson) == 0) {
        provisionError = "Server returned empty trainer ID";
        return false;
    }

    if (!saveToEEPROM(String(trainerIdFromJson), serialNumberFromJson)) {
        provisionError = "Save failed";
        return false;
    }
    // Force the update step to resolve once using the newly provisioned
    // trainer ID.
    invalidateFirmwareUpdateDecision();
    return true;
}

#ifndef PROVISION
namespace {
portMUX_TYPE settingsFetchStatusMux = portMUX_INITIALIZER_UNLOCKED;
SettingsFetchStatus settingsFetchStatus;

template <typename Update>
void updateSettingsFetchStatus(uint32_t generation, Update update) {
    const uint32_t now = millis();
    const uint32_t heap = ESP.getFreeHeap();
    const uint32_t largest = ESP.getMaxAllocHeap();
    portENTER_CRITICAL(&settingsFetchStatusMux);
    if (settingsFetchStatus.generation == generation) {
        update(settingsFetchStatus);
        settingsFetchStatus.updatedAtMs = now;
        settingsFetchStatus.freeHeap = heap;
        settingsFetchStatus.largestBlock = largest;
    }
    portEXIT_CRITICAL(&settingsFetchStatusMux);
}

uint32_t beginSettingsFetchStatus() {
    const uint32_t now = millis();
    const uint32_t heap = ESP.getFreeHeap();
    const uint32_t largest = ESP.getMaxAllocHeap();
    portENTER_CRITICAL(&settingsFetchStatusMux);
    uint32_t generation = settingsFetchStatus.generation + 1;
    if (generation == 0) generation = 1;
    settingsFetchStatus = SettingsFetchStatus{};
    settingsFetchStatus.generation = generation;
    settingsFetchStatus.stage = SettingsFetchStage::Requesting;
    settingsFetchStatus.startedAtMs = now;
    settingsFetchStatus.updatedAtMs = now;
    settingsFetchStatus.freeHeap = heap;
    settingsFetchStatus.largestBlock = largest;
    portEXIT_CRITICAL(&settingsFetchStatusMux);
    return generation;
}
}  // namespace

SettingsFetchStatus getSettingsFetchStatus() {
    portENTER_CRITICAL(&settingsFetchStatusMux);
    const auto snapshot = settingsFetchStatus;
    portEXIT_CRITICAL(&settingsFetchStatusMux);
    return snapshot;
}

static void sessionFromJson(JsonDocument &sessionJson) {
    TrainingGuard guard(trainingMutex);

    // the session id is set on device boot.
    session.settingsId = sessionJson["settingsId"].as<String>();
    session.name = sessionJson["name"].as<String>();
    session.tagline = sessionJson["tagline"] | "";

    if (sessionJson["iconSetId"].isNull() ||
        !sessionJson["iconSetId"].is<String>()) {
        session.iconId.reset();
    } else {
        const String iconSetIdStr = sessionJson["iconSetId"].as<String>();
        errno = 0;
        char *endPtr = nullptr;
        const long parsedIconId = strtol(iconSetIdStr.c_str(), &endPtr, 10);
        if (endPtr != iconSetIdStr.c_str() && errno == 0) {
            session.iconId = static_cast<int>(parsedIconId);
        } else {
            session.iconId.reset();
        }
    }

    // Optional texts: a missing one stays empty instead of reading "null".
    session.description = sessionJson["description"] | "";
    session.finalText = sessionJson["finalText"] | "";

    // Parse finalColor if present (LED color for final page)
    if (sessionJson["finalColor"].is<int>()) {
        session.finalColor = sessionJson["finalColor"].as<int>();
    } else {
        session.finalColor.reset();
    }

    // Parse icon configuration if present
    if (sessionJson["icon"].is<JsonObject>()) {
        JsonObject iconJson = sessionJson["icon"];
        session.icon.set = iconJson["set"].as<String>();
        session.icon.set_id = iconJson["set_id"].as<int>();
    } else {
        // Use default values if not provided
        session.icon = defaultIconConfig;
    }

    if (sessionJson["toy"].is<JsonObject>()) {
        JsonObject toyJson = sessionJson["toy"];
        ToyCalibration calibration;

        // Parse calibration data if present
        if (toyJson["calibration"].is<JsonObject>()) {
            JsonObject calibrationJson = toyJson["calibration"];
            calibration.isCalibrated =
                calibrationJson["isCalibrated"].as<bool>();
            calibration.minCm = calibrationJson["minCm"].as<float>();
            calibration.maxCm = calibrationJson["maxCm"].as<float>();
            // Ask for a new calibration instead of training on a stored
            // range the device cannot use (backend minCm is the deep end).
            if (checkCalibration(calibration.maxCm, calibration.minCm) !=
                CalibrationProblem::None)
                calibration.isCalibrated = false;
            calibration.calibratedAt =
                calibrationJson["calibratedAt"].as<String>();
        }

        // Keep description for safety, in case of older payloads
        String toyTagline = EMPTY_STRING;
        if (toyJson["tagline"].is<String>()) {
            toyTagline = toyJson["tagline"].as<String>();
        } else if (toyJson["description"].is<String>()) {
            toyTagline = toyJson["description"].as<String>();
        }

        session.toy = Toy{
            .id = toyJson["id"].as<String>(),
            .name = toyJson["name"].as<String>(),
            .tagline = toyTagline,
            .calibration = calibration,
        };
    } else {
        session.toy = std::nullopt;
    }

    session.segmentCount = sessionJson["segmentCount"].as<uint16_t>();
    session.pageIdx = sessionJson["pageIdx"].as<uint16_t>();
    session.durationMinutes = sessionJson["durationMinutes"].as<uint16_t>();
    session.handsFreeMode = sessionJson["handsFreeMode"] | false;

    const auto segments = sessionJson["segments"].as<JsonArray>();
    auto type = TrainingType::REPETITION;
    session.segments.clear();

    for (const auto &i : segments) {
        JsonObject segment = i;

        auto typeString = segment["type"].as<String>();
        typeString.toLowerCase();

        if (typeString == REPETITION_STRING) {
            type = TrainingType::REPETITION;
        } else if (typeString == ENDURANCE_STRING) {
            type = TrainingType::ENDURANCE;
        } else if (typeString == FREEFORM_STRING) {
            type = TrainingType::FREEFORM;
        } else if (typeString == BOUNCE_STRING) {
            type = TrainingType::BOUNCE;
        }

        // Parse passFail configuration if present
        PassFailConfig passFailConfig;
        if (segment["passFail"].is<JsonObject>()) {
            JsonObject passFailJson = segment["passFail"];
            passFailConfig.enabled = passFailJson["enabled"].as<bool>();
            passFailConfig.threshold = passFailJson["threshold"].as<int>();
            passFailConfig.failureText =
                passFailJson["failureText"].is<String>()
                    ? passFailJson["failureText"].as<String>()
                    : "";
        }

        auto segmentId = segment["id"].as<String>();
        auto segmentName = segment["name"].as<String>();
        String segmentDifficulty = segment["difficulty"] | "";
        auto target = segment["params"]["target"].as<int>();
        auto startPos = segment["params"]["startPosition"].as<float>();
        auto endPos = segment["params"]["endPosition"].as<float>();
        auto depthIncrease =
            segment["params"]["trainingDepthIncrease"].as<int>();
        auto speed = segment["params"]["trainingSpeed"].as<float>();
        auto targetWindow = segment["params"]["targetWindow"].as<float>();

        session.segments.push_back(Segment{
            .id = segmentId,
            .idx = segment["idx"].as<uint16_t>(),
            .name = segmentName,
            .difficulty = segmentDifficulty,
            .type = type,
            .params =
                TrainingParams{
                    .target = target,
                    .startPosition = startPos,
                    .endPosition = endPos,
                    .trainingDepthIncrease = depthIncrease,
                    .trainingSpeed = speed,
                    .targetWindow = targetWindow,
                },
            .passFail = passFailConfig,
        });
    }

    // If toy is calibrated on backend, override segment positions
    // Backend: minCm = lower value (endPosition), maxCm = higher value
    // (startPosition)
    if (session.toy.has_value() && session.toy->calibration.isCalibrated) {

        for (auto &segment : session.segments) {
            segment.params.startPosition =
                session.toy->calibration.maxCm;  // maxCm is the higher value
            segment.params.endPosition =
                session.toy->calibration.minCm;  // minCm is the lower value
        }

        // Mark session as calibrated
        session.isCalibrated = true;
        session.calibratedMinPosition = session.toy->calibration.maxCm;
        session.calibratedMaxPosition = session.toy->calibration.minCm;
    }

};

namespace {
constexpr char SESSION_TEMP_FILE[] = "/session.tmp";
constexpr char SESSION_BACKUP_FILE[] = "/session.bak";

// Verify a closed staging file against the exact bounded serialization with
// constant memory. A matching size alone cannot detect corrupted/short reads.
class SessionFileVerifier {
   public:
    explicit SessionFileVerifier(File &file) : file_(file) {}
    size_t write(uint8_t value) { return write(&value, 1); }
    size_t write(const uint8_t *bytes, size_t length) {
        if (failed_) return 0;
        for (size_t index = 0; index < length; ++index) {
            const int value = file_.read();
            if (value < 0 || static_cast<uint8_t>(value) != bytes[index]) {
                failed_ = true;
                return index;
            }
            ++verifiedBytes_;
        }
        return length;
    }
    size_t verifiedBytes() const { return verifiedBytes_; }
    bool complete(size_t expected) {
        return !failed_ && verifiedBytes_ == expected && file_.read() == -1;
    }
   private:
    File &file_;
    size_t verifiedBytes_ = 0;
    bool failed_ = false;
};

bool readSessionCache(const char *path, JsonDocument &document, String &error) {
    File file = SPIFFS.open(path, "r");
    if (!file || file.size() == 0 ||
        file.size() > MAX_DASHBOARD_RESPONSE_BYTES) {
        error = "Session cache is missing or too large";
        file.close();
        return false;
    }
    const auto result = deserializeJson(
        document, file, DeserializationOption::NestingLimit(8));
    file.close();
    if (result || document.overflowed()) {
        error = "Session cache is not valid JSON";
        return false;
    }
    return validateSessionDocument(document.as<JsonObjectConst>(), error,
                                   SessionDocumentMode::DashboardPage);
}

bool persistSessionDocument(
    const JsonDocument &document, String &error,
    SessionPersistenceError *failure = nullptr,
    SettingsWriteStatus *writeStatus = nullptr) {
    if (failure) *failure = SessionPersistenceError::None;
    SettingsWriteStatus observed;
    const auto reject = [&](const char *message, SessionPersistenceError reason) {
        error = message;
        if (failure) *failure = reason;
        if (writeStatus) *writeStatus = observed;
        return false;
    };
    const size_t expectedSize = measureJson(document);
    observed.expected = expectedSize;
    if (document.overflowed() || expectedSize == 0 ||
        expectedSize > MAX_DASHBOARD_RESPONSE_BYTES) {
        return reject("Session document exceeds the storage limit",
                      SessionPersistenceError::Limit);
    }
    // Mount without auto-formatting: a storage fault must not erase the last
    // session or pending upload queue as a side effect of a network request.
    if (!SPIFFS.begin(false)) {
        return reject("Could not mount session storage",
                      SessionPersistenceError::Mount);
    }
    observed.fsUsed = SPIFFS.usedBytes();
    observed.fsTotal = SPIFFS.totalBytes();
    SPIFFS.remove(SESSION_TEMP_FILE);
    File temporary = SPIFFS.open(SESSION_TEMP_FILE, "w");
    observed.opened = static_cast<bool>(temporary);
    const size_t written = temporary ? serializeJson(document, temporary) : 0;
    observed.written = written;
    temporary.flush();
    // Writable SPIFFS handles may report a stale size until close. Record it
    // for diagnostics, but never use it to accept or reject durable storage.
    observed.openReportedSize = temporary.size();
    temporary.close();
    bool complete = observed.opened && written == expectedSize;
    if (complete) {
        File staged = SPIFFS.open(SESSION_TEMP_FILE, "r");
        observed.reopened = static_cast<bool>(staged);
        observed.reopenedSize = staged.size();
        complete = observed.reopened && observed.reopenedSize == expectedSize;
        if (complete) {
            SessionFileVerifier verifier(staged);
            const size_t verified = serializeJson(document, verifier);
            observed.verifiedBytes = verifier.verifiedBytes();
            complete = verified == expectedSize && verifier.complete(expectedSize);
        }
        staged.close();
    }
    observed.verified = complete;
    if (!complete) {
        SPIFFS.remove(SESSION_TEMP_FILE);
        return reject("Could not persist the complete replacement session",
                      SessionPersistenceError::Write);
    }

    if (SPIFFS.exists(SESSION_FILE)) {
        bool stagePrimary = true;
        if (SPIFFS.exists(SESSION_BACKUP_FILE)) {
            // Distinguish an interrupted replacement from an unreadable
            // primary. Parse/allocation failure alone must never delete the
            // only previous copy. Ordinary rotation needs no extra document.
            JsonDocument previous;
            String previousError;
            if (readSessionCache(SESSION_FILE, previous, previousError)) {
                if (!SPIFFS.remove(SESSION_BACKUP_FILE)) {
                    SPIFFS.remove(SESSION_TEMP_FILE);
                    return reject("Could not rotate the session backup",
                                  SessionPersistenceError::Rotate);
                }
            } else {
                previous.clear();
                if (!readSessionCache(SESSION_BACKUP_FILE, previous,
                                      previousError) ||
                    !SPIFFS.remove(SESSION_FILE)) {
                    SPIFFS.remove(SESSION_TEMP_FILE);
                    return reject("Could not recover the previous session cache",
                                  SessionPersistenceError::Recover);
                }
                stagePrimary = false;
            }
        }
        if (stagePrimary && !SPIFFS.rename(SESSION_FILE, SESSION_BACKUP_FILE)) {
            SPIFFS.remove(SESSION_TEMP_FILE);
            return reject("Could not stage the existing session",
                          SessionPersistenceError::Stage);
        }
    }
    if (!SPIFFS.rename(SESSION_TEMP_FILE, SESSION_FILE)) {
        if (SPIFFS.exists(SESSION_BACKUP_FILE))
            SPIFFS.rename(SESSION_BACKUP_FILE, SESSION_FILE);
        SPIFFS.remove(SESSION_TEMP_FILE);
        return reject("Could not commit the replacement session",
                      SessionPersistenceError::Commit);
    }
    SPIFFS.remove(SESSION_BACKUP_FILE);
    if (writeStatus) *writeStatus = observed;
    error = "";
    return true;
}
}  // namespace

bool applySessionDocument(JsonDocument sessionJson, String &error) {
    if (sessionJson.overflowed() ||
        !validateSessionDocument(sessionJson.as<JsonObjectConst>(), error,
                                 SessionDocumentMode::Complete))
        return false;
    sessionJson["segmentCount"] = sessionJson["segments"].size();
    sessionJson["segmentIdx"] = 0;
    sessionJson["pageIdx"] = 0;
    if (!persistSessionDocument(sessionJson, error)) return false;

    // The state-machine adapter serializes this callback while no segment is
    // active. Validation and durable replacement precede live-state mutation.
    sessionFromJson(sessionJson);
    session.segmentIdx = 0;
    session.pageIdx = 0;
    session.segmentFailureCounts.clear();
    return true;
}

void loadSessionTask(void *pvParameters) {
    const uint32_t generation = getSettingsFetchStatus().generation;
    JsonDocument sessionJson;
    String error;
    bool valid = false;
    SettingsCacheSource cacheSource = SettingsCacheSource::Recovery;
    const bool cacheMounted = SPIFFS.begin(false);
    if (cacheMounted) {
        valid = readSessionCache(SESSION_FILE, sessionJson, error);
        if (valid) cacheSource = SettingsCacheSource::Primary;
        if (!valid) {
            sessionJson.clear();
            valid = readSessionCache(SESSION_BACKUP_FILE, sessionJson, error);
            if (valid) cacheSource = SettingsCacheSource::Backup;
        }
    }
    bool installed = false;
    stateMachine->process_event(session_load_ready{
        [&]() {
            // A cached later page cannot start a new session at index zero.
            if (valid && sessionJson["pageIdx"].as<uint16_t>() ==
                             session.segmentIdx / PAGE_SIZE) {
                sessionFromJson(sessionJson);
            } else {
                cacheSource = SettingsCacheSource::Recovery;
                session = Session{};
                ESP_LOGW(WIFI_TAG, "no usable cached session; using recovery");
            }
            return true;
        },
        installed});
    updateSettingsFetchStatus(generation, [&](auto &status) {
        status.cacheSource = cacheSource;
        status.cacheMounted = cacheMounted;
    });
    vTaskDelete(nullptr);
}

void fetchSettingsTask(void *pvParameters) {
    const uint32_t generation = beginSettingsFetchStatus();
    JsonDocument sessionJson;

    // if not connected to wifi, return
    if (WiFiClass::status() != WL_CONNECTED) {
        updateSettingsFetchStatus(generation, [](auto &status) {
            status.stage = SettingsFetchStage::HttpFailed;
            status.error = SettingsFetchError::Offline;
        });
        // Fall back to the validated cache while offline.
        ESP_LOGD(WIFI_TAG, "no wifi, loading cached settings");
        stateMachine->process_event(session_load_failed{});
        vTaskDelete(nullptr);
        return;
    }
    ESP_LOGD(WIFI_TAG, "about to fetch settings");
    JsonDocument doc;
    doc["trainerId"] = trainerId;
    doc["pageIdx"] = static_cast<int>(floor(session.segmentIdx / PAGE_SIZE));
    doc["sessionId"] = session.id;

    String payload = "{}";
    int httpResponseCode = -1;
    for (int attempt = 0; attempt < 3; ++attempt) {
        DashboardResponseMetrics metrics;
        httpResponseCode = postJson("/get-settings", doc, &payload, 15000, &metrics);
        updateSettingsFetchStatus(generation, [&](auto &status) {
            status.attempt = attempt + 1;
            status.httpStatus = metrics.httpStatus;
            status.clientStatus = httpResponseCode;
            status.responseBytes = metrics.responseBytes;
            status.retainedBodyBytes = payload.length();
        });
        ESP_LOGD(WIFI_TAG, "HTTP Response code (attempt %d): %d", attempt + 1,
                 httpResponseCode);
        if (httpResponseCode == 200) {
            break;
        }
        if (attempt < 2) vTaskDelay(5000 / portTICK_PERIOD_MS);
    }

    if (httpResponseCode != 200) {
        updateSettingsFetchStatus(generation, [&](auto &status) {
            status.stage = SettingsFetchStage::HttpFailed;
            status.error = httpResponseCode < 0 ? SettingsFetchError::Transport
                                               : SettingsFetchError::Http;
        });
        // Diagnostic for support: distinguishes "dashboard errored while online"
        // (http>0, wifi=1, health=1) from "truly offline" (wifi=0).
        ESP_LOGW(WIFI_TAG,
                 "get-settings failed: http=%d wifi=%d health=%d -> using "
                 "cached session",
                 httpResponseCode, WiFiClass::status() == WL_CONNECTED,
                 healthCheckPassed);
        stateMachine->process_event(session_load_failed{});
        vTaskDelete(nullptr);
        return;
    }

    String validationError;
    updateSettingsFetchStatus(generation, [](auto &status) {
        status.stage = SettingsFetchStage::Parsing;
    });
    const auto parseError = deserializeJson(
        sessionJson, payload, DeserializationOption::NestingLimit(8));
    // Release the raw body before cache serialization/parsing into Session.
    payload = String();
    const bool valid = !parseError && !sessionJson.overflowed() &&
        validateSessionDocument(sessionJson.as<JsonObjectConst>(), validationError,
                                SessionDocumentMode::DashboardPage);
    const bool pageMatches = valid &&
        sessionJson["pageIdx"].as<uint16_t>() == doc["pageIdx"].as<uint16_t>();
    updateSettingsFetchStatus(generation, [&](auto &status) {
        status.parseCode = static_cast<uint8_t>(parseError.code());
        status.overflow = sessionJson.overflowed();
        if (parseError || status.overflow) {
            status.stage = SettingsFetchStage::ParseFailed;
            status.error = SettingsFetchError::Parse;
        } else if (!valid) {
            status.stage = SettingsFetchStage::ValidationFailed;
            status.error = SettingsFetchError::Validation;
        } else if (!pageMatches) {
            status.stage = SettingsFetchStage::PageMismatch;
            status.error = SettingsFetchError::RequestPage;
        } else {
            status.stage = SettingsFetchStage::AwaitingInstall;
        }
    });
    if (!valid || !pageMatches) {
        ESP_LOGW(WIFI_TAG, "dashboard session rejected; keeping cached session");
        stateMachine->process_event(session_load_failed{});
        vTaskDelete(nullptr);
        return;
    }

    bool installed = false;
    const bool accepted = stateMachine->process_event(session_load_ready{
        [&]() {
            updateSettingsFetchStatus(generation, [](auto &status) {
                status.callbackInvoked = true;
            });
            if (sessionJson["pageIdx"].as<uint16_t>() !=
                session.segmentIdx / PAGE_SIZE) {
                updateSettingsFetchStatus(generation, [](auto &status) {
                    status.stage = SettingsFetchStage::PageMismatch;
                    status.error = SettingsFetchError::LivePage;
                });
                return false;
            }
            SessionPersistenceError persistenceError;
            SettingsWriteStatus writeStatus;
            updateSettingsFetchStatus(generation, [](auto &status) {
                status.stage = SettingsFetchStage::Persisting;
            });
            if (!persistSessionDocument(sessionJson, validationError,
                                        &persistenceError, &writeStatus)) {
                updateSettingsFetchStatus(generation, [&](auto &status) {
                    status.stage = SettingsFetchStage::PersistenceFailed;
                    status.error = SettingsFetchError::Persistence;
                    status.persistenceError = persistenceError;
                    status.write = writeStatus;
                });
                return false;
            }
            updateSettingsFetchStatus(generation, [&](auto &status) {
                status.stage = SettingsFetchStage::Installing;
                status.persisted = true;
                status.write = writeStatus;
            });
            sessionFromJson(sessionJson);
            updateSettingsFetchStatus(generation, [](auto &status) {
                status.stage = SettingsFetchStage::Installed;
                status.persisted = true;
                status.installed = true;
            });
            return true;
        },
        installed});
    updateSettingsFetchStatus(generation, [&](auto &status) {
        status.eventAccepted = accepted;
        if (!installed && status.stage == SettingsFetchStage::AwaitingInstall) {
            status.stage = SettingsFetchStage::StateRejected;
            status.error = SettingsFetchError::State;
        }
    });
    if (!installed) {
        ESP_LOGW(WIFI_TAG, "dashboard session was not installed");
        vTaskDelete(nullptr);
        return;
    }

    // We're confirmed online (get-settings just returned 200) — opportunistically
    // drain any training results queued from an earlier offline/low-heap moment.
    flushUploadQueue();

    ESP_LOGD(WIFI_TAG, "settings fetched, got %d / %d segments with pageIdx %d",
             session.segments.size(), session.segmentCount, session.pageIdx);
    vTaskDelete(nullptr);
}

namespace {
std::unique_ptr<JsonDocument> captureCompletedResult() {
    TrainingGuard guard(trainingMutex);
    if (!currentSegment) return {};
#ifndef BYPASS_PLAY
    if (currentSegment->state != TrainingState::END) return {};
#endif
    String toyId = session.toy.has_value() ? session.toy->id : "";
    const Segment* definition = getSegmentByIdx(session.segmentIdx);
    int passedStatus = -1;
    if (definition && definition->passFail.enabled)
        passedStatus = currentSegment->grade() >= definition->passFail.threshold ? 1 : 0;
    auto result = std::make_unique<JsonDocument>(currentSegment->createPayload(
        trainerId, session.id, session.segmentIdx, session.settingsId, toyId, passedStatus));
    if (result->overflowed()) return {};
    return result;
}

void persistAndUploadResult(const JsonDocument& document) {
    if (!enqueuePayload(document)) {
        ESP_LOGE(WIFI_TAG, "failed to persist segment result to upload queue");
        return;
    }
    const int uploaded = flushUploadQueue();
    ESP_LOGD(WIFI_TAG, "queued-result flush uploaded %d item(s)", uploaded);
#ifdef PIO_UNIT_TESTING
    resultsUploaded = uploaded > 0;
    resultsHttpCode = uploaded > 0 ? 200 : -1;
#endif
}
}  // namespace

void startSaveResultsTask() {
    // Called synchronously on entry to grade while SML still binds this exact
    // session/index. Upload owns the snapshot even if the user advances at once.
    auto document = captureCompletedResult();
    if (!document) return;
    auto* parameter = document.release();
    if (xTaskCreatePinnedToCore(saveResultsTask, saveResultsTaskName,
            8 * configMINIMAL_STACK_SIZE, parameter, 1, &saveResultsTaskHandle, 1) != pdPASS) {
        std::unique_ptr<JsonDocument> retained(parameter);
        if (!enqueuePayload(*retained))
            ESP_LOGE(WIFI_TAG, "failed to queue result after task creation failure");
    }
}

void saveResultsTask(void* parameter) {
    {
        std::unique_ptr<JsonDocument> document(static_cast<JsonDocument*>(parameter));
        if (!document) document = captureCompletedResult(); // synchronous test callers
        if (document) persistAndUploadResult(*document);
    }
    vTaskDelete(nullptr);
}

#endif  // PROVISION (sessionFromJson through saveResultsTask)

void getIsPaired() {
#ifdef PROVISION
    dashboardState.isPaired = false;
    return;
#else
    // if not connected to wifi, return
    if (WiFiClass::status() != WL_CONNECTED) {
        dashboardState.isPaired = true;
        return;
    }
    // Nothing to check against yet; provisioning runs before pairing.
    if (trainerId.isEmpty()) {
        dashboardState.isPaired = false;
        return;
    }
    JsonDocument doc;
    doc["trainerId"] = trainerId;
    addPhysicalFlashSize(doc);
    String payload;
    int httpResponseCode = -1;
    for (int attempt = 0; attempt < 3; ++attempt) {
        httpResponseCode = postJson("/is-paired", doc, &payload);
        if (httpResponseCode == 200) {
            break;
        }
        vTaskDelay(500 / portTICK_PERIOD_MS);  // small delay before retry
    }
    if (httpResponseCode == 200) {
        ESP_LOGD(WIFI_TAG, "is paired");
        dashboardState.isPaired = true;
    } else {
        ESP_LOGD(WIFI_TAG, "not paired");
        dashboardState.isPaired = false;
    }
#endif  // PROVISION
}

#ifndef PROVISION
void sendCalibrationToBackend(float minCm, float maxCm) {
    // if not connected to wifi, return silently
    if (WiFiClass::status() != WL_CONNECTED) {
        ESP_LOGD(WIFI_TAG,
                 "Not connected to WiFi, skipping calibration upload");
        return;
    }

    // Prepare payload for calibrate-toy endpoint
    JsonDocument doc;
    doc["sessionId"] = session.id;
    doc["minCm"] = minCm;
    doc["maxCm"] = maxCm;

    String payload;
    int httpResponseCode = postJson("/calibrate-toy", doc, &payload);

#ifdef PIO_UNIT_TESTING
    calibrationHttpCode = httpResponseCode;
    calibrationUploaded = (httpResponseCode == 200);
#endif

    ESP_LOGD(WIFI_TAG, "calibration upload HTTP %d", httpResponseCode);
}
#endif  // PROVISION
