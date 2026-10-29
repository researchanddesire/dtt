import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import development_server as dev
from development_server import DEFAULT_SERVER, development_server, local_origin


class DevelopmentServerTests(unittest.TestCase):
    def test_defaults_and_explicit_private_lan_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(development_server(directory), DEFAULT_SERVER)
            path = Path(directory) / "local.settings.json"
            path.write_text(json.dumps({"server": "http://192.168.2.59:3000/"}))
            self.assertEqual(development_server(directory), "http://192.168.2.59:3000")

    def test_allows_loopback_and_private_networks_without_dns(self):
        for origin in ("http://localhost:3000", "http://127.0.0.1", "http://[::1]:3000",
                       "https://10.1.2.3:18443", "http://172.16.0.1", "http://192.168.1.1"):
            with self.subTest(origin=origin):
                self.assertEqual(local_origin(origin), origin)

    def test_rejects_external_ambiguous_or_credential_origins(self):
        for origin in (None, 42, "https://dashboard.researchanddesire.com", "http://example.local",
                       "http://8.8.8.8", "http://169.254.1.1", "http://172.32.0.1",
                       "http://[fe80::1]", "ftp://192.168.1.1", "http://u:p@192.168.1.1",
                       "http://@192.168.1.1", "http://127.0.0.1/api", "http://127.0.0.1?q=x",
                       "http://127.0.0.1#x", "http://127.0.0.1:0", "http://127.0.0.1:65536",
                       "http://127.0.0.1\n", 'http://127.0.0.1/"'):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                local_origin(origin)

    def test_rewrites_loopback_origins_to_the_lan_address(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(development_server(directory, lan_ip="192.168.1.195"),
                             "http://192.168.1.195:3000")
            path = Path(directory) / "local.settings.json"
            for server, expected in (("http://localhost:3000", "http://192.168.1.195:3000"),
                                     ("https://[::1]:18443", "https://192.168.1.195:18443"),
                                     ("http://192.168.2.59:3000", "http://192.168.2.59:3000")):
                path.write_text(json.dumps({"server": server}))
                with self.subTest(server=server):
                    self.assertEqual(development_server(directory, lan_ip="192.168.1.195"), expected)
            path.write_text(json.dumps({"server": "http://localhost:3000"}))
            with self.assertRaises(ValueError):
                development_server(directory, lan_ip="8.8.8.8")

    def test_detects_only_a_private_lan_address(self):
        for detected, expected in (("192.168.1.195", "192.168.1.195"), ("8.8.4.4", None),
                                   ("127.0.0.1", None)):
            with self.subTest(detected=detected), mock.patch.object(dev.socket, "socket") as factory:
                factory.return_value.__enter__.return_value.getsockname.return_value = (detected, 5000)
                self.assertEqual(dev.detect_lan_ip(), expected)
        with mock.patch.object(dev.socket, "socket", side_effect=OSError):
            self.assertIsNone(dev.detect_lan_ip())

    def test_rejects_unknown_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "local.settings.json"
            for settings in ([], {"password": "synthetic"}):
                path.write_text(json.dumps(settings))
                with self.assertRaises(ValueError):
                    development_server(directory)


if __name__ == "__main__":
    unittest.main()
