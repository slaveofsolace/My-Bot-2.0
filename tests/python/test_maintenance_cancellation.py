from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def function_body(text: str, name: str) -> str:
    match = re.search(rf"(?ms)^Func {re.escape(name)}\([^\r\n]*\)\s*(.*?)^EndFunc", text)
    if not match:
        raise AssertionError(f"function not found: {name}")
    return match.group(1)


class MaintenanceCancellationTests(unittest.TestCase):
    def test_normal_auto_upgrade_never_forces_or_restores_running_state(self) -> None:
        body = function_body(source("COCBot/functions/Village/Auto Upgrade.au3"), "AutoUpgrade")
        self.assertIn("If Not $bTest And Not $g_bRunState Then Return False", body)
        self.assertIn("If $bTest Then $g_bRunState = True", body)
        self.assertIn("If $bTest Then $g_bRunState = $bWasRunState", body)
        self.assertNotRegex(body, r"(?m)^\s*\$g_bRunState\s*=\s*True\s*$")
        self.assertNotRegex(body, r"(?m)^\s*\$g_bRunState\s*=\s*\$bWasRunState\s*$")

    def test_upgrade_worker_fails_closed_and_polls_before_spending(self) -> None:
        body = function_body(source("COCBot/functions/Village/Auto Upgrade.au3"), "_AutoUpgrade")
        state_gate = body.index("If Not $g_bRunState Or Not $g_bAutoUpgradeEnabled Then Return False")
        first_click = body.index("Click(")
        self.assertLess(state_gate, first_click)
        final_click = body.index("Click(630, 540 + $g_iMidOffsetY)")
        stop_poll = body.rfind("If _Sleep(1) Then Return False", 0, final_click)
        self.assertGreater(stop_poll, final_click - 160)

    def test_collectors_poll_stop_after_recognition_and_before_click(self) -> None:
        body = function_body(source("COCBot/functions/Village/Collect.au3"), "Collect")
        click = body.index('If IsMainPage() Then Click($aCollectXY[$t][0], $aCollectXY[$t][1]')
        stop_poll = body.rfind("If _Sleep(1) Then Return", 0, click)
        self.assertGreater(stop_poll, click - 200)

    def test_loot_cart_polls_stop_before_irreversible_collect_button(self) -> None:
        body = function_body(source("COCBot/functions/Village/Collect.au3"), "CollectLootCart")
        click = body.index("ClickP($aiCollectButton)")
        stop_poll = body.rfind("If _Sleep(1) Then Return", 0, click)
        self.assertGreater(stop_poll, click - 120)


if __name__ == "__main__":
    unittest.main()
