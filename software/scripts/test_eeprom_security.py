"""Compile actual EEPROM initialization with synthetic memory and sanitizers."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class EepromSecurityTests(unittest.TestCase):
    def test_unterminated_and_valid_persisted_identities(self):
        compiler = shutil.which("clang++") or shutil.which("g++")
        self.assertIsNotNone(compiler, "A C++ compiler is required")
        with tempfile.TemporaryDirectory(prefix="dtt-eeprom-security-") as directory:
            temp = Path(directory)
            (temp / "Arduino.h").write_text('''#pragma once
#include <cstdint>
#include <cstring>
#include <string>
struct String : std::string {
    using std::string::string;
    String(const std::string &value) : std::string(value) {}
    String substring(size_t begin, size_t end) const {
        return String(substr(begin, end - begin));
    }
};
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGD(...) ((void)0)
''')
            (temp / "EEPROM.h").write_text('''#pragma once
#include <array>
#include <cstring>
struct Memory {
    std::array<unsigned char, 200> bytes;
    bool begin(int) { return true; }
    template<class T> void get(int offset, T& value) {
        std::memcpy(&value, bytes.data() + offset, sizeof(value));
    }
    template<class T> void put(int offset, const T& value) {
        std::memcpy(bytes.data() + offset, &value, sizeof(value));
    }
    bool commit() { return true; }
};
extern Memory EEPROM;
''')
            (temp / "main.cpp").write_text('''#include "EEPROM.h"
#include "eeprom_service.h"
#include <cassert>
Memory EEPROM;
int main() {
    EEPROM.bytes.fill(0xff);
    initEEPROM();
    assert(trainerId.empty());
    assert(trainerIdShort.empty());
    assert(!isAlphaVersion);
    EEPROM.bytes.fill(0);
    const char id[] = "synthetic-trainer-0001";
    const char shortId[] = "TEST01";
    const int serial = 7;
    EEPROM.put(0, id);
    EEPROM.put(100, shortId);
    EEPROM.put(132, serial);
    EEPROM.bytes[110] = 1;
    initEEPROM();
    assert(trainerId == id);
    assert(trainerIdShort == shortId);
    assert(serialNumber == 7);
    assert(isAlphaVersion);
    toggleIsAlpha();
    assert(!isAlphaVersion);
    assert(EEPROM.bytes[110] == 0);
    EEPROM.bytes.fill(0xff);
    const std::string savedId(32, 'x');
    assert(saveToEEPROM(String(savedId), 9));
    assert(trainerId == savedId && trainerIdShort == "xxxxxx");
    initEEPROM();
    assert(trainerId == savedId);
    assert(trainerIdShort == "xxxxxx" && serialNumber == 9);
    assert(!isAlphaVersion && EEPROM.bytes[110] == 0);
}
''')
            executable = temp / "test-eeprom"
            subprocess.run([
                compiler, "-std=c++17", "-fsanitize=address,undefined",
                "-fno-omit-frame-pointer", "-I", str(temp),
                "-I", str(ROOT / "src/services"),
                str(ROOT / "src/services/eeprom_service.cpp"),
                str(temp / "main.cpp"), "-o", str(executable),
            ], check=True)
            subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    unittest.main()
