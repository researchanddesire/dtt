#include "upload_queue.h"
#include "upload_queue_policy.h"
#include "json_file_verifier.h"

#include <SPIFFS.h>
#include <WiFi.h>

// clang-format off
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
// clang-format on

#include "wifiSettings.h"  // postJson

#define UPQ_TAG "UPQ"

namespace {

constexpr char kPrefix[] = "/q_";
constexpr char kSuffix[] = ".json";

// Max queued payloads. The device is a transient retry buffer, not an archive;
// when full we drop the OLDEST (newest data is most valuable, and the server
// dedups replays anyway).
constexpr int kMaxItems = 50;

// postJson allocates ~20 KB for the TLS client; require headroom before we
// attempt a flush so we never push the device into the OOM state we're fixing.
constexpr uint32_t kMinFreeHeapForFlush = 24000;

// Keep this much SPIFFS free so we can always persist the next result.
constexpr uint32_t kMinFreeBytes = 24 * 1024;

SemaphoreHandle_t queueMutex = nullptr;
// Protected by queueMutex; filesystem writers may run while HTTP is in flight.
bool flushInProgress = false;
uint32_t nextCounter = 0;

String makeFileName(uint32_t counter) {
    char buf[24];
    snprintf(buf, sizeof(buf), "%s%010u%s", kPrefix, counter, kSuffix);
    return String(buf);
}

// SPIFFS entry names differ across core versions (basename vs full path);
// normalize to a leading-slash path so prefix matching and remove() are stable.
String fullPath(const String &name) {
    return name.startsWith("/") ? name : "/" + name;
}

bool isQueueFile(const String &path) {
    return path.startsWith(kPrefix) && path.endsWith(kSuffix);
}

// Parse the counter out of "/q_0000000042.json". Returns false if not a match.
bool parseCounter(const String &path, uint32_t &out) {
    if (!isQueueFile(path)) return false;
    const int start = strlen(kPrefix);
    const int end = path.length() - strlen(kSuffix);
    if (end <= start) return false;
    out = strtoul(path.substring(start, end).c_str(), nullptr, 10);
    return true;
}

// Count queue files. (Caller holds the mutex, or accepts a best-effort count.)
int countQueueFiles() {
    int count = 0;
    File root = SPIFFS.open("/");
    if (!root) return 0;
    for (File f = root.openNextFile(); f; f = root.openNextFile()) {
        uint32_t c;
        if (parseCounter(fullPath(String(f.name())), c)) count++;
    }
    return count;
}

// Find the oldest (lowest-counter) queue file. Returns false if queue is empty.
bool findOldest(String &outPath) {
    bool found = false;
    uint32_t best = 0;
    File root = SPIFFS.open("/");
    if (!root) return false;
    for (File f = root.openNextFile(); f; f = root.openNextFile()) {
        const String path = fullPath(String(f.name()));
        uint32_t c;
        if (!parseCounter(path, c)) continue;
        if (!found || c < best) {
            best = c;
            outPath = path;
            found = true;
        }
    }
    return found;
}

// Evict oldest files until under the item cap and above the free-space floor.
// Logs every eviction (no silent data loss). Caller must hold the mutex.
void evictUntilRoom() {
    while (countQueueFiles() >= kMaxItems) {
        String oldest;
        if (!findOldest(oldest)) break;
        ESP_LOGW(UPQ_TAG, "queue full (%d) — evicting %s, SEGMENT DATA LOST",
                 kMaxItems, oldest.c_str());
        SPIFFS.remove(oldest);
    }
    while (SPIFFS.totalBytes() - SPIFFS.usedBytes() < kMinFreeBytes) {
        String oldest;
        if (!findOldest(oldest)) break;
        ESP_LOGW(UPQ_TAG, "low SPIFFS space — evicting %s, SEGMENT DATA LOST",
                 oldest.c_str());
        SPIFFS.remove(oldest);
    }
}

}  // namespace

void initUploadQueue() {
    if (queueMutex == nullptr) {
        queueMutex = xSemaphoreCreateMutex();
    }
    if (!SPIFFS.begin(true)) {
        ESP_LOGE(UPQ_TAG, "SPIFFS mount failed; upload queue unavailable");
        return;
    }

    // Seed the counter past the highest existing file so new files always sort
    // after old ones, even across reboots (no NVS write on the hot path).
    uint32_t next = 0;
    int count = 0;
    File root = SPIFFS.open("/");
    if (root) {
        for (File f = root.openNextFile(); f; f = root.openNextFile()) {
            uint32_t c;
            if (parseCounter(fullPath(String(f.name())), c)) {
                count++;
                if (c + 1 > next) next = c + 1;
            }
        }
    }
    nextCounter = next;
    ESP_LOGI(UPQ_TAG, "init: %d queued payload(s), nextCounter=%u", count,
             nextCounter);
}

bool enqueuePayload(const JsonDocument &doc) {
    if (queueMutex == nullptr) {
        ESP_LOGE(UPQ_TAG, "enqueue before init");
        return false;
    }
    const size_t expected = measureJson(doc);
    if (doc.overflowed() || expected == 0) {
        ESP_LOGE(UPQ_TAG, "invalid queue document");
        return false;
    }
    xSemaphoreTake(queueMutex, portMAX_DELAY);

    const String path = makeFileName(nextCounter);
    // Never truncate an existing committed result, even if the counter is stale.
    if (SPIFFS.exists(path)) {
        ESP_LOGE(UPQ_TAG, "queue filename conflict");
        xSemaphoreGive(queueMutex);
        return false;
    }
    // The suffix is deliberately not .json: interrupted/unverified staging
    // files must never be selected by the queue scanner or uploaded.
    const String staging = path + ".tmp";
    if (SPIFFS.exists(staging) && !SPIFFS.remove(staging)) {
        ESP_LOGE(UPQ_TAG, "could not discard old queue staging file");
        xSemaphoreGive(queueMutex);
        return false;
    }
    const auto discardStaging = [&]() {
        if (SPIFFS.exists(staging) && !SPIFFS.remove(staging))
            ESP_LOGE(UPQ_TAG, "could not discard uncommitted queue staging file");
    };

    evictUntilRoom();
    File file = SPIFFS.open(staging, "w");
    const bool opened = static_cast<bool>(file);
    const size_t written = opened ? serializeJson(doc, file) : 0;
    file.flush();
    file.close();
    bool complete = opened && written == expected;
    if (complete) {
        File reopened = SPIFFS.open(staging, "r");
        complete = reopened && reopened.size() == expected;
        if (complete) {
            JsonFileVerifier<File> verifier(reopened);
            complete = serializeJson(doc, verifier) == expected &&
                       verifier.complete(expected);
        }
        reopened.close();
    }
    if (!complete) {
        discardStaging();
        ESP_LOGE(UPQ_TAG, "queue staging write or readback failed");
        xSemaphoreGive(queueMutex);
        return false;
    }
    if (!SPIFFS.rename(staging, path)) {
        discardStaging();
        ESP_LOGE(UPQ_TAG, "could not commit verified queue result");
        xSemaphoreGive(queueMutex);
        return false;
    }
    ++nextCounter;
    ESP_LOGI(UPQ_TAG, "queued segment (%u bytes)", static_cast<unsigned>(written));
    xSemaphoreGive(queueMutex);
    return true;
}

int flushUploadQueue() {
    if (queueMutex == nullptr) return 0;

    // Cheap pre-checks before taking the lock or allocating anything.
    if (WiFi.status() != WL_CONNECTED) return 0;
    if (ESP.getFreeHeap() < kMinFreeHeapForFlush) {
        ESP_LOGD(UPQ_TAG, "skip flush: heap=%u too low",
                 (unsigned)ESP.getFreeHeap());
        return 0;
    }

    // Keep one flush in flight without holding the filesystem mutex over HTTP.
    // In particular, durable enqueue after a task-create failure may be called
    // under SML and must never wait behind a network operation.
    if (xSemaphoreTake(queueMutex, 0) != pdTRUE) return 0;
    if (flushInProgress) {
        xSemaphoreGive(queueMutex);
        return 0;
    }
    flushInProgress = true;

    int uploaded = 0;
    while (true) {
        // Heap can drop mid-flush; stop before we starve the device.
        if (ESP.getFreeHeap() < kMinFreeHeapForFlush) break;

        String path;
        if (!findOldest(path)) break;  // queue empty

        File file = SPIFFS.open(path, "r");
        if (!file || file.size() == 0) {
            ESP_LOGW(UPQ_TAG, "corrupt/empty queue file %s — dropping",
                     path.c_str());
            if (file) file.close();
            SPIFFS.remove(path);
            continue;
        }

        JsonDocument doc;
        const DeserializationError err = deserializeJson(doc, file);
        file.close();
        if (err) {
            ESP_LOGW(UPQ_TAG, "unparseable queue file %s (%s) — dropping",
                     path.c_str(), err.c_str());
            SPIFFS.remove(path);
            continue;
        }

        xSemaphoreGive(queueMutex);
        const int code = postJson("/training-completed", doc);
        xSemaphoreTake(queueMutex, portMAX_DELAY);
        // Enqueue may have evicted this unique filename during HTTP. Removing
        // an already absent entry is safe; a newer result uses a new counter.

        if (code == 200) {
            SPIFFS.remove(path);
            uploaded++;
            ESP_LOGI(UPQ_TAG, "flushed %s", path.c_str());
        } else if (uploadQueuePermanentRejection(code)) {
            // Validation-style rejections retain the existing disposal policy.
            // Never log a server body: it can contain personal session data.
            ESP_LOGE(UPQ_TAG,
                     "server rejected queued result (http=%d); dropping",
                     code);
            SPIFFS.remove(path);
        } else {
            // Auth/rate limits, 5xx, timeouts and connection failures keep this
            // rest; retry on the next flush / boot.
            ESP_LOGW(UPQ_TAG,
                     "transient upload failure for %s (http=%d) — will retry",
                     path.c_str(), code);
            break;
        }
    }

    flushInProgress = false;
    xSemaphoreGive(queueMutex);
    return uploaded;
}

int uploadQueueDepth() { return countQueueFiles(); }
