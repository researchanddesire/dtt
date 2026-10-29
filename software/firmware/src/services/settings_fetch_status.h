#pragma once

#include <ArduinoJson.h>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <initializer_list>

// Diagnostics contain only fixed categories and numeric telemetry. Never add
// session text, identifiers, addresses, credentials or response excerpts here.
struct DashboardResponseMetrics {
    int httpStatus = 0;
    size_t responseBytes = 0;
};

enum class SettingsFetchStage : uint8_t {
    Idle, Requesting, HttpFailed, Parsing, ParseFailed, ValidationFailed,
    PageMismatch, AwaitingInstall, Persisting, PersistenceFailed, Installing,
    StateRejected, Installed
};
enum class SettingsFetchError : uint8_t {
    None, Offline, Http, Transport, Parse, Validation, RequestPage, LivePage,
    Persistence, State
};
enum class SessionPersistenceError : uint8_t {
    None, Limit, Mount, Write, Rotate, Recover, Stage, Commit
};
enum class SettingsCacheSource : uint8_t { NotLoaded, Primary, Backup, Recovery };
enum class SettingsFetchView : uint8_t { Summary, Transport, Parse, Storage, Write, Memory };

struct SettingsWriteStatus {
    uint32_t expected = 0;
    uint32_t written = 0;
    uint32_t openReportedSize = 0;
    uint32_t reopenedSize = 0;
    uint32_t verifiedBytes = 0;
    uint32_t fsUsed = 0;
    uint32_t fsTotal = 0;
    bool opened = false;
    bool reopened = false;
    bool verified = false;
};

struct SettingsFetchStatus {
    uint32_t generation = 0;
    SettingsFetchStage stage = SettingsFetchStage::Idle;
    SettingsFetchError error = SettingsFetchError::None;
    SessionPersistenceError persistenceError = SessionPersistenceError::None;
    SettingsCacheSource cacheSource = SettingsCacheSource::NotLoaded;
    uint8_t attempt = 0;
    int httpStatus = 0;
    int clientStatus = 0;
    size_t responseBytes = 0;
    size_t retainedBodyBytes = 0;
    uint8_t parseCode = 255;  // Not parsed yet; ArduinoJson codes are 0..5.
    bool overflow = false;
    bool callbackInvoked = false;
    bool eventAccepted = false;
    bool persisted = false;
    bool installed = false;
    bool cacheMounted = false;
    uint32_t startedAtMs = 0;
    uint32_t updatedAtMs = 0;
    uint32_t freeHeap = 0;
    uint32_t largestBlock = 0;
    SettingsWriteStatus write;
};

inline const char *settingsFetchStageName(SettingsFetchStage stage) {
    switch (stage) {
        case SettingsFetchStage::Idle: return "idle";
        case SettingsFetchStage::Requesting: return "requesting";
        case SettingsFetchStage::HttpFailed: return "http_failed";
        case SettingsFetchStage::Parsing: return "parsing";
        case SettingsFetchStage::ParseFailed: return "parse_failed";
        case SettingsFetchStage::ValidationFailed: return "validation_failed";
        case SettingsFetchStage::PageMismatch: return "page_mismatch";
        case SettingsFetchStage::AwaitingInstall: return "awaiting_install";
        case SettingsFetchStage::Persisting: return "persisting";
        case SettingsFetchStage::PersistenceFailed: return "persistence_failed";
        case SettingsFetchStage::Installing: return "installing";
        case SettingsFetchStage::StateRejected: return "state_rejected";
        case SettingsFetchStage::Installed: return "installed";
    }
    return "unknown";
}
inline const char *settingsFetchErrorName(SettingsFetchError error) {
    switch (error) {
        case SettingsFetchError::None: return "none";
        case SettingsFetchError::Offline: return "offline";
        case SettingsFetchError::Http: return "http";
        case SettingsFetchError::Transport: return "transport";
        case SettingsFetchError::Parse: return "parse";
        case SettingsFetchError::Validation: return "validation";
        case SettingsFetchError::RequestPage: return "request_page";
        case SettingsFetchError::LivePage: return "live_page";
        case SettingsFetchError::Persistence: return "persistence";
        case SettingsFetchError::State: return "state";
    }
    return "unknown";
}
inline const char *sessionPersistenceErrorName(SessionPersistenceError error) {
    switch (error) {
        case SessionPersistenceError::None: return "none";
        case SessionPersistenceError::Limit: return "limit";
        case SessionPersistenceError::Mount: return "mount";
        case SessionPersistenceError::Write: return "write";
        case SessionPersistenceError::Rotate: return "rotate";
        case SessionPersistenceError::Recover: return "recover";
        case SessionPersistenceError::Stage: return "stage";
        case SessionPersistenceError::Commit: return "commit";
    }
    return "unknown";
}
inline const char *settingsCacheSourceName(SettingsCacheSource source) {
    switch (source) {
        case SettingsCacheSource::NotLoaded: return "not_loaded";
        case SettingsCacheSource::Primary: return "primary";
        case SettingsCacheSource::Backup: return "backup";
        case SettingsCacheSource::Recovery: return "recovery";
    }
    return "unknown";
}
inline const char *settingsFetchViewName(SettingsFetchView view) {
    switch (view) {
        case SettingsFetchView::Summary: return "summary";
        case SettingsFetchView::Transport: return "transport";
        case SettingsFetchView::Parse: return "parse";
        case SettingsFetchView::Storage: return "storage";
        case SettingsFetchView::Write: return "write";
        case SettingsFetchView::Memory: return "memory";
    }
    return "unknown";
}
inline bool parseSettingsFetchView(const char *name, SettingsFetchView &view) {
    for (const auto candidate : {SettingsFetchView::Summary, SettingsFetchView::Transport,
                                SettingsFetchView::Parse, SettingsFetchView::Storage,
                                SettingsFetchView::Write,
                                SettingsFetchView::Memory}) {
        if (name && std::strcmp(name, settingsFetchViewName(candidate)) == 0) {
            view = candidate;
            return true;
        }
    }
    return false;
}

// Each fixed view must fit RadBLE's complete reply envelope, not just this
// object. Do not add an unbounded "all" view or increase protocol limits.
inline void writeSettingsFetchStatus(
    JsonObject output, const SettingsFetchStatus &status,
    SettingsFetchView view = SettingsFetchView::Summary) {
    output["v"] = 2;
    output["view"] = settingsFetchViewName(view);
    output["generation"] = status.generation;
    output["stage"] = settingsFetchStageName(status.stage);
    if (view == SettingsFetchView::Summary) {
        output["error"] = settingsFetchErrorName(status.error);
        output["httpStatus"] = status.httpStatus;
        output["clientStatus"] = status.clientStatus;
        output["parseCode"] = status.parseCode;
        output["persistenceError"] = sessionPersistenceErrorName(status.persistenceError);
        output["cacheSource"] = settingsCacheSourceName(status.cacheSource);
    } else if (view == SettingsFetchView::Transport) {
        output["attempt"] = status.attempt;
        output["httpStatus"] = status.httpStatus;
        output["clientStatus"] = status.clientStatus;
        output["responseBytes"] = status.responseBytes;
        output["retainedBodyBytes"] = status.retainedBodyBytes;
    } else if (view == SettingsFetchView::Parse) {
        output["error"] = settingsFetchErrorName(status.error);
        output["parseCode"] = status.parseCode;
        output["overflow"] = status.overflow;
        output["callbackInvoked"] = status.callbackInvoked;
        output["eventAccepted"] = status.eventAccepted;
    } else if (view == SettingsFetchView::Storage) {
        output["persistenceError"] = sessionPersistenceErrorName(status.persistenceError);
        output["cacheSource"] = settingsCacheSourceName(status.cacheSource);
        output["cacheMounted"] = status.cacheMounted;
        output["callbackInvoked"] = status.callbackInvoked;
        output["eventAccepted"] = status.eventAccepted;
        output["persisted"] = status.persisted;
        output["installed"] = status.installed;
    } else if (view == SettingsFetchView::Write) {
        output["expected"] = status.write.expected;
        output["written"] = status.write.written;
        output["openReportedSize"] = status.write.openReportedSize;
        output["reopenedSize"] = status.write.reopenedSize;
        output["verifiedBytes"] = status.write.verifiedBytes;
        output["opened"] = status.write.opened;
        output["reopened"] = status.write.reopened;
        output["verified"] = status.write.verified;
    } else if (view == SettingsFetchView::Memory) {
        output["startedAtMs"] = status.startedAtMs;
        output["updatedAtMs"] = status.updatedAtMs;
        output["freeHeap"] = status.freeHeap;
        output["largestBlock"] = status.largestBlock;
        output["fsUsed"] = status.write.fsUsed;
        output["fsTotal"] = status.write.fsTotal;
    }
}
