#include "radHil.h"

#if defined(RAD_HIL_VARIANT) && defined(ARDUINO)
#include <Arduino.h>
#include <NetworkRequestLock.h>
#include <WiFi.h>
#include <atomic>
#include <cstring>
#include <cstdio>
#include <cstdarg>
#include <cstdlib>
#include <esp_heap_caps.h>
#include <time.h>
#include <esp_crt_bundle.h>
#include <esp_http_client.h>
#include <esp_idf_version.h>
#include <esp_log.h>
#include <esp_ota_ops.h>
#include <esp_partition.h>
#include <esp_system.h>
#include <esp_timer.h>
#if DTT_ENABLE_RAD_BLE
// The BLE-enabled bench needs source-built TLS with bounded transient storage.
// Reject an SDK configuration that silently falls back to fixed record buffers.
#if !CONFIG_MBEDTLS_DYNAMIC_BUFFER || !CONFIG_MBEDTLS_DYNAMIC_FREE_PEER_CERT || \
    !CONFIG_MBEDTLS_CERTIFICATE_BUNDLE || !CONFIG_MBEDTLS_HAVE_TIME_DATE || \
    !CONFIG_MBEDTLS_KEY_EXCHANGE_PSK
#error "Staging V2 requires dynamic TLS buffers and certificate validation"
#endif
#if CONFIG_MBEDTLS_SSL_KEEP_PEER_CERTIFICATE || CONFIG_MBEDTLS_DYNAMIC_FREE_CONFIG_DATA
#error "Staging V2 must free peer certificates and retain reusable TLS configuration"
#endif
static_assert(CONFIG_MBEDTLS_SSL_IN_CONTENT_LEN == 16384 &&
              CONFIG_MBEDTLS_SSL_OUT_CONTENT_LEN == 4096,
              "Staging V2 must retain standard TLS record capacities");
#endif
#if __has_include("mqtt.h")
#include "mqtt.h"
#define RAD_HIL_LOCKBOX_MQTT
#endif
#if __has_include("CertificateDateClient.h")
#include "CertificateDateClient.h"
#include <HTTPClient.h>
#include <time.h>
#define RAD_HIL_CERTIFICATE_DATE_CLIENT
#ifndef RAD_HIL_ARDUINO_HTTP
#define RAD_HIL_ARDUINO_HTTP
#endif
#elif defined(RAD_HIL_ARDUINO_HTTP)
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>
#else
// Arduino 2 also ships a header with this name exposing only its wrapper.
// The IDF symbol is present in the pinned SDK's libmbedtls.a in both builds.
extern "C" esp_err_t esp_crt_bundle_attach(void *conf);
#endif
#if ESP_IDF_VERSION_MAJOR >= 5
#include <esp_mac.h>
#endif

namespace {
#if DTT_ENABLE_RAD_BLE
// Arduino's ROM logger and IDF task logger must share the UART write mutex
// with health records. Retain all ordinary and fault logs, without interleaving.
int serialLog(const char* format, va_list arguments) {
    char local[256];
    va_list copy;
    va_copy(copy, arguments);
    const int count = vsnprintf(local, sizeof(local), format, copy);
    va_end(copy);
    if (count < 0) return count;
    if (static_cast<size_t>(count) < sizeof(local)) {
        return Serial.write(reinterpret_cast<const uint8_t*>(local), count);
    }
    auto* expanded = static_cast<char*>(malloc(static_cast<size_t>(count) + 1));
    if (!expanded) {
        Serial.print("\nRAD_HEALTH log allocation failed\n");
        return -1;
    }
    vsnprintf(expanded, static_cast<size_t>(count) + 1, format, arguments);
    const int written = Serial.write(reinterpret_cast<const uint8_t*>(expanded), count);
    free(expanded);
    return written;
}
#endif

// One buffered serial write prevents concurrent task logs from splitting JSON.
// The initial newline separates a record from a partial ordinary log message.
void emitHealth(const char* format, ...) {
    char frame[768];
    frame[0] = '\n';
    va_list arguments;
    va_start(arguments, format);
    const int count = vsnprintf(frame + 1, sizeof(frame) - 1, format, arguments);
    va_end(arguments);
    if (count > 0 && static_cast<size_t>(count) < sizeof(frame) - 1) {
        if (Serial.write(reinterpret_cast<const uint8_t*>(frame), count + 1) !=
            static_cast<size_t>(count + 1)) {
            Serial.print("\nRAD_HEALTH incomplete serial write\n");
        }
    }
}
std::atomic<uint32_t> progressMs{0};
std::atomic<bool> ready{false};
std::atomic<bool> bleStarted{false};
std::atomic<uint32_t> disconnects{0};
uint32_t bootId = 0;
std::atomic<uint32_t> lastNetworkMs{0};
std::atomic<bool> internet{false};

unsigned long long uptimeMs() {
    return static_cast<unsigned long long>(esp_timer_get_time() / 1000);
}

unsigned unusedStack(const char* name) {
    // These services live for the entire boot; no transient/deleted task handles.
    const auto task = xTaskGetHandle(name);
    return task ? static_cast<unsigned>(uxTaskGetStackHighWaterMark(task)) : 0;
}

bool checkInternet() {
    // TLS certificate dates require a synchronized clock. Some products do
    // not initialize SNTP during ordinary idle startup, so the staging-only
    // observer requests it once and waits without weakening verification.
    static bool clockRequested = false;
    if (time(nullptr) < 1704067200) {
        if (!clockRequested) {
            configTime(0, 0, "time.cloudflare.com", "pool.ntp.org");
            clockRequested = true;
        }
        return false;
    }
    // A read-only request with full certificate/hostname validation. Never
    // follow a redirect to a different environment or send device credentials.
#if defined(RAD_HIL_ARDUINO_HTTP)
    // Reuse the Trainer's existing HTTP stack to retain its small OTA slot.
    extern const uint8_t bundleStart[] asm("_binary_x509_crt_bundle_start");
#if defined(RAD_HIL_CERTIFICATE_DATE_CLIENT)
    // Preserve the public Trainer's SDK certificate-date hardening.
    firmware::CertificateDateClient client;
#else
    WiFiClientSecure client;
#endif
    client.setCACertBundle(bundleStart);
    client.setHandshakeTimeout(5);
    HTTPClient http;
    http.setConnectTimeout(5000);
    http.setTimeout(5000);
    http.setReuse(false);
    http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
    if (!http.begin(client, "https://staging.researchanddesire.com/")) return false;
    const int status = http.sendRequest("HEAD");
    http.end();
    return status >= 200 && status < 400;
#else
    esp_http_client_config_t config = {};
    config.url = "https://staging.researchanddesire.com/";
    config.method = HTTP_METHOD_HEAD;
    config.transport_type = HTTP_TRANSPORT_OVER_SSL;
    config.timeout_ms = 5000;
    config.disable_auto_redirect = true;
    config.buffer_size = 512;
#if defined(FIRMWARE_USE_IDF_CRT_BUNDLE)
    config.crt_bundle_attach = esp_crt_bundle_attach;
#else
    config.crt_bundle_attach = arduino_esp_crt_bundle_attach;
#endif
    auto client = esp_http_client_init(&config);
    if (!client) return false;
    const auto result = esp_http_client_perform(client);
    const int status = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);
    return result == ESP_OK && status >= 200 && status < 400;
#endif
}

void networkTask(void*) {
    uint32_t previousProbe = 0;
    for (;;) {
        const uint32_t now = millis();
        const bool wifi = WiFi.status() == WL_CONNECTED;
        if (!wifi) internet = false;
        // Leave the application's boot preflight first use of TLS memory.
        if (wifi && ready.load(std::memory_order_relaxed) &&
            (previousProbe == 0 || now - previousProbe >= 30000)) {
            // Queue for the same TLS slot as application requests. Polling it
            // only at heartbeat boundaries can starve behind periodic traffic.
            // This worker may wait; the independent reporter keeps heartbeats
            // advancing and fails if network evidence ages past 60 seconds.
            NetworkRequestLock requestLock;
            if (requestLock) {
                previousProbe = millis();
                const bool reachable = WiFi.status() == WL_CONNECTED && checkInternet();
                if (reachable) lastNetworkMs.store(millis(), std::memory_order_relaxed);
                internet.store(reachable, std::memory_order_release);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(250));
    }
}

void observeTask(void*) {
    // Boot and an immediately scheduled reporter can share one millisecond.
    // Start at the normal cadence so the first heartbeat proves advancing time.
    vTaskDelay(pdMS_TO_TICKS(5000));
    for (;;) {
        const bool reachable = internet.load(std::memory_order_acquire);
        const auto lastNetwork = lastNetworkMs.load(std::memory_order_relaxed);
        const auto lastProgress = progressMs.load(std::memory_order_relaxed);
        // Read progress first: another core can advance it while we sample.
        // Taking the clock first could report a wrapped, enormous task age.
        const uint32_t sampled = millis();
        bool applicationReady = ready.load(std::memory_order_relaxed) && lastProgress != 0;
#if DTT_ENABLE_RAD_BLE
        applicationReady = applicationReady && bleStarted.load(std::memory_order_relaxed);
#endif
#if defined(RAD_HIL_LOCKBOX_MQTT)
        // Retain the original Lockbox gate's staging MQTT requirement.
        applicationReady = applicationReady && mqttConnected && mqtt_server != nullptr &&
            std::strcmp(mqtt_server, "mqtts://x15ff600.ala.us-east-1.emqxsl.com") == 0;
#endif
        emitHealth(
            "RAD_HEALTH {\"event\":\"heartbeat\",\"boot_id\":%lu,\"uptime_ms\":%llu,"
            "\"ready\":%s,\"app_age_ms\":%lu,\"wifi\":%s,\"bench_wifi\":%s,"
            "\"ip\":\"%s\",\"internet\":%s,\"network_age_ms\":%lu,\"disconnects\":%lu}\n",
            static_cast<unsigned long>(bootId), uptimeMs(),
            applicationReady ? "true" : "false",
            static_cast<unsigned long>(sampled-lastProgress),
            WiFi.status() == WL_CONNECTED ? "true" : "false",
            WiFi.SSID() == "IoT_PHB" ? "true" : "false", WiFi.localIP().toString().c_str(),
            reachable ? "true" : "false", static_cast<unsigned long>(sampled-lastNetwork),
            static_cast<unsigned long>(disconnects.load(std::memory_order_relaxed)));
        Serial.printf("\nRAD_DIAG observer_stack_free=%u heap=%u max_alloc=%u\n",
                      static_cast<unsigned>(uxTaskGetStackHighWaterMark(nullptr)),
                      ESP.getFreeHeap(), ESP.getMaxAllocHeap());
        Serial.printf("\nRAD_DIAG network_stack_free=%u\n", unusedStack("rad-hil-net"));
        Serial.printf("\nRAD_DIAG button_stack_free=%u header_stack_free=%u led_stack_free=%u state_stack_free=%u ble_stack_free=%u stack_unit=%u\n",
                      unusedStack("drawButtonTask"), unusedStack("drawBatteryTask"),
                      unusedStack("ledsTask"), unusedStack("stateMonitor"),
                      unusedStack("rad-ble-v1"), static_cast<unsigned>(configMINIMAL_STACK_SIZE));
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}
}  // namespace

#if DTT_ENABLE_RAD_BLE
// Only the source-built V2 SDK needs this bridge. V1's prebuilt SDK already
// exports an esp_diagnostics wrapper with this symbol and must retain it.
extern "C" int log_printfv(const char* format, va_list arguments);
extern "C" int __wrap_log_printf(const char* format, ...) {
    va_list arguments;
    va_start(arguments, format);
    const int written = bootId == 0 ? log_printfv(format, arguments)
                                    : serialLog(format, arguments);
    va_end(arguments);
    return written;
}
#endif

void radHilStart() {
    if (bootId != 0) return;
#if DTT_ENABLE_RAD_BLE
    esp_log_set_vprintf(serialLog);
#endif
    bootId = esp_random();
    if (bootId == 0) bootId = 1;
    uint8_t mac[6] = {};
    esp_efuse_mac_get_default(mac);
    char deviceId[13];
    snprintf(deviceId, sizeof(deviceId), "%02X%02X%02X%02X%02X%02X", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    uint8_t hash[32] = {};
    const auto partition = esp_ota_get_running_partition();
    if (!partition || esp_partition_get_sha256(partition, hash) != ESP_OK) {
        emitHealth( "RAD_HEALTH invalid running image\n");
        return;
    }
    char imageHash[65];
    for (size_t i = 0; i < sizeof(hash); ++i) snprintf(imageHash+i*2, 3, "%02x", hash[i]);
    emitHealth(
        "RAD_HEALTH {\"event\":\"boot\",\"schema\":1,\"boot_id\":%lu,\"uptime_ms\":%llu,"
        "\"product\":\"%s\",\"variant\":\"%s\",\"device_id\":\"%s\",\"flash_bytes\":%lu,"
        "\"build_sha\":\"%s\",\"image_sha256\":\"%s\",\"track\":\"%s\"}\n",
        static_cast<unsigned long>(bootId), uptimeMs(), RAD_HIL_PRODUCT, RAD_HIL_VARIANT,
        deviceId, static_cast<unsigned long>(ESP.getFlashChipSize()), FIRMWARE_BUILD_SHA, imageHash, FIRMWARE_TRACK);
    WiFi.onEvent([](WiFiEvent_t, WiFiEventInfo_t) {
        disconnects.fetch_add(1, std::memory_order_relaxed);
    }, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
    if (xTaskCreate(observeTask, "radHil", 5120, nullptr, 1, nullptr) != pdPASS) {
        emitHealth( "RAD_HEALTH observer task creation failed\n");
        return;
    }
    if (xTaskCreate(networkTask, "rad-hil-net", 6144, nullptr, 1, nullptr) != pdPASS) {
        emitHealth("RAD_HEALTH network task creation failed\n");
    }
}

void radHilProgress(bool idleAndReady) {
    ready.store(idleAndReady, std::memory_order_relaxed);
    progressMs.store(millis(), std::memory_order_relaxed);
}
void radHilBleStarted(bool succeeded) {
    bleStarted.store(succeeded, std::memory_order_relaxed);
    if (!succeeded) emitHealth("RAD_HEALTH BLE initialization failed\n");
}
#else
void radHilStart() {}
void radHilProgress(bool) {}
void radHilBleStarted(bool) {}
#endif
