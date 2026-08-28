from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SLEEP = (ROOT / "COCBot" / "functions" / "Other" / "_Sleep.au3").read_text(encoding="utf-8-sig")
ACTION = (ROOT / "COCBot" / "MBR GUI Action.au3").read_text(encoding="utf-8-sig")
MAIN_SCREEN = (ROOT / "COCBot" / "functions" / "Main Screen" / "checkMainScreen.au3").read_text(
    encoding="utf-8-sig"
)
OPEN_HOME = (ROOT / "COCBot" / "functions" / "Run" / "OpenHomeCollectors.au3").read_text(
    encoding="utf-8-sig"
)
ANDROID = (ROOT / "COCBot" / "functions" / "Android" / "Android.au3").read_text(encoding="utf-8-sig")
MBR_FUNC = (ROOT / "COCBot" / "functions" / "Other" / "MBRFunc.au3").read_text(
    encoding="utf-8-sig"
)


def function_body(source: str, name: str) -> str:
    start = source.index(f"Func {name}(")
    return source[start : source.index("EndFunc", start)]


class CooperativeStopCheckpointTests(unittest.TestCase):
    def test_checkpoint_dynamically_polls_optional_bridge_and_fails_open_when_absent(self) -> None:
        checkpoint = function_body(SLEEP, "RunControlCheckpoint")
        poll_name = checkpoint.index('"RunControl" & "Poll"')
        poll_call = checkpoint.index("Call($sRunControlPollCallback)", poll_name)
        stop_name = checkpoint.index('"RunControl" & "StopRequested"', poll_call)
        stop_call = checkpoint.index("Call($sRunControlStopCallback)", stop_name)
        missing_bridge = checkpoint.index("If @error Then Return False", stop_call)
        explicit_stop = checkpoint.index("Return $vStopRequested = True", missing_bridge)
        self.assertEqual(
            [poll_name, poll_call, stop_name, stop_call, missing_bridge, explicit_stop],
            sorted((poll_name, poll_call, stop_name, stop_call, missing_bridge, explicit_stop)),
        )
        self.assertNotIn("IsFunc(", checkpoint)
        self.assertNotIn("$g_bRunState", checkpoint)

    def test_mixed_mode_checkpoint_queries_stop_even_when_optional_poll_is_absent(self) -> None:
        checkpoint = function_body(MBR_FUNC, "_MBRFuncStopCheckpoint")
        poll = checkpoint.index('Call("RunControl" & "Poll")')
        stop = checkpoint.index('Call("RunControl" & "StopRequested")', poll)
        error_gate = checkpoint.index("If @error Or Not $bStopRequested Then Return False", stop)
        result = checkpoint.index("Return True", error_gate)
        self.assertEqual([poll, stop, error_gate, result], sorted((poll, stop, error_gate, result)))
        self.assertNotIn("IsFunc(", checkpoint)

    def test_managed_initialization_is_bracketed_by_checkpoints(self) -> None:
        for function_name, call in (
            ("_BotCheckManagedEngine", "MBRFuncInitialize(False)"),
            ("BotStart", "MBRFuncInitialize()"),
        ):
            body = function_body(ACTION, function_name)
            initialize = body.index(call)
            before = body.rfind("RunControlCheckpoint()", 0, initialize)
            after = body.index("RunControlCheckpoint()", initialize)
            self.assertGreaterEqual(before, 0)
            self.assertLess(before, initialize)
            self.assertGreater(after, initialize)
            self.assertIn("RunControlStopRequested()", body[before:after + len("RunControlCheckpoint()")])

    def test_main_screen_capture_iterations_poll_before_and_after_capture(self) -> None:
        body = function_body(MAIN_SCREEN, "_checkMainScreen")
        loop = body.index("While True")
        capture = body.index("$bCaptureReady = _CaptureRegions()", loop)
        before = body.rfind("If RunControlCheckpoint() Then Return False", loop, capture)
        after = body.index("If RunControlCheckpoint() Then Return False", capture)
        exit_condition = body.index("If Not ($bCaptureReady And Not _checkMainScreenImage", after)
        self.assertEqual([loop, before, capture, after, exit_condition], sorted((loop, before, capture, after, exit_condition)))

    def test_current_client_capture_polls_and_disposes_cancelled_bitmap(self) -> None:
        body = function_body(OPEN_HOME, "OpenHomeCollectorsCapture")
        capture = body.index("AndroidScreencap(")
        before = body.rfind("RunControlCheckpoint()", 0, capture)
        after = body.index("RunControlCheckpoint()", capture)
        valid_bitmap = body.index("$iCaptureError = 0 And $hNewBitmap <> 0", after)
        dispose = body.index("GdiDeleteHBitmap($hNewBitmap)", after)
        cancelled = body.index("Return SetError(2, 0, False)", after)
        self.assertEqual(
            [before, capture, after, valid_bitmap, dispose, cancelled],
            sorted((before, capture, after, valid_bitmap, dispose, cancelled)),
        )

    def test_adb_wait_loops_poll_and_retain_running_operation_gate(self) -> None:
        shell = function_body(ANDROID, "_AndroidAdbSendShellCommand")
        shell_loop = shell.index("While @error = 0")
        shell_poll = shell.index("$bRunControlStopRequested = RunControlCheckpoint()", shell_loop)
        shell_gate = shell.index(
            "If $wasRunState And ($bRunControlStopRequested Or Not $g_bRunState) Then ExitLoop", shell_poll
        )
        shell_wait = shell.index("Sleep(10)", shell_gate)
        self.assertEqual(
            [shell_loop, shell_poll, shell_gate, shell_wait],
            sorted((shell_loop, shell_poll, shell_gate, shell_wait)),
        )

        pull = function_body(ANDROID, "_AndroidAdbPullCaptureFile")
        pull_loop = pull.index("Do")
        pull_poll = pull.index("$bRunControlStopRequested = RunControlCheckpoint()", pull_loop)
        pull_gate = pull.index(
            "If $wasRunState And ($bRunControlStopRequested Or Not $g_bRunState) Then", pull_poll
        )
        pull_wait = pull.index("_WinAPI_WaitForSingleObject", pull_gate)
        self.assertEqual(
            [pull_loop, pull_poll, pull_gate, pull_wait],
            sorted((pull_loop, pull_poll, pull_gate, pull_wait)),
        )


if __name__ == "__main__":
    unittest.main()
