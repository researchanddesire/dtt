"""Offline tests of the actual certificate-date client with synthetic TLS ports."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


class CertificateDateTests(unittest.TestCase):
    def run_fixture(self, *defines):
        with tempfile.TemporaryDirectory(prefix="dtt-certificate-dates-") as directory:
            temporary = Path(directory)
            source = temporary / "main.cpp"
            source.write_text((HERE / "fixture.cpp.in").read_text())
            executable = temporary / "certificate-dates"
            subprocess.run([
                os.environ.get("CXX", "c++"), "-std=c++17", "-Wall", "-Wextra",
                "-Werror", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                *defines,
                "-I", str(HERE), "-I", str(ROOT / "lib/FirmwareUpdateProtocol/src"),
                str(source), "-o", str(executable),
            ], check=True)
            subprocess.run([str(executable)], check=True)

    def test_calendar_chain_and_client_dispatch(self):
        self.run_fixture()

    def test_sdk_checked_dates_need_only_a_plausible_clock(self):
        self.run_fixture("-DMBEDTLS_HAVE_TIME_DATE")

    def test_every_application_tls_consumer_uses_the_date_client(self):
        wifi = (ROOT / "src/wifiSettings.cpp").read_text()
        updater = (ROOT / "lib/FirmwareUpdateProtocol/src/FirmwareUpdateRuntime.cpp").read_text()
        header = (ROOT / "lib/FirmwareUpdateProtocol/src/CertificateDateClient.h").read_text()
        self.assertIn("DashboardClient<firmware::CertificateDateClient>", wifi)
        self.assertNotIn("DashboardClient<WiFiClientSecure>", wifi)
        self.assertEqual(updater.count("firmware::CertificateDateClient secureClient;"), 2)
        self.assertNotIn("WiFiClientSecure secureClient;", updater)
        self.assertIn("firmware::CertificateDateClient &secureClient", updater)
        for consumer in (wifi, updater):
            self.assertIn("setCACertBundle", consumer)
            self.assertIn("HTTPC_DISABLE_FOLLOW_REDIRECTS", consumer)
        self.assertNotIn("mbedtls_x509_time_is_past(", header)
        self.assertNotIn("mbedtls_x509_time_is_future(", header)
        self.assertNotIn("setInsecure(", header)


if __name__ == "__main__":
    unittest.main()
