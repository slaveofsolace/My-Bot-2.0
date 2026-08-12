from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ANDROID_SOURCE = REPOSITORY_ROOT / "COCBot/functions/Android/Android.au3"


class AndroidScreencapTransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = ANDROID_SOURCE.read_text(encoding="utf-8")

    def test_bluestacks_capture_uses_private_png_transport(self) -> None:
        self.assertIn(
            '$bUseBlueStacksInternalCapture = $g_sAndroidEmulator = "BlueStacks5"',
            self.source,
        )
        self.assertIn(
            "$bCapturePng = $g_bAndroidAdbScreencapPngEnabled Or "
            "$bUseBlueStacksInternalCapture",
            self.source,
        )
        self.assertIn('@TempDir & "\\MyBot.run-Capture\\"', self.source)
        self.assertIn(
            '"/data/local/tmp/mybot-screencap-" & @AutoItPID & ".png"',
            self.source,
        )
        self.assertIn(
            '"screencap " & ($bCapturePng ? "-p " : "")',
            self.source,
        )
        self.assertIn("Func _AndroidAdbPullCaptureFile(", self.source)
        self.assertIn("' pull \"' & $sAndroidFile", self.source)
        self.assertIn(
            '_AndroidAdbSendShellCommand("rm -f """ & $sCaptureAndroidPath',
            self.source,
        )

    def test_png_capture_validates_frame_and_has_bounded_retry(self) -> None:
        self.assertIn(
            "$g_iAndroidAdbScreencapWidth <> $g_iAndroidClientWidth Or "
            "$g_iAndroidAdbScreencapHeight <> $g_iAndroidClientHeight",
            self.source,
        )
        self.assertIn(
            "$iPngRetryLimit = ($bUseBlueStacksInternalCapture ? 2 : 10)",
            self.source,
        )
        self.assertIn(
            "$hPngFile = FileOpen($sHostCaptureFile, 16)",
            self.source,
        )
        self.assertIn(
            "$hBitmap = __GDIPlus_BitmapCreateFromMemory($dPngData)",
            self.source,
        )
        self.assertLess(
            self.source.index("FileDelete($sHostCaptureFile)"),
            self.source.index("__GDIPlus_BitmapCreateFromMemory($dPngData)"),
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
        self.assertEqual(self.source.count("_GDIPlus_BitmapDispose($hClone)"), 2)
        self.assertNotIn(
            "_GDIPlus_ImageDispose($g_hAndroidAdbScreencapBufferPngHandle)",
            self.source,
        )
        self.assertNotIn(
            "_WinAPI_DeleteObject($g_hAndroidAdbScreencapBufferPngHandle)",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
