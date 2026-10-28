#include "rad_ble.h"

#if DTT_ENABLE_RAD_BLE

#include <Preferences.h>
#include <WiFi.h>
#include <esp_ota_ops.h>

#include "FirmwareProvenance.h"
#include "FirmwareProvenanceResponse.h"
#include "constants/Version.h"
#include "input.h"
#include "services/board.hpp"
#include "services/leds.h"
#include "services/wifi_service.h"
#include "state/events.hpp"
#include "state/state.h"
#include "utils/update.hpp"
#include "wifiSettings.h"

#ifndef PROVISION
#include "services/vibrator.h"
#endif

#ifndef FIRMWARE_BUILD_SHA
#define FIRMWARE_BUILD_SHA "unknown"
#endif

namespace {

constexpr uint16_t R = radble::RESOURCE_READABLE |
                       radble::RESOURCE_AVAILABLE;
constexpr uint16_t RW = R | radble::RESOURCE_WRITABLE |
                        radble::RESOURCE_LEASE_REQUIRED;
constexpr uint16_t RWS = RW | radble::RESOURCE_SAFETY_CRITICAL;
constexpr uint16_t RS = R | radble::RESOURCE_STREAMABLE;
constexpr uint16_t RP = R | radble::RESOURCE_PERSISTENT;
constexpr uint16_t RWP = RW | radble::RESOURCE_PERSISTENT;

const radble::Resource RESOURCES[] = {
    {"essential", "essential.live", "essential", "object", "", RS,
     "{\"characteristic\":\"2010\",\"changeDriven\":true,\"maxRateHz\":4}"},
    {"device_name", "device.name", "setting", "string", "", RWP,
     "{\"maxBytes\":24,\"emptyResets\":true}"},
    {"firmware_provenance", "device.firmwareProvenance", "setting", "object",
     "", R, ""},
    {"main", "button.main", "button", "bool", "", RS,
     "{\"events\":[\"click\",\"double\",\"long\",\"multiple\"]}"},
    {"distance", "analog.distance", "analog", "float", "cm", RS,
     "{\"min\":0}"},
    {"distance_voltage", "analog.distanceVoltage", "analog", "float", "V",
     RS, ""},
    {"distance_raw", "analog.distanceRaw", "analog", "int", "raw", RS, ""},
    {"battery_raw", "analog.batteryRaw", "analog", "int", "raw", RS, ""},
    {"battery", "power.batteryVoltage", "power", "float", "V", RS, ""},
    {"battery_percent", "power.batteryPercent", "power", "int", "percent", RS,
     "{\"min\":0,\"max\":100}"},
    {"charging", "power.charging", "power", "bool", "", RS, ""},
    {"health", "connectivity.health", "connectivity", "bool", "", R, ""},
    {"voltage_slope", "setting.voltageCalibrationInverseSlope", "setting",
     "float", "adc/V", RWP, "{\"min\":100,\"max\":2000}"},
    {"voltage_offset", "setting.voltageCalibrationOffset", "setting",
     "float", "V", RWP, "{\"min\":-1,\"max\":1}"},
#ifndef PROVISION
    {"settings_fetch", "connectivity.settings", "connectivity", "object", "", R,
     "{\"diagnosticOnly\":true,\"schema\":2}"},
    {"position", "motion.position", "motion", "float", "cm", RS, ""},
    {"speed", "motion.speed", "motion", "float", "cm/s", RS, ""},
    {"rpm", "motion.rpm", "motion", "float", "rpm", RS, ""},
    {"position_state", "motion.positionState", "motion", "int", "enum", RS,
     ""},
    {"training_state", "motion.trainingState", "motion", "int", "enum", RS,
     ""},
    {"strokes", "motion.strokeCount", "motion", "int", "strokes", RS,
     ""},
    {"progress", "motion.progress", "motion", "float", "ratio", RS,
     "{\"min\":0,\"max\":1}"},
    {"grade", "motion.grade", "motion", "int", "percent", RS,
     "{\"min\":0,\"max\":100}"},
    {"distance_trained", "motion.distance", "motion", "float", "cm", RS,
     ""},
    {"current_value", "motion.currentValue", "motion", "int", "", RS,
     ""},
    {"target_value", "motion.target", "motion", "int", "", RS, ""},
    {"window_time", "motion.windowTime", "motion", "object", "ms", RS,
     ""},
    {"streak", "motion.streak", "motion", "object", "strokes", RS, ""},
    {"session", "session.current", "setting", "object", "", R, ""},
    {"hands_free", "session.handsFree", "setting", "bool", "", RW, ""},
    {"session_name", "session.name", "setting", "string", "", R, ""},
    {"session_segment", "session.segmentIndex", "setting", "int", "index", R,
     ""},
    {"calibration_min", "session.calibrationMin", "setting", "float", "cm", R,
     ""},
    {"calibration_max", "session.calibrationMax", "setting", "float", "cm", R,
     ""},
    {"session_apply", "session.definition", "setting", "object", "", RWP,
     "{\"operation\":\"session.apply\",\"maxSegmentsPerRequest\":8}"},
#endif
    {"trainer_id", "device.trainerId", "setting", "string", "",
     RP,
     ""},
    {"trainer_short_id", "device.trainerShortId", "setting", "string", "", RP,
     ""},
    {"serial_number", "device.serialNumber", "setting", "int", "", RP, ""},
#ifdef PROVISION
    {"factory_identity", "factory.identity", "setting", "object", "",
     RWS | radble::RESOURCE_PERSISTENT,
     "{\"operation\":\"factory.identity.write\"}"},
#endif
    {"update_channel", "device.alphaChannel", "setting", "bool", "", RWP,
     ""},
    {"led", "indicator.status", "indicator", "object", "hsv", RW, ""},
#ifndef PROVISION
    {"reward", "haptic.reward", "haptic", "int", "percent", RWS,
     "{\"min\":0,\"max\":100,\"maxDurationMs\":2000}"},
    {"punishment", "haptic.punishment", "haptic", "bool", "", RWS,
     "{\"maxDurationMs\":250}"},
    {"recalibrate", "target.recalibrate", "target", "event", "", RW, ""},
    {"restart", "target.restartTraining", "target", "event", "", RW, ""},
    {"preflight", "target.preflight", "target", "event", "", RW, ""},
    {"pairing", "target.pairing", "target", "event", "", RW, ""},
    {"wifi_setup", "target.wifi", "target", "event", "", RW, ""},
    {"target_calibration_min", "target.calibrationMin", "target", "event", "", RW,
     ""},
    {"target_calibration_max", "target.calibrationMax", "target", "event", "", RW,
     ""},
    {"session_details", "target.sessionDetails", "target", "event", "", RW,
     ""},
    {"play", "target.play", "target", "event", "", RW, ""},
#ifdef BYPASS_PLAY
    {"target_grade", "target.grade", "target", "event", "", RW, ""},
#endif
    {"retry", "target.retry", "target", "event", "", RW, ""},
    {"final", "target.final", "target", "event", "", RW, ""},
#endif
    {"update", "target.update", "target", "event", "", RW, ""},
#ifdef PROVISION
    {"provisioning", "target.provisioning", "target", "event", "", RW, ""},
#endif
    {"event_timeout", "event.timeout", "event", "event", "", RW, ""},
    {"event_done", "event.done", "event", "event", "", RW, ""},
    {"event_fail", "event.fail", "event", "event", "", RW, ""},
    {"event_preflight", "event.preflightDone", "event", "event", "", RW,
     ""},
#ifndef PROVISION
    {"event_segment_failed", "event.segmentFailed", "event", "event", "", RW,
     ""},
    {"event_three_strikes", "event.threeStrikes", "event", "event", "", RW,
     ""},
    {"event_recalibrate", "event.recalibrate", "event", "event", "", RW,
     ""},
#endif
    {"wifi", "connectivity.wifi", "connectivity", "object", "", RS, ""},
};

String stateName() {
    String state = "starting";
    if (stateMachine != nullptr)
        stateMachine->visit_current_states(
            [&state](auto current) { state = current.c_str(); });
    return state;
}

struct PowerTelemetry {
    bool valid = false;
    uint32_t updatedAt = 0;
    int raw = 0;
    float voltage = 0.0f;
    int percent = 0;
    bool charging = false;
};

PowerTelemetry powerTelemetry;

void refreshPowerTelemetry(bool force = false) {
    const uint32_t now = millis();
    if (!force && powerTelemetry.valid &&
        now - powerTelemetry.updatedAt < 1000U)
        return;
    powerTelemetry.raw = analogRead(BATTERY_SENSE_INPUT);
    powerTelemetry.voltage = getBatteryVoltage();
    powerTelemetry.percent = constrain(
        static_cast<int>((powerTelemetry.voltage - 3.3f) * 111.11f), 0, 100);
    powerTelemetry.charging = checkIfCharging();
    powerTelemetry.updatedAt = millis();
    powerTelemetry.valid = true;
}

void loadVoltageCalibration() {
    Preferences preferences;
    if (!preferences.begin("radble-dtt", true)) return;
    global_voltageCalibrationInverseSlope = preferences.getFloat(
        "voltageSlope", global_voltageCalibrationInverseSlope);
    global_voltageCalibrationOffset = preferences.getFloat(
        "voltageOffset", global_voltageCalibrationOffset);
    preferences.end();
}

radble::Result calibrationValue(const String &path) {
    JsonDocument document;
    document["path"] = path;
    if (path == "setting.voltageCalibrationInverseSlope")
        document["value"] = global_voltageCalibrationInverseSlope;
    else if (path == "setting.voltageCalibrationOffset")
        document["value"] = global_voltageCalibrationOffset;
    else
        return radble::Result::failure("unknown_path", "Unknown calibration setting");
    String output;
    serializeJson(document, output);
    return radble::Result::success(output);
}

#ifndef PROVISION
radble::Result settingsFetchDiagnostic(JsonObjectConst args) {
    const auto requested = args["view"];
    SettingsFetchView view;
    if ((!requested.isNull() &&
         (!requested.is<const char *>() ||
          requested.as<JsonString>().size() != std::strlen(requested.as<const char *>()))) ||
        !parseSettingsFetchView(requested | "summary", view))
        return radble::Result::failure("invalid_value", "Unknown settings diagnostic view");
    JsonDocument document;
    document["path"] = "connectivity.settings";
    writeSettingsFetchStatus(document.as<JsonObject>(), getSettingsFetchStatus(), view);
    String output;
    serializeJson(document, output);
    return radble::Result::success(output);
}

radble::Result sessionDefinition(size_t index) {
    if (index >= session.segments.size())
        return radble::Result::failure("invalid_value", "Segment index is out of range");
    const Segment &segment = session.segments[index];
    JsonDocument document;
    document["id"] = session.id;
    document["name"] = session.name;
    document["segmentCount"] = session.segments.size();
    document["index"] = index;
    JsonObject item = document["segment"].to<JsonObject>();
    item["id"] = segment.id;
    item["idx"] = segment.idx;
    item["name"] = segment.name;
    item["type"] = static_cast<int>(segment.type);
    item["target"] = segment.params.target;
    item["start"] = segment.params.startPosition;
    item["end"] = segment.params.endPosition;
    item["speed"] = segment.params.trainingSpeed;
    item["window"] = segment.params.targetWindow;
    String output;
    serializeJson(document, output);
    return radble::Result::success(output);
}
#endif

struct PulseRequest {
    uint8_t output;
    uint16_t durationMs;
    uint32_t generation;
};

volatile uint32_t pulseGeneration[2] = {0, 0};

void requestNetworkOtaTask(void*) {
    vTaskDelay(pdMS_TO_TICKS(500));
    if (stateMachine == nullptr ||
        !stateMachine->process_event(force_update{}))
        Serial.println("[RAD BLE][DTT] network OTA state rejected");
    vTaskDelete(nullptr);
}

void pulseTask(void* parameter) {
    const PulseRequest request = *static_cast<PulseRequest*>(parameter);
    delete static_cast<PulseRequest*>(parameter);
    vTaskDelay(pdMS_TO_TICKS(request.durationMs));
    if (request.generation != pulseGeneration[request.output]) {
        vTaskDelete(nullptr);
        return;
    }
    if (request.output == 0)
        ledcWrite(0, 0);
    else
        digitalWrite(PUNISHMENT_OUTPUT, LOW);
    Serial.printf("[RAD BLE][DTT] diagnostic output %u off\n", request.output);
    vTaskDelete(nullptr);
}

radble::Result startPulse(uint8_t output, int value, int durationMs) {
    const String state = stateName();
    if (state.startsWith("play"))
        return radble::Result::failure(
            "invalid_state", "Diagnostic outputs are disabled during training");
    durationMs = constrain(durationMs, 1, output == 0 ? 2000 : 250);
    const uint32_t generation = ++pulseGeneration[output];
    if (output == 0)
        ledcWrite(0, map(constrain(value, 0, 100), 0, 100, 0, 255));
    else
        digitalWrite(PUNISHMENT_OUTPUT, value ? HIGH : LOW);
    auto* pulse =
        new PulseRequest{output, static_cast<uint16_t>(durationMs), generation};
    if (xTaskCreate(pulseTask, "rad-ble-pulse", 2048, pulse, 1, nullptr) !=
        pdPASS) {
        delete pulse;
        if (output == 0) ledcWrite(0, 0);
        else digitalWrite(PUNISHMENT_OUTPUT, LOW);
        return radble::Result::failure("busy", "Could not schedule output timeout");
    }
    return radble::Result::success(
        "{\"durationMs\":" + String(durationMs) + "}");
}

radble::Result handleCommand(JsonObjectConst request, void*) {
    if (stateMachine == nullptr)
        return radble::Result::failure("not_ready", "DTT is still starting");
    const String operation = request["op"] | "";
    const String path = request["path"] | "";
    const JsonObjectConst args = request["args"].as<JsonObjectConst>();

    if (operation == "ota.start" && String(args["transport"] | "") == "wifi") {
        if (WiFi.status() != WL_CONNECTED)
            return radble::Result::failure("network_failed", "Wi-Fi is disconnected");
        const String state = stateName();
#ifdef PROVISION
        const bool canUpdate = state == "init" || state == "provisioning.done";
#else
        const bool canUpdate = state == "init.idle" ||
                               state == "play.preflight" ||
                               state == "play.loadSettings" ||
                               state.startsWith("play.details");
#endif
        if (!canUpdate)
            return radble::Result::failure(
                "invalid_state", "Enter a safe idle page before network OTA");
        if (xTaskCreate(requestNetworkOtaTask, "rad-net-ota", 4096, nullptr, 1,
                        nullptr) != pdPASS)
            return radble::Result::failure("busy", "Could not schedule network OTA");
        return radble::Result::success(R"({"transport":"wifi","requested":true})");
    }

    if (operation == "sensor.read" || operation == "setting.read") {
        if (path == "device.firmwareProvenance") {
            const auto snapshot = firmware::provenance::runningSnapshot(
                FIRMWARE_TRACK, "dtt", VERSION, FIRMWARE_BUILD_SHA);
            const auto reply = firmware::provenance::response(snapshot, args);
            return reply.ok ? radble::Result::success(reply.json.c_str())
                            : radble::Result::failure(reply.code, reply.message);
        }
#ifndef PROVISION
        if (path == "connectivity.settings")
            return settingsFetchDiagnostic(args);
#endif
#ifndef PROVISION
        TrainingGuard guard(trainingMutex);
#endif
        JsonDocument document;
        document["path"] = path;
        if (path == "button.main")
            document["value"] = digitalRead(BUTTON_IN) == LOW;
        else if (path == "analog.distance") document["value"] = getDistance(5);
        else if (path == "analog.distanceVoltage")
            document["value"] = getAnalogVoltage(SENSOR_INPUT, 5);
        else if (path == "analog.distanceRaw")
            document["value"] = analogRead(SENSOR_INPUT);
        else if (path == "analog.batteryRaw" ||
                 path == "power.batteryVoltage" ||
                 path == "power.batteryPercent" ||
                 path == "power.charging") {
            refreshPowerTelemetry();
            if (path == "analog.batteryRaw")
                document["value"] = powerTelemetry.raw;
            else if (path == "power.batteryVoltage")
                document["value"] = powerTelemetry.voltage;
            else if (path == "power.batteryPercent")
                document["value"] = powerTelemetry.percent;
            else
                document["value"] = powerTelemetry.charging;
        } else if (path == "connectivity.health")
            document["value"] = healthCheckPassed;
        else if (path == "connectivity.wifi") {
            const bool connected = WiFi.status() == WL_CONNECTED;
            document["connected"] = connected;
            if (connected) {
                document["rssi"] = WiFi.RSSI();
                document["ip"] = WiFi.localIP().toString();
            }
        }
        else if (path == "setting.voltageCalibrationInverseSlope" ||
                 path == "setting.voltageCalibrationOffset")
            return calibrationValue(path);
#ifndef PROVISION
        else if (path == "motion.position")
            document["value"] = currentSegment ? currentSegment->currentPosition : 0;
        else if (path == "motion.speed")
            document["value"] = currentSegment ? currentSegment->currentSpeed : 0;
        else if (path == "motion.rpm")
            document["value"] = currentSegment ? currentSegment->currentRpm : 0;
        else if (path == "motion.positionState")
            document["value"] = currentSegment
                                    ? static_cast<int>(currentSegment->positionState)
                                    : 0;
        else if (path == "motion.trainingState")
            document["value"] = currentSegment
                                    ? static_cast<int>(currentSegment->state)
                                    : 0;
        else if (path == "motion.strokeCount")
            document["value"] = currentSegment ? currentSegment->statistics.strokes : 0;
        else if (path == "motion.progress")
            document["value"] = currentSegment ? currentSegment->getTrainingProgress() : 0.0f;
        else if (path == "motion.grade")
            document["value"] = currentSegment ? currentSegment->grade() : 0;
        else if (path == "motion.distance")
            document["value"] = currentSegment ? currentSegment->statistics.distance : 0.0f;
        else if (path == "motion.currentValue")
            document["value"] = currentSegment ? currentSegment->currentValue : 0;
        else if (path == "motion.target")
            document["value"] = currentSegment ? currentSegment->params.target : 0;
        else if (path == "motion.windowTime") {
            document["insideMs"] = currentSegment ? currentSegment->timeInsideWindow : 0;
            document["outsideMs"] = currentSegment ? currentSegment->timeOutsideWindow : 0;
        } else if (path == "motion.streak") {
            document["current"] = currentSegment ? currentSegment->currentStreak : 0;
            document["longest"] = currentSegment ? currentSegment->longestStreak : 0;
        }
        else if (path == "session.handsFree")
            document["value"] = session.handsFreeMode;
        else if (path == "session.current") {
            document["id"] = session.id;
            document["name"] = session.name;
            document["segmentIndex"] = session.segmentIdx;
            document["segmentCount"] = session.segmentCount;
            document["handsFree"] = session.handsFreeMode;
            document["calibrated"] = session.isCalibrated;
        } else if (path == "session.name")
            document["value"] = session.name;
        else if (path == "session.segmentIndex")
            document["value"] = session.segmentIdx;
        else if (path == "session.calibrationMin")
            document["value"] = session.calibratedMinPosition;
        else if (path == "session.calibrationMax")
            document["value"] = session.calibratedMaxPosition;
        else if (path == "session.definition")
            return sessionDefinition(args["index"] | session.segmentIdx);
#endif
        else if (path == "device.trainerId")
            document["value"] = trainerId;
        else if (path == "device.trainerShortId")
            document["value"] = trainerIdShort;
        else if (path == "device.serialNumber")
            document["value"] = serialNumber;
        else if (path == "device.alphaChannel")
            document["value"] = isAlphaVersion;
        else return radble::Result::failure("unknown_path", "Unknown resource path");
        String output;
        serializeJson(document, output);
        return radble::Result::success(output);
    }

    if (operation == "input.emit" || operation == "event.emit") {
        bool handled = false;
        const String event = args["event"] | "click";
        if (path == "button.main") {
            if (event == "click")
                handled = stateMachine->process_event(button_pressed{});
            else if (event == "double")
                handled = stateMachine->process_event(button_double_pressed{});
            else if (event == "long")
                handled = stateMachine->process_event(button_long_pressed{});
            else if (event == "multiple")
                if (!args["count"].is<int>() || args["count"].as<int>() < 2 ||
                    args["count"].as<int>() > 20)
                    return radble::Result::failure(
                        "invalid_value", "Multiple-click count must be 2..20");
                else
                    handled = stateMachine->process_event(
                        button_multiple_pressed{.count =
                            static_cast<uint8_t>(args["count"].as<int>())});
            else
                return radble::Result::failure("invalid_value",
                                               "Unknown button event");
        } else if (operation == "event.emit" && path == "event.timeout")
            handled = stateMachine->process_event(timeout_expired{});
        else if (operation == "event.emit" && path == "event.done")
            handled = stateMachine->process_event(done{});
        else if (operation == "event.emit" && path == "event.fail")
            handled = stateMachine->process_event(fail{});
        else if (operation == "event.emit" && path == "event.preflightDone")
            handled = stateMachine->process_event(preflight_done{});
#ifndef PROVISION
        else if (operation == "event.emit" && path == "event.segmentFailed")
            handled = stateMachine->process_event(segment_failed{});
        else if (operation == "event.emit" && path == "event.threeStrikes")
            handled = stateMachine->process_event(three_strikes{});
        else if (operation == "event.emit" && path == "event.recalibrate")
            handled = stateMachine->process_event(recalibrate{});
#endif
        else
            return radble::Result::failure("unknown_path", "Unknown event path");
        if (!handled)
            return radble::Result::failure(
                "guard_rejected", "The current state rejected this event");
        Serial.printf("[RAD BLE][DTT] event %s %s\n", path.c_str(),
                      event.c_str());
        return radble::Result::success();
    }

    if (operation == "setting.write" && path == "session.handsFree") {
#ifndef PROVISION
        if (!args["value"].is<bool>())
            return radble::Result::failure("invalid_value",
                                           "A boolean hands-free value is required");
        session.handsFreeMode = args["value"] | false;
        Serial.printf("[RAD BLE][DTT] handsFree=%d\n", session.handsFreeMode);
        return radble::Result::success(
            session.handsFreeMode ? "{\"value\":true}" : "{\"value\":false}");
#else
        return radble::Result::failure("unsupported", "No session in provisioning firmware");
#endif
    }

    if (operation == "setting.write" && path == "device.alphaChannel") {
        if (!args["value"].is<bool>())
            return radble::Result::failure("invalid_value",
                                           "A boolean update channel is required");
        const bool requested = args["value"] | false;
        if (requested != isAlphaVersion) toggleIsAlpha();
        return radble::Result::success(
            isAlphaVersion ? "{\"value\":true}" : "{\"value\":false}");
    }

    if ((operation == "setting.write" || operation == "setting.reset") &&
        (path == "setting.voltageCalibrationInverseSlope" ||
         path == "setting.voltageCalibrationOffset")) {
        const bool slope = path.endsWith("InverseSlope");
        const float defaultValue = slope ? 630.0f : 0.15f;
        if (operation == "setting.write" && !args["value"].is<float>())
            return radble::Result::failure("invalid_value", "A numeric calibration value is required");
        const float value = operation == "setting.reset"
                                ? defaultValue
                                : args["value"].as<float>();
        if ((slope && (value < 100.0f || value > 2000.0f)) ||
            (!slope && (value < -1.0f || value > 1.0f)))
            return radble::Result::failure("invalid_value", "Calibration value is out of range");
        Preferences preferences;
        if (!preferences.begin("radble-dtt", false))
            return radble::Result::failure("storage_failed", "Could not open calibration storage");
        const size_t stored = slope ? preferences.putFloat("voltageSlope", value)
                                    : preferences.putFloat("voltageOffset", value);
        preferences.end();
        if (stored != sizeof(float))
            return radble::Result::failure("storage_failed", "Could not store calibration value");
        if (slope)
            global_voltageCalibrationInverseSlope = value;
        else
            global_voltageCalibrationOffset = value;
        powerTelemetry.valid = false;
        return calibrationValue(path);
    }

#ifndef PROVISION
    if (operation == "session.apply" && path == "session.definition") {
        if (!args["session"].is<JsonObjectConst>())
            return radble::Result::failure("invalid_value", "A complete session object is required");
        JsonDocument replacement;
        replacement.set(args["session"]);
        String applyError = "Stop active training before replacing the session";
        bool applied = false;
        // process_event serializes the state check and mutation with countdown
        // and training transitions. Checking currentSegment here would race.
        const bool accepted =
            stateMachine != nullptr &&
            stateMachine->process_event(session_replace_requested{
                [&]() { return applySessionDocument(replacement, applyError); },
                applied});
        if (!accepted)
            return radble::Result::failure("invalid_state", applyError.c_str());
        if (!applied)
            return radble::Result::failure("invalid_value", applyError.c_str());
        Serial.printf("[RAD BLE][DTT] session replaced (%u segments)\n",
                      static_cast<unsigned>(session.segments.size()));
        return radble::Result::success(
            "{\"segmentCount\":" + String(session.segments.size()) + "}");
    }
#else
    if (operation == "factory.identity.write" && path == "factory.identity") {
        if (!args["trainerId"].is<const char *>() ||
            !args["serialNumber"].is<int>())
            return radble::Result::failure("invalid_value", "trainerId and serialNumber are required");
        const String requestedId = args["trainerId"].as<String>();
        const int requestedSerial = args["serialNumber"].as<int>();
        if (requestedId.length() < 6 || requestedId.length() > 99 ||
            requestedSerial < 0)
            return radble::Result::failure("invalid_value", "Factory identity is out of range");
        saveToEEPROM(requestedId, requestedSerial);
        return radble::Result::success(
            "{\"trainerId\":\"" + trainerId + "\",\"serialNumber\":" +
            String(serialNumber) + "}");
    }
#endif

    if (operation == "target.set") {
        bool handled = false;
#ifndef PROVISION
        if (path == "target.recalibrate")
            handled = stateMachine->process_event(recalibrate{});
        else if (path == "target.restartTraining")
            handled = stateMachine->process_event(restart_training{});
        else if (path == "target.preflight")
            handled = stateName() == "init.idle" &&
                      stateMachine->process_event(button_pressed{});
        else if (path == "target.pairing")
            handled = stateName() == "init.idle" &&
                      stateMachine->process_event(request_pairing{});
        else if (path == "target.wifi")
            handled = stateName() == "init.idle" &&
                      stateMachine->process_event(button_long_pressed{});
        else if (path == "target.calibrationMin")
            handled = stateMachine->process_event(recalibrate{});
        else if (path == "target.calibrationMax")
            handled = stateName() == "play.calibration.min" &&
                      stateMachine->process_event(button_pressed{});
        else if (path == "target.sessionDetails")
            handled = stateName() == "play.ready" &&
                      stateMachine->process_event(done{});
        else if (path == "target.play")
            handled = stateName().startsWith("play.details") &&
                      stateMachine->process_event(button_long_pressed{});
#ifdef BYPASS_PLAY
        else if (path == "target.grade")
            handled = stateName() == "play.idle" &&
                      stateMachine->process_event(button_long_pressed{});
#endif
        else if (path == "target.retry")
            handled = stateName() == "play.failed" &&
                      stateMachine->process_event(done{});
        else if (path == "target.final")
            handled = stateName() == "play.grade" &&
                      stateMachine->process_event(done{});
        else
#endif
        if (path == "target.update")
            handled = stateMachine->process_event(force_update{});
#ifdef PROVISION
        else if (path == "target.provisioning")
            handled = stateMachine->process_event(preflight_done{});
#endif
        else return radble::Result::failure("unknown_path", "Unknown target path");
        if (!handled)
            return radble::Result::failure(
                "guard_rejected", "The current state rejected this target");
        Serial.printf("[RAD BLE][DTT] target %s\n", path.c_str());
        return radble::Result::success();
    }

    if (operation == "indicator.set") {
        if (path != "indicator.status")
            return radble::Result::failure("unknown_path", "Unknown indicator path");
        if ((!args["hue"].isNull() && !args["hue"].is<int>()) ||
            (!args["brightness"].isNull() && !args["brightness"].is<int>()) ||
            (!args["durationMs"].isNull() && !args["durationMs"].is<int>()))
            return radble::Result::failure("invalid_value",
                                           "Indicator values must be integers");
        const int hue = args["hue"] | 0;
        const int brightness = args["brightness"] | 255;
        const int fadeMs = args["durationMs"] | 0;
        if (hue < 0 || hue > 255 || brightness < 0 || brightness > 255 ||
            fadeMs < 0 || fadeMs > 2000)
            return radble::Result::failure("invalid_value",
                                           "Indicator value is out of range");
        setLed(hue, brightness, fadeMs);
        Serial.printf("[RAD BLE][DTT] indicator hue=%d brightness=%d\n", hue,
                      brightness);
        return radble::Result::success();
    }

#ifndef PROVISION
    if (operation == "haptic.set" && path == "haptic.reward") {
        if (!args["value"].is<int>() ||
            (!args["durationMs"].isNull() && !args["durationMs"].is<int>()))
            return radble::Result::failure("invalid_value",
                                           "Reward value and duration must be integers");
        const int value = args["value"].as<int>();
        const int durationMs = args["durationMs"] | 250;
        if (value < 0 || value > 100 || durationMs < 1 || durationMs > 2000)
            return radble::Result::failure("invalid_value",
                                           "Reward pulse is out of range");
        return startPulse(0, value, durationMs);
    }
    if (operation == "haptic.set" && path == "haptic.punishment") {
        if ((!args["value"].is<bool>() && !args["value"].is<int>()) ||
            (!args["durationMs"].isNull() && !args["durationMs"].is<int>()))
            return radble::Result::failure(
                "invalid_value", "Punishment value and duration are invalid");
        const int value = args["value"] | 0;
        const int durationMs = args["durationMs"] | 100;
        if ((value != 0 && value != 1) || durationMs < 1 || durationMs > 250)
            return radble::Result::failure("invalid_value",
                                           "Punishment pulse is out of range");
        return startPulse(1, value, durationMs);
    }
#endif

    return radble::Result::failure("unsupported", "Operation is not supported");
}

String snapshot(radble::Surface surface, void*) {
    const String currentState = stateName();
#ifndef PROVISION
    TrainingGuard guard(trainingMutex);
#endif
    JsonDocument document;
    switch (surface) {
        case radble::Surface::State:
            document["state"] = currentState;
#ifndef PROVISION
            document["sessionId"] = session.id;
            document["segment"] = session.segmentIdx;
            document["segmentCount"] = session.segmentCount;
            document["training"] = trainingLifecycle.active();
#endif
            break;
        case radble::Surface::Essential:
            refreshPowerTelemetry();
            document["state"] = currentState;
            document["powered"] = true;
            document["batteryPercent"] = powerTelemetry.percent;
            document["charging"] = powerTelemetry.charging;
#ifndef PROVISION
            document["gameMode"] = trainingLifecycle.active();
            if (trainingLifecycle.active() && currentSegment) {
                document["positionCm"] = currentSegment->currentPosition;
                document["targetStartCm"] = currentSegment->startWindow;
                document["targetEndCm"] = currentSegment->endWindow;
                document["gradePercent"] = currentSegment->grade();
            } else {
                document["positionCm"] = nullptr;
                document["targetStartCm"] = nullptr;
                document["targetEndCm"] = nullptr;
                document["gradePercent"] = nullptr;
            }
#else
            document["gameMode"] = false;
            document["positionCm"] = nullptr;
            document["targetStartCm"] = nullptr;
            document["targetEndCm"] = nullptr;
            document["gradePercent"] = nullptr;
#endif
            break;
        case radble::Surface::Button:
            document["id"] = "main";
            document["pressed"] = digitalRead(BUTTON_IN) == LOW;
            break;
        case radble::Surface::Analog:
            document["distanceCm"] = getDistance(1);
            document["distanceVoltage"] = getAnalogVoltage(SENSOR_INPUT, 1);
            document["distanceRaw"] = analogRead(SENSOR_INPUT);
            refreshPowerTelemetry();
            document["batteryRaw"] = powerTelemetry.raw;
            break;
        case radble::Surface::Power:
            refreshPowerTelemetry();
            document["raw"] = powerTelemetry.raw;
            document["voltage"] = powerTelemetry.voltage;
            document["percent"] = powerTelemetry.percent;
            document["charging"] = powerTelemetry.charging;
            break;
        case radble::Surface::Motion:
#ifndef PROVISION
            document["available"] = currentSegment != nullptr;
            if (currentSegment != nullptr) {
                document["position"] = currentSegment->currentPosition;
                document["speed"] = currentSegment->currentSpeed;
                document["rpm"] = currentSegment->currentRpm;
                document["positionState"] =
                    static_cast<int>(currentSegment->positionState);
                document["trainingState"] =
                    static_cast<int>(currentSegment->state);
                document["strokes"] = currentSegment->statistics.strokes;
                document["progress"] = currentSegment->getTrainingProgress();
                document["grade"] = currentSegment->grade();
                document["distanceCm"] = currentSegment->statistics.distance;
                document["currentValue"] = currentSegment->currentValue;
                document["target"] = currentSegment->params.target;
                document["insideMs"] = currentSegment->timeInsideWindow;
                document["outsideMs"] = currentSegment->timeOutsideWindow;
            }
#else
            document["available"] = false;
#endif
            break;
        case radble::Surface::Connectivity:
            document["wifi"] = WiFi.status() == WL_CONNECTED;
            document["rssi"] = WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0;
            document["ip"] = WiFi.localIP().toString();
            document["health"] = healthCheckPassed;
            break;
        case radble::Surface::Indicator:
            document["id"] = "led";
            document["available"] = true;
            break;
        case radble::Surface::Haptic:
            document["rewardAvailable"] = true;
            document["punishmentAvailable"] = true;
            document["diagnosticOnly"] = true;
            break;
        default:
            return "{}";
    }
    String output;
    serializeJson(document, output);
    return output;
}

radble::Result prepareOta(bool starting, const char*, void*) {
    if (!starting) return radble::Result::success();
    if (esp_ota_get_next_update_partition(nullptr) == nullptr)
        return radble::Result::failure(
            "unsupported_partition", "No inactive OTA application slot exists");
    const String state = stateName();
    if (state == "play.idle" || state == "play.begin")
        return radble::Result::failure(
            "invalid_state", "Stop the training session before direct OTA");
    if (!checkIfCharging() && getBatteryVoltage() < 3.5f)
        return radble::Result::failure(
            "preflight_failed", "Battery is too low for direct OTA");
    ++pulseGeneration[0];
    ++pulseGeneration[1];
    ledcWrite(0, 0);
    digitalWrite(PUNISHMENT_OUTPUT, LOW);
    Serial.println("[RAD BLE][DTT] direct OTA outputs disabled");
    return radble::Result::success();
}

void releaseDiagnosticOutputs(void*) {
    ++pulseGeneration[0];
    ++pulseGeneration[1];
    ledcWrite(0, 0);
    digitalWrite(PUNISHMENT_OUTPUT, LOW);
    setLedOff();
}

class ServerCallbacks final : public NimBLEServerCallbacks {
    void onConnect(NimBLEServer*, NimBLEConnInfo& connection) override {
        radBleServer.onConnect(connection.getConnHandle());
    }

    void onDisconnect(NimBLEServer* server, NimBLEConnInfo& connection,
                      int) override {
        radBleServer.onDisconnect(connection.getConnHandle());
        server->startAdvertising();
    }
};

ServerCallbacks serverCallbacks;

}  // namespace

radble::Server radBleServer;

bool initRadBle() {
    loadVoltageCalibration();
    refreshPowerTelemetry(true);
    static String deviceName = radble::loadDeviceName("DTT");
    NimBLEDevice::init(deviceName.c_str());
    NimBLEDevice::setMTU(512);
    auto* server = NimBLEDevice::createServer();
    server->setCallbacks(&serverCallbacks);
    const radble::Config config = {
        .identity = {
            .deviceType = "DTT",
            .deviceName = "DTT",
            .serviceUuid = radble::DTT_SERVICE_UUID,
            .firmwareVersion = VERSION,
            .build = FIRMWARE_BUILD_SHA,
            .partitionLayout = "dtt-ota-16mb-v1",
        },
        .capabilities = radble::CAP_BUTTON | radble::CAP_POWER |
                        radble::CAP_ANALOG |
#ifndef PROVISION
                        radble::CAP_MOTION |
                        radble::CAP_HAPTIC |
#endif
                        radble::CAP_CONNECTIVITY | radble::CAP_INDICATOR |
                        radble::CAP_SENSOR_STREAM,
        .channels = radble::CHANNEL_SENSOR_STREAM | radble::CHANNEL_BUTTON |
                    radble::CHANNEL_POWER | radble::CHANNEL_ANALOG |
#ifndef PROVISION
                    radble::CHANNEL_MOTION | radble::CHANNEL_HAPTIC |
#endif
                    radble::CHANNEL_CONNECTIVITY | radble::CHANNEL_INDICATOR |
                    radble::CHANNEL_BATTERY |
                    radble::CHANNEL_APPLICATION_OTA,
        .resources = RESOURCES,
        .resourceCount = sizeof(RESOURCES) / sizeof(RESOURCES[0]),
        .callbacks = {
            .commandHandler = handleCommand,
            .snapshotHandler = snapshot,
            .otaDataHandler = nullptr,
            .otaSafetyHandler = prepareOta,
            .leaseReleaseHandler = releaseDiagnosticOutputs,
            .streamSafetyHandler = nullptr,
        },
        .context = nullptr,
    };
    if (!radBleServer.begin(server, config)) return false;
    auto* advertising = NimBLEDevice::getAdvertising();
    advertising->setName(deviceName.c_str());
    advertising->addServiceUUID(radBleServer.serviceUuid());
    advertising->enableScanResponse(true);
    return advertising->start();
}

#endif
