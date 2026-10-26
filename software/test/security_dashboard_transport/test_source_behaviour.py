"""Offline regressions for the actual transport/cache helpers and portal renderer.

Prepare the pinned reply dependency with --prepare-reply-dependency, then run:
python3 test/security_dashboard_transport/test_source_behaviour.py
Requires a C++17 compiler and test_native ArduinoJson/RadBLE headers and sources.
The ESP32 HTTP/TLS and SPIFFS ports are synthetic; this is not a hardware TLS test.
"""
from pathlib import Path
import os
import json
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def between(source, start, end):
    return source[source.index(start):source.index(end, source.index(start))]


class SourceBehaviourTests(unittest.TestCase):
    def test_actual_helpers_in_production_and_development(self):
        wifi = (ROOT / "src/wifiSettings.cpp").read_text()
        portal = (ROOT / "lib/WiFiManager/WiFiManager.cpp").read_text()
        transport = between(wifi, "namespace {\nconstexpr size_t MAX_DASHBOARD", "\n#ifndef PROVISION\nvoid checkIfPairedTask")
        cache = between(wifi, "namespace {\nconstexpr char SESSION_TEMP_FILE", "\nbool applySessionDocument")
        diagnostics = between(wifi, "namespace {\nportMUX_TYPE settingsFetchStatusMux", "\nstatic void sessionFromJson")
        load = between(wifi, "void loadSessionTask(", "\nvoid fetchSettingsTask(")
        fetch = between(wifi, "void fetchSettingsTask(", "\nvoid saveResultsTask(")
        html = between(portal, "String WiFiManager::htmlEntities(", "\n/**")
        # This is the actual pinned dependency used by the firmware, including
        # its final envelope serialization and unchanged 509-byte rejection gate.
        reply_root = ROOT / ".pio/libdeps/test_native/RadBLE/src"
        reply_source = (reply_root / "RadBle.cpp").read_text()
        reply = between(reply_source, "void Server::sendStage(", "\nvoid Server::sendSerialized(")
        result = between(reply_source, "Result Result::success(", "\nServer::Server()")
        ble = (ROOT / "src/services/rad_ble.cpp").read_text()
        handler = between(ble, "radble::Result settingsFetchDiagnostic(", "\nradble::Result sessionDefinition(")
        states = sorted(set(re.findall(r'"([A-Za-z][A-Za-z0-9_.]*)"_s', (ROOT / "src/state/machine.h").read_text())))
        source = (HERE / "fixture.cpp.in").read_text()
        source = source.replace("// ACTUAL_TRANSPORT", transport)
        source = source.replace("// ACTUAL_CACHE", cache)
        source = source.replace("// ACTUAL_DIAGNOSTICS", diagnostics)
        source = source.replace("// ACTUAL_LOAD", load)
        source = source.replace("// ACTUAL_FETCH", fetch)
        source = source.replace("// ACTUAL_HTML", html)
        source = source.replace("// ACTUAL_REPLY", reply)
        source = source.replace("// ACTUAL_RESULT", result)
        source = source.replace("// ACTUAL_DIAGNOSTIC_HANDLER", handler)
        source = source.replace("// DTT_STATE_NAMES", "static const char *dttStates[] = {" + ",".join(json.dumps(s) for s in states) + "};")
        includes = ROOT / ".pio/libdeps/test_native/ArduinoJson/src"
        self.assertTrue((includes / "ArduinoJson.h").is_file())
        with tempfile.TemporaryDirectory(prefix="dtt-security-transport-") as directory:
            # The real date-validation client uses the synthetic transport
            # declared by fixture.cpp.in; no SDK, network or hardware is used.
            (Path(directory) / "WiFiClientSecure.h").write_text("#pragma once\n")
            (Path(directory) / "mbedtls").mkdir()
            (Path(directory) / "mbedtls/x509_crt.h").write_text("#pragma once\n")
            cpp = Path(directory) / "test.cpp"
            cpp.write_text(source)
            for local_http in (False, True):
                with self.subTest(local_http=local_http):
                    binary = Path(directory) / ("development" if local_http else "production")
                    command = [os.environ.get("CXX", "c++"), "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-I", directory, "-I", str(includes), "-I", str(reply_root), "-I", str(ROOT / "src"), "-I", str(ROOT / "lib/TrainingTypes/src"), "-I", str(ROOT / "lib/FirmwareUpdateProtocol/src"), str(cpp), "-o", str(binary)]
                    if local_http:
                        command += ["-DDTT_ALLOW_LOCAL_HTTP"]
                    subprocess.run(command, check=True, capture_output=True, text=True)
                    result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
                    self.assertIn("all assertions passed", result.stdout)
                    for line in result.stdout.splitlines():
                        if line.startswith("actual reply budget:"):
                            print(f"local_http={local_http}: {line}")

    def test_rendering_and_session_entry_points_are_wired(self):
        source = (ROOT / "lib/WiFiManager/WiFiManager.cpp").read_text()
        form = between(source, "void WiFiManager::handleWifi(", "\nvoid WiFiManager::handleWifiSave")
        self.assertIn("pitem.replace(FPSTR(T_v), htmlEntities(WiFi_SSID()))", form)
        self.assertIn("pitem.replace(FPSTR(T_p), htmlEntities(WiFi_psk()))", form)
        self.assertIn("millis() - _configPortalStart >= _configPortalTimeout", source)
        wifi = (ROOT / "src/wifiSettings.cpp").read_text()
        self.assertNotIn("setInsecure", wifi)
        self.assertNotIn("http.getString()", wifi)
        self.assertNotIn("SPIFFS.begin(true)", wifi)
        for secret in ("payload.c_str()", "requestBody.c_str()", "session.id.c_str()", "session.name.c_str()"):
            self.assertNotIn(secret, wifi)
        fetch = between(wifi, "void fetchSettingsTask(", "\nvoid saveResultsTask(")
        self.assertIn("SessionDocumentMode::DashboardPage", fetch)
        self.assertIn("session_load_ready{", fetch)
        self.assertIn("session_load_failed{}", fetch)
        self.assertNotIn("process_event(done{})", fetch)
        self.assertNotIn("process_event(fail{})", fetch)
        apply = between(wifi, "bool applySessionDocument(", "\nvoid loadSessionTask(")
        self.assertLess(apply.index("validateSessionDocument"), apply.index("persistSessionDocument"))
        self.assertLess(apply.index("persistSessionDocument"), apply.index("sessionFromJson"))


if __name__ == "__main__":
    if sys.argv[1:] == ["--prepare-reply-dependency"]:
        pins = set(re.findall(r"https://github\.com/researchanddesire/rad-ble\.git#[0-9a-fA-F]{40}", (ROOT / "platformio.ini").read_text()))
        if len(pins) != 1:
            raise SystemExit("Expected one unique pinned RadBLE dependency")
        subprocess.run([sys.executable, "-m", "platformio", "pkg", "install",
                        "-e", "test_native", "--library", pins.pop(),
                        "--no-save", "--skip-dependencies"], cwd=ROOT, check=True)
    else:
        unittest.main()
