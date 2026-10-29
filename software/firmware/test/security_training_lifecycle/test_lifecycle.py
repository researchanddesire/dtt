"""Native SML/cancellation tests with actual transition/guard/status source.

Tasks, sensors and HTTP are controlled host ports. No physical completion or
delivery is claimed; the unmodified lifecycle and state-machine rules run here.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent


def between(text, start, end):
    return text[text.index(start):text.index(end, text.index(start))]


class TrainingLifecycleTests(unittest.TestCase):
    def test_actual_transitions_cancel_stale_workers_without_completion(self):
        machine = (ROOT / "src/state/machine.h").read_text(encoding="utf-8")
        guards = (ROOT / "src/state/guards.hpp").read_text(encoding="utf-8")
        actions = (ROOT / "src/state/actions.hpp").read_text(encoding="utf-8")
        page = (ROOT / "src/pages/play/page.cpp").read_text(encoding="utf-8")
        ble = (ROOT / "src/services/rad_ble.cpp").read_text(encoding="utf-8")
        wifi = (ROOT / "src/wifiSettings.cpp").read_text(encoding="utf-8")
        source = (HERE / "fixture.cpp.in").read_text(encoding="utf-8")
        source = source.replace("// ACTUAL_STOP", between(page, "void stopTrainingRun()", "\nbool startTrainingTasks("))
        source = source.replace("// ACTUAL_ACTIONS", between(actions, "constexpr auto startTrainingRun =", "\ninline bool sessionLoadComplete"))
        source = source.replace("// ACTUAL_GUARDS", between(guards, "constexpr auto completedTrainingWorker", "\ntemplate <typename Event = done>\nconstexpr auto isSessionLoadComplete"))
        source = source.replace("// ACTUAL_CAPTURE", between(wifi, "std::unique_ptr<JsonDocument> captureCompletedResult()", "\nvoid persistAndUploadResult("))
        active = between(machine, '"play.idle"_s + on_entry<_>', "\n            #ifdef BYPASS_PLAY")
        grade = between(machine, '"play.grade"_s + on_entry<_>', '\n            "play.grade"_s + event<button_pressed>')
        source = source.replace("// ACTUAL_TRANSITIONS", active + "\n" + grade)
        state = between(ble, 'document["state"] = currentState;', "\n            break;")
        state = state.replace("#ifndef PROVISION", "").replace("#endif", "")
        source = source.replace("// ACTUAL_STATE_FIELDS", state)
        with tempfile.TemporaryDirectory(prefix="dtt-training-lifecycle-") as temp:
            directory = Path(temp)
            cpp = directory / "test.cpp"
            cpp.write_text(source, encoding="utf-8")
            binary = directory / "lifecycle"
            command = [os.environ.get("CXX", "c++"), "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "include"), "-I", str(ROOT / "src"), "-I", str(ROOT / "lib/TrainingTypes/src"), "-I", str(ROOT / ".pio/libdeps/test_native/ArduinoJson/src"), str(cpp), "-o", str(binary)]
            if "clang" in command[0]:
                command += ["-Wno-unknown-warning-option"]
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
                result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as error:
                print(error.stdout, error.stderr)
                raise
            self.assertIn("assertions passed", result.stdout)
            print(result.stdout.strip())

    def test_worker_ownership_and_notification_wiring(self):
        ble = (ROOT / "src/services/rad_ble.cpp").read_text(encoding="utf-8")
        page = (ROOT / "src/pages/play/page.cpp").read_text(encoding="utf-8")
        machine = (ROOT / "src/state/machine.h").read_text(encoding="utf-8")
        wifi = (ROOT / "src/wifiSettings.cpp").read_text(encoding="utf-8")
        worker = between(page, "void runDrawPlayModeTask(", "\nvoid runDistanceTask(")
        self.assertNotIn("process_event(done", worker)
        self.assertNotIn('stateMachine->is("play.idle"', worker)
        self.assertIn("training_worker_finished{generation}", worker)
        self.assertIn("trainingLifecycle.current(generation)", worker)
        self.assertIn("std::shared_ptr<SegmentBase> running", worker)
        self.assertIn("trainingLifecycle.reserveNotification", worker)
        self.assertNotIn("notifyTrainingTask", between(machine, '"init.idle"_s + event<button_pressed>', '\n            "init.idle"_s + sml::on_exit'))
        self.assertIn("saveCompletedResult", between(machine, '"play.grade"_s + on_entry', '\n            "play.grade"_s + event<button_pressed>'))
        capture = between(wifi, "std::unique_ptr<JsonDocument> captureCompletedResult()", "\nvoid persistAndUploadResult(")
        self.assertIn("TrainingGuard guard(trainingMutex)", capture)
        self.assertIn("TrainingState::END", capture)
        notification = between(wifi, "void notifyActualTraining(", "\n}  // namespace")
        self.assertEqual(notification.count('postJson("/training-started"'), 1)
        self.assertNotIn("for (", notification)
        self.assertIn('#ifdef BYPASS_PLAY\n    {"target_grade"', ble)
        bypass = between(ble, 'else if (path == "target.grade")', '\n#endif')
        self.assertIn('button_long_pressed{}', bypass)
        self.assertNotIn('done{}', bypass)



if __name__ == "__main__":
    unittest.main()
