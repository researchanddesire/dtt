"""Compile actual vendored portal wait/save methods with synthetic clock/Wi-Fi."""

import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


def method(source, signature):
    start = source.index(signature)
    body = source.index("{", start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


HARNESS = r"""
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <memory>
#include <string>
#include "PortalSafety.h"

constexpr uint8_t WL_IDLE_STATUS = 0;
constexpr uint8_t WL_CONNECTED = 3;
constexpr uint8_t WL_CONNECT_FAILED = 4;
uint32_t clockMs = 0;
uint32_t millis() { return clockMs; }
void delay(uint32_t amount) { clockMs += amount; }
struct SyntheticWifi {
    int sdkWaits = 0;
    bool scheduledConnection = false;
    uint32_t connectsAt = 0;
    uint8_t status() {
        return scheduledConnection && clockMs >= connectsAt
            ? WL_CONNECTED : WL_IDLE_STATUS;
    }
    uint8_t waitForConnectResult() { ++sdkWaits; return WL_CONNECTED; }
} WiFi;
struct SyntheticServer {
    uint32_t address;
    uint16_t port;
    SyntheticServer(uint32_t address, uint16_t port): address(address), port(port) {}
    explicit SyntheticServer(uint16_t port): address(0), port(port) {}
    void handleClient() {}
};
struct SyntheticDns { void processNextRequest() {} };
class WiFiManager {
public:
    bool configPortalActive = true;
    uint32_t _configPortalAbsoluteStart = 0;
    uint32_t _configPortalTimeout = 300000;
    bool connect = true;
    bool _enableCaptivePortal = false;
    uint32_t _cpclosedelay = 2000;
    std::string _ssid = "synthetic";
    std::string _pass = "synthetic";
    bool _connectonsave = true;
    bool _disableConfigPortal = true;
    bool _shouldBreakAfterConfig = false;
    uint32_t connectAdvance = 0;
    uint8_t connectResult = WL_CONNECTED;
    int shutdowns = 0;
    int callbacks = 0;
    int connections = 0;
    int disabledStation = 0;
    std::function<void()> _savewificallback = [&] { ++callbacks; };
    std::unique_ptr<SyntheticServer> server{new SyntheticServer(80)};
    std::unique_ptr<SyntheticDns> dnsServer{new SyntheticDns};
    bool configPortalHasTimeout() {
        return configPortalActive && _configPortalTimeout > 0 &&
            portal_safety::remaining(_configPortalAbsoluteStart,
                                     _configPortalTimeout, clockMs) == 0;
    }
    bool shutdownConfigPortal() {
        ++shutdowns;
        configPortalActive = false;
        return true;
    }
    uint8_t connectWifi(const std::string&, const std::string&, bool) {
        ++connections;
        clockMs += connectAdvance;
        return connectResult;
    }
    bool WiFi_enableSTA(bool enabled) {
        if (!enabled) ++disabledStation;
        return true;
    }
    uint8_t waitForConnectResult(uint32_t timeout);
    uint8_t processConfigPortal();
};
"""

CASES = r"""
int main(int argc, char **argv) {
    assert(argc == 2);
    const int test = std::atoi(argv[1]);
    WiFiManager wm;
    switch (test) {
    case 0: {
        const auto captive = portal_safety::makeServer<SyntheticServer>(true, 0xc0a80401U, 80);
        const auto standalone = portal_safety::makeServer<SyntheticServer>(false, 0xc0a80401U, 80);
        assert(captive->address == 0xc0a80401U && captive->port == 80);
        assert(standalone->address == 0 && standalone->port == 80);
        break;
    }
    case 1:
        clockMs = 299950;
        assert(wm.waitForConnectResult(0) == WL_CONNECT_FAILED);
        assert(clockMs == 300000 && WiFi.sdkWaits == 0);
        break;
    case 2:
        clockMs = 299850;
        WiFi.scheduledConnection = true;
        WiFi.connectsAt = 299900;
        assert(wm.waitForConnectResult(0) == WL_CONNECTED);
        assert(clockMs < 300000 && WiFi.sdkWaits == 0);
        break;
    case 3:
        clockMs = 299500;
        assert(wm.waitForConnectResult(10) == WL_IDLE_STATUS);
        assert(clockMs == 299510);
        break;
    case 4:
        wm._configPortalAbsoluteStart = UINT32_MAX - 100;
        wm._configPortalTimeout = 300;
        clockMs = UINT32_MAX - 50;
        assert(wm.waitForConnectResult(0) == WL_CONNECT_FAILED);
        assert(uint32_t(clockMs - wm._configPortalAbsoluteStart) == 300);
        break;
    case 5:
        wm.configPortalActive = false;
        assert(wm.waitForConnectResult(0) == WL_CONNECTED);
        assert(WiFi.sdkWaits == 1);
        break;
    case 6:
        clockMs = 299900;
        wm.connectAdvance = 250;
        WiFi.scheduledConnection = true;
        WiFi.connectsAt = 300000;
        assert(wm.processConfigPortal() == WL_CONNECT_FAILED);
        assert(wm.callbacks == 0 && wm.shutdowns == 1);
        assert(wm.disabledStation == 0);
        assert(WiFi.status() == WL_CONNECTED);
        break;
    case 7:
        clockMs = 299900;
        wm._enableCaptivePortal = true;
        assert(wm.processConfigPortal() == WL_CONNECT_FAILED);
        assert(clockMs == 300000 && wm.connections == 0);
        assert(wm.callbacks == 0 && wm.shutdowns == 1);
        break;
    case 8:
        clockMs = 299500;
        wm.connectAdvance = 100;
        assert(wm.processConfigPortal() == WL_CONNECTED);
        assert(wm.callbacks == 1 && wm.shutdowns == 1);
        break;
    case 9:
        clockMs = 1000;
        wm.connectResult = WL_CONNECT_FAILED;
        assert(wm.processConfigPortal() == WL_IDLE_STATUS);
        assert(wm.disabledStation == 1 && wm.shutdowns == 0);
        assert(wm.callbacks == 0);
        break;
    default: assert(false);
    }
}
"""


class PortalSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "lib/WiFiManager/WiFiManager.cpp").read_text()
        cls.directory = tempfile.TemporaryDirectory(prefix="dtt-wifi-portal-")
        directory = pathlib.Path(cls.directory.name)
        harness = directory / "portal.cpp"
        harness.write_text(
            HARNESS
            + method(source, "uint8_t WiFiManager::waitForConnectResult(uint32_t timeout)")
            + method(source, "uint8_t WiFiManager::processConfigPortal()")
            + CASES
        )
        cls.binary = directory / "portal"
        subprocess.run(
            ["c++", "-std=c++17", "-fsanitize=address,undefined",
             "-fno-omit-frame-pointer", "-I", str(ROOT / "lib/WiFiManager"),
             str(harness), "-o", str(cls.binary)],
            check=True, capture_output=True, text=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_captive_binding_and_standalone_compatibility(self):
        self.run_case(0)

    def test_default_wait_cannot_exceed_portal_deadline(self):
        self.run_case(1)

    def test_successful_connection_before_deadline(self):
        self.run_case(2)

    def test_shorter_explicit_connection_timeout(self):
        self.run_case(3)

    def test_millisecond_rollover(self):
        self.run_case(4)

    def test_standalone_wait_keeps_sdk_behavior(self):
        self.run_case(5)

    def test_late_connection_preserved_without_save_callback(self):
        self.run_case(6)

    def test_captive_delay_cannot_start_connection_after_expiry(self):
        self.run_case(7)

    def test_successful_save_before_deadline(self):
        self.run_case(8)

    def test_failed_captive_connection_disables_station_before_serving_requests(self):
        self.run_case(9)

    def run_case(self, case):
        subprocess.run([str(self.binary), str(case)], check=True,
                       capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
