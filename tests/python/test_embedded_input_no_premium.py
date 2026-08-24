from __future__ import annotations

import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
GUI_CONTROL = ROOT / "COCBot" / "MBR GUI Control.au3"


def autoit_function(source: str, name: str) -> str:
    match = re.search(rf"(?ms)^Func {re.escape(name)}\b.*?^EndFunc\b", source)
    if match is None:
        raise AssertionError(f"missing AutoIt function {name}")
    return match.group(0)


class EmbeddedInputNoPremiumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = GUI_CONTROL.read_text(encoding="utf-8-sig")
        cls.mouse_forwarder = autoit_function(source, "GUIControl_WM_MOUSE")
        cls.forwarder = autoit_function(source, "GUIControl_AndroidEmbedded")
        cls.wndproc = autoit_function(source, "frmBot_WNDPROC")

    def test_active_wndproc_routes_embedded_keys_only_to_fail_closed_forwarder(self) -> None:
        self.assertIn("$WM_KEYDOWN, $WM_KEYUP, $WM_SYSKEYDOWN, $WM_SYSKEYUP, $WM_MOUSEHWHEEL", self.wndproc)
        self.assertIn("GUIControl_AndroidEmbedded($hWin, $iMsg, $wParam, $lParam)", self.wndproc)
        for raw_sink in ("_WinAPI_PostMessage(", "_SendMessage(", "AndroidBackButton(", "ControlSend("):
            self.assertNotIn(raw_sink, self.wndproc)

    def test_embedded_key_system_key_and_wheel_forwarder_is_terminal_and_sink_free(self) -> None:
        self.assertLess(self.forwarder.index("TestCapture()"), self.forwarder.index("NoPremiumActionBlocked("))
        self.assertIn("embedded keyboard, system-key, and wheel game input is unavailable", self.forwarder)
        self.assertLess(self.forwarder.index("NoPremiumActionBlocked("), self.forwarder.rindex("Return $GUI_RUNDEFMSG"))
        for raw_sink in (
            "_WinAPI_PostMessage(",
            "_SendMessage(",
            "AndroidBackButton(",
            "AndroidAdbSendShellCommand(",
            "Minitouch(",
            "ControlSend(",
            "ControlClick(",
        ):
            self.assertNotIn(raw_sink, self.forwarder)

    def test_escape_key_has_no_special_bypass(self) -> None:
        self.assertNotIn("$wParam = 27", self.forwarder)
        self.assertNotIn("ADB back", self.forwarder)

    def test_embedded_mouse_wheel_and_alternate_buttons_are_terminal_and_sink_free(self) -> None:
        self.assertIn("If $iMsg = $WM_MOUSEMOVE Then", self.mouse_forwarder)
        self.assertIn("Hover remains a local diagnostic only", self.mouse_forwarder)
        self.assertIn(
            "embedded mouse, wheel, and alternate-button game input is unavailable",
            self.mouse_forwarder,
        )
        self.assertLess(
            self.mouse_forwarder.index("If $iMsg = $WM_MOUSEMOVE Then"),
            self.mouse_forwarder.index("NoPremiumActionBlocked("),
        )
        for raw_sink in (
            "_WinAPI_PostMessage(",
            "_SendMessage(",
            "AndroidAdbSendShellCommand(",
            "Minitouch(",
            "ControlSend(",
            "ControlClick(",
        ):
            self.assertNotIn(raw_sink, self.mouse_forwarder)


if __name__ == "__main__":
    unittest.main()
