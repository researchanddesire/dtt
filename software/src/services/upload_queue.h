#ifndef UPLOAD_QUEUE_H_
#define UPLOAD_QUEUE_H_

#include <Arduino.h>
#include <ArduinoJson.h>

// Durable upload queue (write-ahead log) for completed training segments.
//
// A completed segment's payload is persisted to SPIFFS the moment training
// finishes, BEFORE any network upload is attempted, so the data survives WiFi
// loss, low heap, crashes and reboots. Queued payloads are re-sent on
// boot/reconnect and after each completion, and deleted once the server
// confirms (HTTP 200) or permanently rejects them (validation-style HTTP 4xx).
// HTTP 401/403/408/429 are retained for retry after recovery. Server response
// bodies are never written to device logs.
//
// Re-sending is safe: /training-completed upserts on (sessionId, segmentId), so
// a replay of an already-stored segment is idempotent (no duplicates).
//
// Queue files are named "/q_<10-digit-counter>.json"; their content is exactly
// the POST body for /training-completed.

// Create the mutex and seed the filename counter from a boot scan of existing
// queue files. Idempotent; call once at startup (before initWifi()).
void initUploadQueue();

// Persist `doc` (a /training-completed payload) to a new queue file. Returns
// true if it was written to flash. Cheap — no TLS/HTTP heap needed; call this
// FIRST, before attempting any upload.
bool enqueuePayload(const JsonDocument &doc);

// Attempt to upload every queued payload (oldest first), deleting each on HTTP
// 200 or validation-style HTTP 4xx. Auth/rate-limit/timeouts stay queued.
// No-ops quietly when offline or when free heap is too low for
// TLS (the next boot, with fresh heap, is the recovery moment). Stops at the
// first transient failure (server/network down) and leaves the rest queued.
// Returns the number of items successfully uploaded this pass.
int flushUploadQueue();

// Number of payloads currently queued on flash (diagnostics / tests).
int uploadQueueDepth();

#endif  // UPLOAD_QUEUE_H_
