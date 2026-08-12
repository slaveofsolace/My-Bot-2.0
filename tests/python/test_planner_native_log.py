import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("planner_ui_native_log", ROOT / "tools" / "planner_ui.py")
PLANNER_UI = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PLANNER_UI)


class PlannerNativeLogTests(unittest.TestCase):
    def test_latest_normal_profile_log_is_selected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles = Path(temp_dir)
            logs = profiles / "MyVillage" / "Logs"
            logs.mkdir(parents=True)
            older = logs / "2026-08-11_20.00.00.log"
            newer = logs / "2026-08-11_21.00.00.log"
            attack = logs / "AttackLog-2026-08.log"
            older.write_text("old\n", encoding="utf-8")
            newer.write_text("new\n", encoding="utf-8")
            attack.write_text("attack\n", encoding="utf-8")
            os.utime(older, (1, 1))
            os.utime(newer, (2, 2))
            os.utime(attack, (3, 3))
            with mock.patch.object(PLANNER_UI, "PROFILES_ROOT", profiles):
                self.assertEqual(PLANNER_UI.native_log_path("MyVillage"), newer)

    def test_profile_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(PLANNER_UI, "PROFILES_ROOT", Path(temp_dir)):
                for profile in ("../MyVillage", "..", ".", "bad/name", ""):
                    self.assertIsNone(PLANNER_UI.native_log_path(profile))

    def test_payload_is_bounded_and_uses_active_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles = Path(temp_dir)
            logs = profiles / "MyVillage" / "Logs"
            logs.mkdir(parents=True)
            path = logs / "2026-08-11_21.00.00.log"
            path.write_text("\n".join(f"line-{i}" for i in range(PLANNER_UI.MAX_NATIVE_LOG_LINES + 20)), encoding="utf-8")
            with mock.patch.object(PLANNER_UI, "PROFILES_ROOT", profiles), \
                    mock.patch.object(PLANNER_UI, "control_status", return_value={"profile": "MyVillage"}), \
                    mock.patch.object(PLANNER_UI, "displayed_path", side_effect=lambda value: value.name):
                payload = PLANNER_UI.native_log_payload()
            self.assertTrue(payload["available"])
            self.assertTrue(payload["truncated"])
            self.assertNotIn("line-0\n", payload["text"])
            self.assertIn(f"line-{PLANNER_UI.MAX_NATIVE_LOG_LINES + 19}", payload["text"])

    def test_ui_demotes_raw_log_to_collapsed_diagnostics(self):
        html = (ROOT / "ui" / "planner.html").read_text(encoding="utf-8")
        js = (ROOT / "ui" / "planner.js").read_text(encoding="utf-8")
        diagnostics = html.split('id="viewDiagnostics"', 1)[1]
        self.assertIn('<details class="raw-log" id="rawLogDetails">', diagnostics)
        self.assertNotIn('<dialog', html)
        self.assertNotIn('id="openNativeLog"', html)
        self.assertIn('id="downloadNativeLog"', html)
        self.assertIn("$('rawLogDetails').addEventListener('toggle'", js)
        self.assertIn("document.activeElement === output", js)


if __name__ == "__main__":
    unittest.main()
