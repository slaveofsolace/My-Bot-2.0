import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OBSTACLES = (ROOT / "COCBot" / "functions" / "Main Screen" / "checkObstacles.au3").read_text(
    encoding="utf-8-sig"
)
SLEEP = (ROOT / "COCBot" / "functions" / "Other" / "_Sleep.au3").read_text(encoding="utf-8-sig")


def function_body(source: str, name: str) -> str:
    start = source.index(f"Func {name}(")
    return source[start : source.index("EndFunc", start)]


class RecoveryCancellationTests(unittest.TestCase):
    def test_reload_polls_stop_before_capture_or_process_mutation(self):
        body = function_body(OBSTACLES, "checkObstacles_ReloadCoC")
        diagnostic = body.index('If TestCapture() Then Return "Reload CoC"')
        cancellation = body.index("If _Sleep(1) Then", diagnostic)
        capture = body.index("ForceCaptureRegion(True)")
        self.assertLess(diagnostic, cancellation)
        self.assertLess(cancellation, capture)

        shared_prefs = body.index("PushSharedPrefs()")
        open_game = body.index("OpenCoC()")
        self.assertIn("If _Sleep(1) Then Return True", body[shared_prefs:open_game])

        close_game = body.index("CloseCoC(True)")
        self.assertIn("If _Sleep(1) Then Return True", body[capture:close_game])

    def test_reboot_polls_stop_before_capture_and_reboot(self):
        body = function_body(OBSTACLES, "checkObstacles_RebootAndroid")
        diagnostic = body.index('If TestCapture() Then Return "Reboot Android"')
        first_poll = body.index("If _Sleep(1) Then", diagnostic)
        capture = body.index("ForceCaptureRegion(True)")
        reboot = body.index("CheckAndroidReboot()")
        self.assertLess(diagnostic, first_poll)
        self.assertLess(first_poll, capture)
        self.assertIn("If _Sleep(1) Then Return True", body[capture:reboot])

    def test_return_home_recovery_clicks_are_cancellable(self):
        completed = OBSTACLES.index('findButton("ReturnHome", Default, 1, True, False, False)')
        old_attack_chrome = OBSTACLES.index("If _CheckPixel($aNoCloudsAttack", completed)
        completed_body = OBSTACLES[completed:old_attack_chrome]
        self.assertLess(completed_body.index("If _Sleep(1) Then Return True"), completed_body.index("ClickP("))

        surrender = OBSTACLES.index("If _CheckPixel($aSurrenderButton")
        surrender_body = OBSTACLES[surrender : OBSTACLES.index("EndIf", surrender)]
        self.assertLess(surrender_body.index("If _Sleep(1) Then Return True"), surrender_body.index("ReturnHome("))

    def test_sleep_polls_control_bridge_before_run_state_exit(self):
        poll = SLEEP.index('If IsFunc("RunControlPoll") Then Call("RunControlPoll")')
        exit_gate = SLEEP.index("If $CheckRunState And Not $g_bRunState Then")
        self.assertLess(poll, exit_gate)


if __name__ == "__main__":
    unittest.main()
