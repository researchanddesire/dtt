#pragma once

// Authentication/configuration changes, request timeouts and rate limits can
// recover later. A rejected request is not evidence that its result was stored.
inline bool uploadQueuePermanentRejection(int status) {
    return status >= 400 && status < 500 && status != 401 && status != 403 &&
           status != 408 && status != 429;
}
