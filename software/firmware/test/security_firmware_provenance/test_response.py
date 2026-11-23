"""Actual provenance verifier/serializer/reply gate with a real OpenSSL host port.

Uses the repository's public ES256 vector, signed by a throwaway key rather
than a release key: the verifier is compiled from a copy whose staging key slot
holds the vector's public key. No signer secrets, network or devices.
Prepare test_native ArduinoJson/RadBLE as for security_dashboard_transport first.
"""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent


def between(source, start, end):
    return source[source.index(start):source.index(end, source.index(start))]


class ProvenanceResponseTests(unittest.TestCase):
    def test_signed_proof_roundtrip_and_actual_reply_budget(self):
        self.assertIsNotNone(shutil.which("openssl"), "OpenSSL is required for real host signature verification")
        reply_root = ROOT / ".pio/libdeps/test_native/RadBLE/src"
        reply = (reply_root / "RadBle.cpp").read_text(encoding="utf-8")
        port = (ROOT / "test/security_dashboard_transport/fixture.cpp.in").read_text(encoding="utf-8")
        source = (HERE / "fixture.cpp.in").read_text(encoding="utf-8")
        source = source.replace("// ACTUAL_NATIVE_STRING_PORT", between(port, "class String :", "\nclass Stream"))
        source = source.replace("// ACTUAL_RESULT", between(reply, "Result Result::success(", "\nServer::Server()"))
        source = source.replace("// ACTUAL_REPLY", between(reply, "void Server::sendStage(", "\nvoid Server::sendSerialized("))
        source = source.replace("// ACTUAL_CRYPTO_PORT", (HERE / "native_crypto_port.h.in").read_text(encoding="utf-8"))
        vector = json.loads((ROOT.parents[1] / ".github/scripts/firmware_provenance_test_vector.json").read_text(encoding="utf-8"))
        source = source.replace("// SIGNED_VECTOR", "static const std::string signedToken = " + json.dumps(vector["compactJws"]) + ";")
        states = sorted(set(re.findall(r'"([A-Za-z][A-Za-z0-9_.]*)"_s', (ROOT / "src/state/machine.h").read_text(encoding="utf-8"))))
        source = source.replace("// DTT_STATE_NAMES", "static const char* states[] = {" + ",".join(json.dumps(s) for s in states) + "};")
        with tempfile.TemporaryDirectory(prefix="dtt-provenance-") as temp:
            directory = Path(temp)
            (directory / "mbedtls").mkdir()
            # The real verifier, trusting the vector's throwaway key in place of
            # the staging release key. The include path finds this copy first.
            verifier = (ROOT / "lib/FirmwareUpdateProtocol/src/FirmwareProvenance.h").read_text(encoding="utf-8")
            staging_key = re.search(
                r'(STAGING_PUBLIC_KEY = R"KEY\()(-----BEGIN PUBLIC KEY-----\n.*?-----END PUBLIC KEY-----\n)(\)KEY")',
                verifier, re.S)
            staging_id = re.search(r'(STAGING_KEY_ID = ")([^"]+)(")', verifier)
            self.assertIsNotNone(staging_key)
            self.assertIsNotNone(staging_id)
            self.assertNotEqual(staging_id.group(2), vector["keyId"])
            self.assertNotIn(vector["publicKeyPem"], verifier)
            verifier = verifier.replace(staging_key.group(0), staging_key.group(1) + vector["publicKeyPem"] + staging_key.group(3), 1)
            verifier = verifier.replace(staging_id.group(0), staging_id.group(1) + vector["keyId"] + staging_id.group(3), 1)
            (directory / "FirmwareProvenance.h").write_text(verifier, encoding="utf-8")
            (directory / "Preferences.h").write_text('''#pragma once
inline std::map<std::string,std::string> fixturePreferences;
struct Preferences {
 bool begin(const char*,bool){return true;} void end(){}
 String getString(const char* key,const char*){auto found=fixturePreferences.find(key);return found==fixturePreferences.end()?String(""):String(found->second);}
 size_t putString(const char* key,const char* value){fixturePreferences[key]=value;return std::strlen(value);}
 bool remove(const char* key){return fixturePreferences.erase(key)>0;}
};
''')
            (directory / "esp_ota_ops.h").write_text('''#pragma once
struct esp_partition_t {}; constexpr int ESP_OK=0;
inline const esp_partition_t* esp_ota_get_running_partition(){return nullptr;}
inline int esp_partition_get_sha256(const esp_partition_t*,unsigned char*){return -1;}
''')
            (directory / "mbedtls/pk.h").write_text('''#pragma once
struct mbedtls_pk_context {std::string pem;}; constexpr int MBEDTLS_MD_SHA256=1;
inline void mbedtls_pk_init(mbedtls_pk_context*); inline void mbedtls_pk_free(mbedtls_pk_context*);
inline int mbedtls_pk_parse_public_key(mbedtls_pk_context*,const unsigned char*,size_t);
inline int mbedtls_pk_verify(mbedtls_pk_context*,int,const unsigned char*,size_t,const unsigned char*,size_t);
''')
            (directory / "mbedtls/sha256.h").write_text('#pragma once\ninline int mbedtls_sha256_ret(const unsigned char*,size_t,unsigned char*,int);\n')
            cpp = directory / "test.cpp"
            cpp.write_text("#define TEST_CRYPTO_DIRECTORY " + json.dumps(str(directory)) + "\n" + source)
            binary = directory / "provenance"
            compiler = os.environ.get("CXX", "c++")
            command = [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-I", str(directory), "-I", str(ROOT / ".pio/libdeps/test_native/ArduinoJson/src"), "-I", str(reply_root), "-I", str(ROOT / "lib/FirmwareUpdateProtocol/src"), str(cpp), "-o", str(binary)]
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
                result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as error:
                print(error.stdout, error.stderr)
                raise
            self.assertIn("provenance real sender:", result.stdout)
            print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
