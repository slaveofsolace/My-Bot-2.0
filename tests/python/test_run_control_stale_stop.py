from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def autoit_function(text: str, name: str) -> str:
    start = text.index(f"Func {name}(")
    return text[start : text.index("EndFunc", start)]


class RunControlStaleStopTests(unittest.TestCase):
    def test_poll_consumes_new_start_before_applying_stale_stop(self) -> None:
        bridge = source("COCBot/functions/Run/RunControlBridge.au3")
        poll = autoit_function(bridge, "RunControlPoll")
        consume = poll.index("_RunControlConsumeCommand()")
        apply_stop = poll.index("If $g_bRunControlStopRequested Then $g_bRunState = False")
        self.assertLess(consume, apply_stop)
        self.assertIn("fresh Start command", poll)
        self.assertEqual(poll.count("If $g_bRunControlStopRequested Then $g_bRunState = False"), 1)


if __name__ == "__main__":
    unittest.main()
