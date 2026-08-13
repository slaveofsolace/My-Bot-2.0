import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import planner_ui  # noqa: E402


class ControlHealthAttachmentTest(unittest.TestCase):
    def _status(self, **values):
        document = {
            "schema_version": 1,
            "state": "idle",
            "message": "Native engine is ready",
            "emulator_attached": False,
            "window_attached": False,
            "adb_ready": False,
            "game_ready": False,
            **values,
        }
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "run-control-status.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            path.touch()
            with mock.patch.object(planner_ui, "CONTROL_STATUS_PATH", path):
                return planner_ui.control_status()

    def test_server_rejects_server_only_adb_health_without_an_attached_device(self):
        status = self._status(adb_ready=True, game_ready=True)
        self.assertTrue(status["connected"])
        self.assertFalse(status["window_attached"])
        self.assertFalse(status["adb_ready"])
        self.assertFalse(status["game_ready"])

    def test_server_accepts_health_only_after_native_attachment(self):
        status = self._status(window_attached=True, adb_ready=True, game_ready=True)
        self.assertTrue(status["window_attached"])
        self.assertTrue(status["adb_ready"])
        self.assertTrue(status["game_ready"])

    def test_primary_window_state_wins_over_a_contradictory_legacy_alias(self):
        status = self._status(window_attached=False, emulator_attached=True, adb_ready=True, game_ready=True)
        self.assertFalse(status["window_attached"])
        self.assertFalse(status["adb_ready"])
        self.assertFalse(status["game_ready"])

    def test_stale_attachment_cannot_remain_ready(self):
        with mock.patch.object(planner_ui, "CONTROL_STATUS_MAX_AGE_SECONDS", -1):
            status = self._status(window_attached=True, adb_ready=True, game_ready=True)
        self.assertFalse(status["connected"])
        self.assertFalse(status["window_attached"])
        self.assertFalse(status["adb_ready"])
        self.assertFalse(status["game_ready"])

    def test_native_and_browser_contracts_require_attachment_before_readiness(self):
        bridge = (ROOT / "COCBot/functions/Run/RunControlBridge.au3").read_text(encoding="utf-8-sig")
        browser = (ROOT / "ui/planner.js").read_text(encoding="utf-8")
        self.assertIn(
            "Local $bWindowAttached = IsHWnd($g_hAndroidWindow) And "
            "WinExists($g_hAndroidWindow) = 1 And WinGetProcess($g_hAndroidWindow) > 0",
            bridge,
        )
        self.assertIn("Local $bAdbReady = $bWindowAttached And $g_bAndroidInitialized", bridge)
        self.assertIn("Local $bGameReady = $bAdbReady And $g_bRunState And $g_bMainWindowOk", bridge)
        self.assertIn("const adbReady = windowAttached && CONTROL.adb_ready === true", browser)
        self.assertIn("const gameReady = adbReady && CONTROL.game_ready === true", browser)


if __name__ == "__main__":
    unittest.main()
