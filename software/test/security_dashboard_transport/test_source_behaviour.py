"""Offline regressions for the actual transport/cache helpers and portal renderer.

Run: python3 test/security_dashboard_transport/test_source_behaviour.py
Requires a C++17 compiler and the locally installed test_native ArduinoJson headers.
The ESP32 HTTP/TLS and SPIFFS ports are synthetic; this is not a hardware TLS test.
"""
from pathlib import Path
import os
import subprocess
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
        html = between(portal, "String WiFiManager::htmlEntities(", "\n/**")
        source = (HERE / "fixture.cpp.in").read_text()
        source = source.replace("// ACTUAL_TRANSPORT", transport)
        source = source.replace("// ACTUAL_CACHE", cache)
        source = source.replace("// ACTUAL_HTML", html)
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
                    command = [os.environ.get("CXX", "c++"), "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-I", directory, "-I", str(includes), "-I", str(ROOT / "lib/TrainingTypes/src"), "-I", str(ROOT / "lib/FirmwareUpdateProtocol/src"), str(cpp), "-o", str(binary)]
                    if local_http:
                        command += ["-DDTT_ALLOW_LOCAL_HTTP"]
                    subprocess.run(command, check=True, capture_output=True, text=True)
                    result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
                    self.assertIn("all assertions passed", result.stdout)

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
    unittest.main()
