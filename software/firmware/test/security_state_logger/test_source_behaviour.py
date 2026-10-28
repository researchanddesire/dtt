"""Check actual state logger avoids quiet-build type names and retains debug logs."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class StateLoggerTests(unittest.TestCase):
    def test_type_names_follow_the_enabled_diagnostic_level(self):
        with tempfile.TemporaryDirectory(prefix="dtt-state-logger-") as directory:
            temporary = Path(directory)
            (temporary / "boost").mkdir()
            (temporary / "Arduino.h").write_text('''#pragma once
#include <cstring>
#define ARDUHAL_LOG_LEVEL_NONE 0
#define ARDUHAL_LOG_LEVEL_ERROR 1
#define ARDUHAL_LOG_LEVEL_WARN 2
#define ARDUHAL_LOG_LEVEL_INFO 3
#define ARDUHAL_LOG_LEVEL_DEBUG 4
#define ARDUHAL_LOG_LEVEL_VERBOSE 5
#define ARDUHAL_LOG_LEVEL CORE_DEBUG_LEVEL
''')
            (temporary / "boost/sml.hpp").write_text('''#pragma once
inline unsigned typeNames = 0;
namespace boost { namespace sml { namespace aux {
template <class T> const char *get_type_name() {
    ++typeNames;
    return T::name;
}
} } }
''')
            (temporary / "esp_log.h").write_text('''#pragma once
inline unsigned logs = 0;
template<class... Args> void diagnosticLog(Args...) { ++logs; }
#define ESP_LOGD(...) do { if constexpr (ARDUHAL_LOG_LEVEL >= 4) diagnosticLog(__VA_ARGS__); } while (0)
#define ESP_LOGV(...) do { if constexpr (ARDUHAL_LOG_LEVEL >= 5) diagnosticLog(__VA_ARGS__); } while (0)
''')
            (temporary / "main.cpp").write_text('''#include <cassert>
#include "utils/StateLogger.h"
struct Machine { static constexpr const char *name = "machine"; };
struct Event { static constexpr const char *name = "event"; };
struct Guard { static constexpr const char *name = "guard"; };
struct Action {};
struct State { const char *c_str() const { return "state"; } };
int main() {
    StateLogger::log_process_event<Machine>(Event{});
    StateLogger::log_guard<Machine>(Guard{}, Event{}, true);
    StateLogger::log_action<Machine>(Action{}, Event{});
    StateLogger::log_state_change<Machine>(State{}, State{});
    if constexpr (ARDUHAL_LOG_LEVEL < 4) {
        assert(typeNames == 0 && logs == 0);
    } else if constexpr (ARDUHAL_LOG_LEVEL == 4) {
        assert(typeNames == 4 && logs == 3);
    } else {
        assert(typeNames == 7 && logs == 6);
    }
}
''')
            for level in range(6):
                with self.subTest(level=level):
                    executable = temporary / f"logger-{level}"
                    subprocess.run([
                        os.environ.get("CXX", "c++"), "-std=c++17",
                        "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        f"-DCORE_DEBUG_LEVEL={level}",
                        "-I", str(temporary), "-I", str(ROOT / "src"),
                        str(temporary / "main.cpp"), "-o", str(executable),
                    ], check=True)
                    subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    unittest.main()
