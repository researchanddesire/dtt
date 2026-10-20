#include "wifiSettings.h"
#include <NetworkRequestLock.h>

#include <errno.h>
#include <memory>
#include <stdlib.h>

#include "SPIFFS.h"
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

SegmentBase *currentSegment = nullptr;

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

// Helper to POST JSON to Bubble server
int postJson(const String &endpoint, const JsonDocument &doc,
             String *responsePayload, const int timeoutMs) {
    NetworkRequestLock requestLock;
    String url = endpoint;
    if (!endpoint.startsWith("http")) {
        url = String(RAD_SERVER) + "/api/dtt/v2" + endpoint;
    }

    int memRetries = 0;

    // Wait for enough memory, up to 10 times
    while (ESP.getFreeHeap() < 20000 && memRetries < 10) {
        ESP_LOGD(WIFI_TAG, "not enough memory, retrying... (%d/10)",
                 memRetries + 1);
        memRetries++;
        vTaskDelay(1000 / portTICK_PERIOD_MS);
    }

    // HTTPClient retains a borrowed pointer even after some end()/begin()
    // paths. Declare its owner first so the transport outlives HTTP cleanup,
    // including early returns after a failed setup or request.
    std::unique_ptr<WiFiClient> currentClient;
    WiFiClientSecure *secureClient = nullptr;
    HTTPClient http;
    bool began = false;

    // Use appropriate client based on protocol
    if (url.startsWith("https://")) {
        secureClient = new WiFiClientSecure();
        secureClient->setInsecure();
        currentClient.reset(secureClient);
        http.setTimeout(timeoutMs);
        http.setConnectTimeout(timeoutMs);
        began = http.begin(*secureClient, url);
    } else {
        currentClient.reset(new WiFiClient());
        http.setTimeout(timeoutMs);
        http.setConnectTimeout(timeoutMs);
        began = http.begin(*currentClient, url);
    }

    auto logNetworkState = []() {
        ESP_LOGE(
            WIFI_TAG,
            "network status=%d ip=%s gateway=%s dns=%s rssi=%d "
            "heap=%u max_alloc=%u min_heap=%u",
            static_cast<int>(WiFi.status()), WiFi.localIP().toString().c_str(),
            WiFi.gatewayIP().toString().c_str(),
            WiFi.dnsIP().toString().c_str(), WiFi.RSSI(), ESP.getFreeHeap(),
            ESP.getMaxAllocHeap(), ESP.getMinFreeHeap());
    };

    if (!began) {
        ESP_LOGE(WIFI_TAG, "HTTP setup failed for %s", url.c_str());
        logNetworkState();
        currentClient->stop();
        return HTTPC_ERROR_CONNECTION_REFUSED;
    }
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

    if (url.indexOf("ngrok") != -1) {
        http.addHeader("ngrok-skip-browser-warning", "true");
    }

    String requestBody;
    serializeJson(doc, requestBody);

    ESP_LOGD(WIFI_TAG, "POSTing to %s", url.c_str());
    ESP_LOGD(WIFI_TAG, "with body %s", requestBody.c_str());
    int httpResponseCode = -1;

#if defined(RAD_HIL_VARIANT)
    Serial.printf("\nRAD_DIAG tls_begin_heap=%u max_alloc=%u\n",
                  ESP.getFreeHeap(), ESP.getMaxAllocHeap());
#endif
    httpResponseCode = http.POST(requestBody);

    if (httpResponseCode < 0) {
        const String transportError =
            HTTPClient::errorToString(httpResponseCode);
        ESP_LOGE(WIFI_TAG, "POST %s failed: %d (%s)", url.c_str(),
                 httpResponseCode, transportError.c_str());
        logNetworkState();

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

    if (responsePayload) {
        *responsePayload = http.getString();
    } else {
        http.getString();  // discard
    }
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

void notifyTrainingTask(void *pvParameters) {
    // Fire-and-forget: if WiFi isn't up, silently drop. Do NOT emit
    // done{}/fail{} events — this task runs as a side effect of the
    // init.idle -> init.preflight transition and the state machine does
    // not expect or handle response events on that edge.
    if (WiFiClass::status() != WL_CONNECTED) {
        ESP_LOGD(WIFI_TAG, "no wifi, skipping notifyTrainingTask");
        vTaskDelete(nullptr);
        return;
    }

    JsonDocument doc;
    doc["trainerId"] = trainerId;

    String payload;
    int httpResponseCode = postJson("/training-started", doc, &payload);
    ESP_LOGD(WIFI_TAG, "training-started HTTP %d: %s", httpResponseCode,
             payload.c_str());

#ifdef PIO_UNIT_TESTING
    // Test observability hooks (see wifiSettings.h). Order matters:
    // write the code before flipping the bool so a racing test reader
    // never sees notified=true with a stale code.
    trainingStartedHttpCode = httpResponseCode;
    trainingStartedNotified = (httpResponseCode == 200);
#endif

    vTaskDelete(nullptr);
}
#endif  // PROVISION

#ifdef PROVISION
String provisionError = "";

void provisionTask(void *pvParameters) {
    vTaskDelay(5000 / portTICK_PERIOD_MS);

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
    ESP_LOGD(WIFI_TAG, "HTTP %d: %s", httpResponseCode, payload.c_str());

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

    saveToEEPROM(String(trainerIdFromJson), serialNumberFromJson);
    // Force the update step to resolve once using the newly provisioned
    // trainer ID.
    invalidateFirmwareUpdateDecision();
    return true;
}
#endif  // PROVISION

#ifndef PROVISION
void sessionFromJson(JsonDocument sessionJson) {
    ESP_LOGD(WIFI_TAG, "=== Parsing session from JSON ===");

    // the session id is set on device boot.
    session.id = session.id;
    session.settingsId = sessionJson["settingsId"].as<String>();
    session.name = sessionJson["name"].as<String>();
    session.tagline = sessionJson["tagline"] | "";

    ESP_LOGD(WIFI_TAG, "Session ID: %s", session.id.c_str());
    ESP_LOGD(WIFI_TAG, "Session name: %s", session.name.c_str());
    ESP_LOGD(WIFI_TAG, "Session tagline: %s", session.tagline.c_str());

    if (sessionJson["iconSetId"].isNull() ||
        !sessionJson["iconSetId"].is<String>()) {
        session.iconId.reset();
        ESP_LOGD(WIFI_TAG, "iconSetId: null or not a string, reset");
    } else {
        const String iconSetIdStr = sessionJson["iconSetId"].as<String>();
        ESP_LOGD(WIFI_TAG, "iconSetId raw string: %s", iconSetIdStr.c_str());
        errno = 0;
        char *endPtr = nullptr;
        const long parsedIconId = strtol(iconSetIdStr.c_str(), &endPtr, 10);
        if (endPtr != iconSetIdStr.c_str() && errno == 0) {
            session.iconId = static_cast<int>(parsedIconId);
            ESP_LOGD(WIFI_TAG, "iconSetId parsed: %d", session.iconId.value());
        } else {
            session.iconId.reset();
            ESP_LOGD(WIFI_TAG, "iconSetId parse failed, reset");
        }
    }

    session.description = sessionJson["description"].as<String>();
    session.finalText = sessionJson["finalText"].as<String>();

    ESP_LOGD(WIFI_TAG, "Description: %s", session.description.c_str());
    ESP_LOGD(WIFI_TAG, "Final text: %s", session.finalText.c_str());

    // Parse finalColor if present (LED color for final page)
    if (sessionJson["finalColor"].is<int>()) {
        session.finalColor = sessionJson["finalColor"].as<int>();
        ESP_LOGD(WIFI_TAG, "Final color: 0x%06X", session.finalColor.value());
    } else {
        session.finalColor.reset();
        ESP_LOGD(WIFI_TAG, "Final color: not set");
    }

    // Parse icon configuration if present
    if (sessionJson["icon"].is<JsonObject>()) {
        JsonObject iconJson = sessionJson["icon"];
        session.icon.set = iconJson["set"].as<String>();
        session.icon.set_id = iconJson["set_id"].as<int>();
        ESP_LOGD(WIFI_TAG, "Icon config: set=%s, set_id=%d",
                 session.icon.set.c_str(), session.icon.set_id);
    } else {
        // Use default values if not provided
        session.icon = defaultIconConfig;
        ESP_LOGD(WIFI_TAG, "Using default icon config");
    }

    if (sessionJson["toy"].is<JsonObject>()) {
        JsonObject toyJson = sessionJson["toy"];
        ESP_LOGD(WIFI_TAG, "--- Parsing toy object ---");
        ToyCalibration calibration;

        // Parse calibration data if present
        if (toyJson["calibration"].is<JsonObject>()) {
            JsonObject calibrationJson = toyJson["calibration"];
            calibration.isCalibrated =
                calibrationJson["isCalibrated"].as<bool>();
            calibration.minCm = calibrationJson["minCm"].as<float>();
            calibration.maxCm = calibrationJson["maxCm"].as<float>();
            calibration.calibratedAt =
                calibrationJson["calibratedAt"].as<String>();
            ESP_LOGD(WIFI_TAG,
                     "Toy calibration: isCalibrated=%d, minCm=%.2f, "
                     "maxCm=%.2f, calibratedAt=%s",
                     calibration.isCalibrated, calibration.minCm,
                     calibration.maxCm, calibration.calibratedAt.c_str());
        } else {
            ESP_LOGD(WIFI_TAG, "Toy calibration: not present");
        }

        // Keep description for safety, in case of older payloads
        String toyTagline = EMPTY_STRING;
        if (toyJson["tagline"].is<String>()) {
            toyTagline = toyJson["tagline"].as<String>();
            ESP_LOGD(WIFI_TAG, "Toy tagline from 'tagline': %s",
                     toyTagline.c_str());
        } else if (toyJson["description"].is<String>()) {
            toyTagline = toyJson["description"].as<String>();
            ESP_LOGD(WIFI_TAG, "Toy tagline from 'description': %s",
                     toyTagline.c_str());
        }

        session.toy = Toy{
            .id = toyJson["id"].as<String>(),
            .name = toyJson["name"].as<String>(),
            .tagline = toyTagline,
            .calibration = calibration,
        };
        ESP_LOGD(WIFI_TAG, "Toy: id=%s, name=%s", session.toy->id.c_str(),
                 session.toy->name.c_str());
    } else {
        session.toy = std::nullopt;
        ESP_LOGD(WIFI_TAG, "No toy object in session");
    }

    session.segmentCount = sessionJson["segmentCount"].as<uint16_t>();
    session.pageIdx = sessionJson["pageIdx"].as<uint16_t>();
    session.durationMinutes = sessionJson["durationMinutes"].as<uint16_t>();
    session.handsFreeMode = sessionJson["handsFreeMode"] | false;

    ESP_LOGD(WIFI_TAG, "Session segmentCount: %d", session.segmentCount);
    ESP_LOGD(WIFI_TAG, "Session pageIdx: %d", session.pageIdx);
    ESP_LOGD(WIFI_TAG, "Session durationMinutes: %d", session.durationMinutes);
    ESP_LOGD(WIFI_TAG, "Session handsFreeMode: %d", session.handsFreeMode);

    const auto segments = sessionJson["segments"].as<JsonArray>();
    auto type = TrainingType::REPETITION;
    ESP_LOGD(WIFI_TAG, "--- Parsing %d segments ---", segments.size());
    session.segments.clear();

    int segmentIdx = 0;
    for (const auto &i : segments) {
        JsonObject segment = i;

        auto typeString = segment["type"].as<String>();
        typeString.toLowerCase();

        ESP_LOGD(WIFI_TAG, "Segment[%d]: type string=%s", segmentIdx,
                 typeString.c_str());

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
            ESP_LOGD(WIFI_TAG, "Segment[%d] passFail: enabled=%d, threshold=%d",
                     segmentIdx, passFailConfig.enabled,
                     passFailConfig.threshold);
        }

        auto segmentId = segment["id"].as<String>();
        auto segmentName = segment["name"].as<String>();
        auto segmentDifficulty = segment["difficulty"].as<String>();
        auto target = segment["params"]["target"].as<int>();
        auto startPos = segment["params"]["startPosition"].as<float>();
        auto endPos = segment["params"]["endPosition"].as<float>();
        auto depthIncrease =
            segment["params"]["trainingDepthIncrease"].as<int>();
        auto speed = segment["params"]["trainingSpeed"].as<float>();
        auto targetWindow = segment["params"]["targetWindow"].as<float>();

        ESP_LOGD(WIFI_TAG, "Segment[%d]: id=%s, name=%s, difficulty=%s",
                 segmentIdx, segmentId.c_str(), segmentName.c_str(),
                 segmentDifficulty.c_str());
        ESP_LOGD(WIFI_TAG,
                 "Segment[%d] params: target=%d, startPos=%.2f, endPos=%.2f",
                 segmentIdx, target, startPos, endPos);
        ESP_LOGD(WIFI_TAG,
                 "Segment[%d] params: depthIncrease=%d, speed=%.2f, "
                 "targetWindow=%.2f",
                 segmentIdx, depthIncrease, speed, targetWindow);

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
        segmentIdx++;
    }

    ESP_LOGD(WIFI_TAG, "Parsed %d segments total", session.segments.size());

    // If toy is calibrated on backend, override segment positions
    // Backend: minCm = lower value (endPosition), maxCm = higher value
    // (startPosition)
    if (session.toy.has_value() && session.toy->calibration.isCalibrated) {
        ESP_LOGD(WIFI_TAG, "--- Applying backend calibration override ---");
        ESP_LOGD(WIFI_TAG, "Backend calibration: minCm=%.2f, maxCm=%.2f",
                 session.toy->calibration.minCm,
                 session.toy->calibration.maxCm);

        for (auto &segment : session.segments) {
            ESP_LOGD(WIFI_TAG,
                     "Overriding segment '%s': startPos %.2f->%.2f, "
                     "endPos %.2f->%.2f",
                     segment.name.c_str(), segment.params.startPosition,
                     session.toy->calibration.maxCm, segment.params.endPosition,
                     session.toy->calibration.minCm);
            segment.params.startPosition =
                session.toy->calibration.maxCm;  // maxCm is the higher value
            segment.params.endPosition =
                session.toy->calibration.minCm;  // minCm is the lower value
        }

        // Mark session as calibrated
        session.isCalibrated = true;
        session.calibratedMinPosition = session.toy->calibration.maxCm;
        session.calibratedMaxPosition = session.toy->calibration.minCm;
        ESP_LOGD(WIFI_TAG,
                 "Session marked calibrated: minPos=%.2f, maxPos=%.2f",
                 session.calibratedMinPosition, session.calibratedMaxPosition);
    } else {
        ESP_LOGD(WIFI_TAG,
                 "No backend calibration to apply (toy=%s, "
                 "calibrated=%d)",
                 session.toy.has_value() ? "present" : "absent",
                 session.toy.has_value() ? session.toy->calibration.isCalibrated
                                         : 0);
    }

    ESP_LOGD(WIFI_TAG, "=== Session parsing complete ===");
};

namespace {
bool validateSessionDocument(JsonObjectConst root, String &error) {
    if (root.isNull() || !root["name"].is<String>() ||
        !root["segments"].is<JsonArrayConst>()) {
        error = "Session name and segments are required";
        return false;
    }
    const String name = root["name"].as<String>();
    const JsonArrayConst segments = root["segments"].as<JsonArrayConst>();
    if (name.isEmpty() || name.length() > 80 || segments.size() == 0 ||
        segments.size() > 8) {
        error = "Session must have a name and 1..8 segments";
        return false;
    }
    if (!root["segmentCount"].isNull() &&
        root["segmentCount"].as<size_t>() != segments.size()) {
        error = "segmentCount must match the complete segment array";
        return false;
    }
    for (JsonObjectConst segment : segments) {
        const String type = segment["type"] | "";
        const JsonObjectConst params = segment["params"].as<JsonObjectConst>();
        const bool knownType =
            type.equalsIgnoreCase(REPETITION_STRING) ||
            type.equalsIgnoreCase(ENDURANCE_STRING) ||
            type.equalsIgnoreCase(FREEFORM_STRING) ||
            type.equalsIgnoreCase(BOUNCE_STRING);
        if (!knownType || params.isNull() ||
            !params["target"].is<int>() ||
            !params["startPosition"].is<float>() ||
            !params["endPosition"].is<float>() ||
            !params["trainingDepthIncrease"].is<int>() ||
            !params["trainingSpeed"].is<float>() ||
            !params["targetWindow"].is<float>()) {
            error = "Each segment needs a known type and numeric parameters";
            return false;
        }
        const int target = params["target"].as<int>();
        const float start = params["startPosition"].as<float>();
        const float end = params["endPosition"].as<float>();
        const int depth = params["trainingDepthIncrease"].as<int>();
        const float speed = params["trainingSpeed"].as<float>();
        const float window = params["targetWindow"].as<float>();
        if (target <= 0 || target > 10000 || start <= end || start > 100.0f ||
            end < 0.0f || depth < 0 || depth > 100 || speed <= 0.0f ||
            speed > 1000.0f || window <= 0.0f || window > 100.0f) {
            error = "Segment parameters are outside safe training ranges";
            return false;
        }
        if (segment["passFail"].is<JsonObjectConst>()) {
            const int threshold = segment["passFail"]["threshold"] | 0;
            if (threshold < 0 || threshold > 100) {
                error = "Pass/fail threshold must be 0..100";
                return false;
            }
        }
    }
    return true;
}
}  // namespace

bool applySessionDocument(JsonDocument sessionJson, String &error) {
    if (!validateSessionDocument(sessionJson.as<JsonObjectConst>(), error))
        return false;
    sessionJson["segmentCount"] = sessionJson["segments"].size();
    sessionJson["segmentIdx"] = 0;
    sessionJson["pageIdx"] = 0;

    if (!SPIFFS.begin(true)) {
        error = "Could not mount session storage";
        return false;
    }
    constexpr char TEMP_FILE[] = "/session.ble.tmp";
    constexpr char BACKUP_FILE[] = "/session.ble.bak";
    SPIFFS.remove(TEMP_FILE);
    File temporary = SPIFFS.open(TEMP_FILE, "w");
    if (!temporary || serializeJson(sessionJson, temporary) == 0) {
        temporary.close();
        SPIFFS.remove(TEMP_FILE);
        error = "Could not persist the replacement session";
        return false;
    }
    temporary.close();

    SPIFFS.remove(BACKUP_FILE);
    const bool hadPrevious = SPIFFS.exists(SESSION_FILE);
    if (hadPrevious && !SPIFFS.rename(SESSION_FILE, BACKUP_FILE)) {
        SPIFFS.remove(TEMP_FILE);
        error = "Could not stage the existing session";
        return false;
    }
    if (!SPIFFS.rename(TEMP_FILE, SESSION_FILE)) {
        if (hadPrevious) SPIFFS.rename(BACKUP_FILE, SESSION_FILE);
        SPIFFS.remove(TEMP_FILE);
        error = "Could not commit the replacement session";
        return false;
    }

    // The adapter only permits replacement while no segment is active.  Use
    // the same parser as the boot-time loader so the in-memory and persisted
    // representations stay identical.
    sessionFromJson(sessionJson);
    session.segmentIdx = 0;
    session.pageIdx = 0;
    session.segmentFailureCounts.clear();
    SPIFFS.remove(BACKUP_FILE);
    return true;
}

void loadSessionTask(void *pvParameters) {
    if (!SPIFFS.begin(true)) {
        ESP_LOGD(WIFI_TAG, "failed to mount SPIFFS, setting to default");
        session = Session{};
        stateMachine->process_event(done{});
        vTaskDelete(nullptr);
        return;
    }

    File file = SPIFFS.open(SESSION_FILE, "r");
    if (SPIFFS.exists(SESSION_FILE) && file && file.size() != 0) {
        JsonDocument sessionJson;
        ESP_LOGD(WIFI_TAG, "loaded session from spiffs");
        deserializeJson(sessionJson, file);
        file.close();

        sessionFromJson(sessionJson);

    } else {
        ESP_LOGD(WIFI_TAG, "no session file found, setting to default");
        // just set it to the default session
        session = Session{};
    }

    stateMachine->process_event(done{});
    vTaskDelete(nullptr);
}

void fetchSettingsTask(void *pvParameters) {
    JsonDocument sessionJson;

    // if not connected to wifi, return
    if (WiFiClass::status() != WL_CONNECTED) {
        // if no wifi, try to load from remote
        ESP_LOGD(WIFI_TAG, "no wifi, trying to load from remote");
        stateMachine->process_event(fail{});
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
        httpResponseCode = postJson("/get-settings", doc, &payload);
        ESP_LOGD(WIFI_TAG, "HTTP Response code (attempt %d): %d", attempt + 1,
                 httpResponseCode);
        if (httpResponseCode == 200) {
            break;
        }
        vTaskDelay(5000 / portTICK_PERIOD_MS);
    }

    ESP_LOGD(WIFI_TAG, "HTTP Response payload: %s", payload.c_str());

    if (httpResponseCode != 200) {
        // Diagnostic for support: distinguishes "dashboard errored while online"
        // (http>0, wifi=1, health=1) from "truly offline" (wifi=0).
        ESP_LOGW(WIFI_TAG,
                 "get-settings failed: http=%d wifi=%d health=%d -> using "
                 "cached session",
                 httpResponseCode, WiFiClass::status() == WL_CONNECTED,
                 healthCheckPassed);
        stateMachine->process_event(fail{});
        vTaskDelete(nullptr);
        return;
    }

    deserializeJson(sessionJson, payload);
    sessionFromJson(sessionJson);

    // Save file to spiffs
    File file = SPIFFS.open(SESSION_FILE, "w");
    serializeJson(sessionJson, file);
    file.close();

    stateMachine->process_event(done{});

    // We're confirmed online (get-settings just returned 200) — opportunistically
    // drain any training results queued from an earlier offline/low-heap moment.
    flushUploadQueue();

    ESP_LOGD(WIFI_TAG, "settings fetched, got %d / %d segments with pageIdx %d",
             session.segments.size(), session.segmentCount, session.pageIdx);
    vTaskDelete(nullptr);
}

void saveResultsTask(void *pvParameters) {
    // Build the payload while currentSegment is still alive, then persist it to
    // flash BEFORE attempting any upload. Persisting is cheap (no TLS heap) and
    // survives WiFi loss, low heap, crashes and reboots — the result is never
    // dropped. flushUploadQueue() retries it now and on every boot/reconnect.
    auto toyId = session.toy.has_value() ? session.toy->id : "";
    auto settingsId = session.settingsId;

    // Calculate passed status for pass/fail feature
    const Segment *segment = getSegmentByIdx(session.segmentIdx);
    int passedStatus = -1;  // Default to null (-1)

    if (segment != nullptr && segment->passFail.enabled) {
        int grade = currentSegment->grade();
        bool passed = (grade >= segment->passFail.threshold);
        passedStatus = passed ? 1 : 0;  // 1=true, 0=false
        ESP_LOGD(WIFI_TAG,
                 "Pass/fail enabled: grade=%d, threshold=%d, passed=%d", grade,
                 segment->passFail.threshold, passedStatus);
    }

    JsonDocument doc =
        currentSegment->createPayload(trainerId, session.id, session.segmentIdx,
                                      session.settingsId, toyId, passedStatus);

    // Persist first — this is the durability guarantee.
    if (!enqueuePayload(doc)) {
        ESP_LOGE(WIFI_TAG, "failed to persist segment result to upload queue");
    }

    // Best-effort send now; no-ops if offline or low on heap. Anything left
    // queued is recovered on the next boot/reconnect (fresh heap).
    const int uploaded = flushUploadQueue();
    if (uploaded == 0) {
        ESP_LOGW(WIFI_TAG,
                 "result queued but not uploaded yet (offline / low heap / "
                 "server error) — will retry on reconnect/boot");
    }

#ifdef PIO_UNIT_TESTING
    resultsUploaded = (uploaded > 0);
    resultsHttpCode = (uploaded > 0) ? 200 : -1;
#endif

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

    if (httpResponseCode == 200) {
        ESP_LOGD(
            WIFI_TAG,
            "Calibration sent to backend successfully: minCm=%.2f, maxCm=%.2f",
            minCm, maxCm);
        ESP_LOGD(WIFI_TAG, "Response: %s", payload.c_str());
    } else {
        ESP_LOGD(WIFI_TAG,
                 "Failed to send calibration to backend. HTTP code: %d, "
                 "response: %s",
                 httpResponseCode, payload.c_str());
    }
}
#endif  // PROVISION
