"""Exercise the actual queue flush with recoverable HTTP statuses and local ports."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent


class UploadQueuePolicyTests(unittest.TestCase):
    def test_recoverable_upload_rejections_keep_the_result(self):
        queue = (ROOT / "src/services/upload_queue.cpp").read_text(encoding="utf-8")
        fixture = (HERE / "fixture.cpp.in").read_text(encoding="utf-8")
        wifi = (ROOT / "src/wifiSettings.cpp").read_text(encoding="utf-8")
        source = fixture.replace("// ACTUAL_FLUSH", queue[queue.index("int flushUploadQueue() {"):])
        source = source.replace("// ACTUAL_ENQUEUE", queue[queue.index("bool enqueuePayload("):queue.index("int flushUploadQueue() {")])
        source = source.replace("// ACTUAL_FALLBACK", wifi[wifi.index("void startSaveResultsTask()"):wifi.index("void saveResultsTask(void* parameter)")])
        with tempfile.TemporaryDirectory(prefix="dtt-upload-policy-") as temp:
            cpp = Path(temp) / "policy.cpp"
            cpp.write_text(source, encoding="utf-8")
            binary = Path(temp) / "policy"
            subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "src"), "-I", str(ROOT / ".pio/libdeps/test_native/ArduinoJson/src"), str(cpp), "-o", str(binary)], check=True, capture_output=True, text=True)
            subprocess.run([str(binary)], check=True, capture_output=True, text=True)
        self.assertNotIn("response.c_str()", queue)
        self.assertIn('postJson("/training-completed", doc)', queue)


if __name__ == "__main__":
    unittest.main()
