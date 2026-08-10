from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ANDROID_SOURCE = REPOSITORY_ROOT / "COCBot/functions/Android/Android.au3"


class AndroidScreencapTransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = ANDROID_SOURCE.read_text(encoding="utf-8")

    def test_bluestacks_capture_uses_android_local_storage_and_adb_pull(self) -> None:
        self.assertIn(
            '$bUseBlueStacksInternalCapture = $g_sAndroidEmulator = "BlueStacks5"',
            self.source,
        )
        self.assertIn('"/data/local/tmp/mybot-screencap-"', self.source)
        self.assertIn(
            'AndroidAdbSendShellCommand("screencap """ & $sCaptureAndroidPath',
            self.source,
        )
        self.assertIn("Func _AndroidAdbPullCaptureFile(", self.source)
        self.assertIn("' pull \"' & $sAndroidFile", self.source)
        self.assertIn(
            '_AndroidAdbSendShellCommand("rm -f """ & $sCaptureAndroidPath',
            self.source,
        )

    def test_pull_is_bounded_and_stop_aware(self) -> None:
        helper = self.source.split(
            "Func _AndroidAdbPullCaptureFile(", maxsplit=1
        )[1].split("EndFunc", maxsplit=1)[0]
        self.assertIn("$wasRunState And Not $g_bRunState", helper)
        self.assertIn("__TimerDiff($hTimer) >= $iTimeout", helper)
        self.assertIn("ClosePipe($iPid", helper)
        self.assertIn("_WinAPI_GetExitCodeProcess($hProcess)", helper)

    def test_raw_capture_accepts_legacy_and_current_android_headers(self) -> None:
        self.assertIn(
            "$bRawFileSizeValid = $iSize = $ExpectedFileSize Or "
            "$iSize = $ExpectedFileSize + 4",
            self.source,
        )
        self.assertIn(
            "Dataspace-aware screencap header (Android 9+)",
            self.source,
        )
        self.assertIn(
            "_WinAPI_SetFilePointer($hFile, $iCaptureHeaderSize)",
            self.source,
        )

    def test_png_clones_are_disposed_after_dib_creation(self) -> None:
        self.assertEqual(
            self.source.count("_GDIPlus_BitmapDispose($hClone)"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
