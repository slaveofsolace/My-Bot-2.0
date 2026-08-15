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
        click = body.index('If Click($iCollectX, $iCollectY')
        stop_poll = body.rfind("If _Sleep(1) Then Return", 0, click)
        state_gate = body.rfind("If Not $g_bRunState Then Return SetExtended($iCollectorClicks, False)", 0, click)
        page_gate = body.rfind("If Not IsMainPage() Then Return SetExtended($iCollectorClicks, False)", 0, click)
        click_count = body.index("Then $iCollectorClicks += 1", click)
        self.assertEqual([stop_poll, state_gate, page_gate, click, click_count], sorted([stop_poll, state_gate, page_gate, click, click_count]))
        self.assertGreater(stop_poll, click - 300)

    def test_common_click_reports_only_an_accepted_input_command(self) -> None:
        click = function_body(source("COCBot/functions/Other/Click.au3"), "Click")
        android_click = function_body(source("COCBot/functions/Android/Android.au3"), "AndroidClick")
        minitouch = function_body(source("COCBot/functions/Android/Android.au3"), "AndroidMinitouchClick")
        self.assertIn("If TestCapture() Then Return False", click)
        self.assertIn("If RunPacingGateAction() Then Return False", click)
        self.assertIn("Return SetError($iAndroidError, $iAndroidExtended, $bAndroidIssued = True)", click)
        self.assertIn("Return $bIssued", click)
        self.assertIn("Return AndroidMinitouchClick", android_click)
        self.assertIn("Return False ; if need to clear screen do not click", minitouch)
        self.assertIn("Return True", minitouch)

    def test_loot_cart_polls_stop_before_irreversible_collect_button(self) -> None:
        body = function_body(source("COCBot/functions/Village/Collect.au3"), "CollectLootCart")
        click = body.index("ClickP($aiCollectButton)")
        stop_poll = body.rfind("If _Sleep(1) Then Return", 0, click)
        self.assertGreater(stop_poll, click - 120)

    def test_donation_entry_and_each_unit_type_fail_closed_when_stopped(self) -> None:
        text = source("COCBot/functions/Village/DonateCC.au3")
        self.assertIn("If Not $g_bRunState Then Return", function_body(text, "DonateCC")[:100])
        for name in ("DonateTroopType", "DonateSpellType", "DonateSiegeType"):
            body = function_body(text, name)
            self.assertIn("If Not $g_bRunState Or", body[:700], name)

    def test_donation_loops_poll_each_click_and_account_only_emitted_commands(self) -> None:
        text = source("COCBot/functions/Village/DonateCC.au3")
        expected_clicks = {
            "DonateTroopType": "PureClickTrain(",
            "DonateSpellType": "Click($g_iDonationWindowX + 43 + ($Slot * 68), $g_iDonationWindowY + 324",
            "DonateSiegeType": "Click($g_iDonationWindowX + 43 + ($Slot * 68), $g_iDonationWindowY + 117",
        }
        for name, click_token in expected_clicks.items():
            body = function_body(text, name)
            loop = body.index("Local $iDonated = 0")
            click = body.index(click_token, loop)
            poll = body.rfind("If _Sleep(1) Then ExitLoop", loop, click)
            increment = body.index("$iDonated += 1", click)
            assign = body.index("$Quant = $iDonated", increment)
            zero_return = body.index("If $Quant = 0 Then Return", assign)
            self.assertGreater(poll, loop, name)
            self.assertLess(click, increment, name)
            self.assertLess(increment, assign, name)
            self.assertLess(assign, zero_return, name)

    def test_spell_debug_capture_cannot_record_a_fake_donation(self) -> None:
        body = function_body(source("COCBot/functions/Village/DonateCC.au3"), "DonateSpellType")
        debug = body.index("If $g_bDebugOCRdonate Then", body.index("Spells Condition Matched"))
        debug_end = body.index("EndIf", debug)
        self.assertIn("Return", body[debug:debug_end])

    def test_laboratory_upgrade_polls_stop_and_restores_uncommitted_time(self) -> None:
        body = function_body(source("COCBot/functions/Village/Laboratory.au3"), "LaboratoryUpgrade")
        self.assertIn("If Not $debug And Not $g_bRunState Then Return False", body[:160])
        final_click = body.index('Click(630, 545 + $g_iMidOffsetY, 1, 120, "#0202")')
        stop_poll = body.rfind("If _Sleep(1) Then", 0, final_click)
        restore = body.rfind("$g_sLabUpgradeTime = $sPreviousLabUpgradeTime", 0, final_click)
        self.assertGreater(stop_poll, final_click - 320)
        self.assertGreater(restore, stop_poll)
        self.assertIn("$g_iLaboratoryElixirCost = $iPreviousLaboratoryElixirCost", body[restore:final_click])
        self.assertIn("$g_iLaboratoryDElixirCost = $iPreviousLaboratoryDElixirCost", body[restore:final_click])

    def test_builder_base_upgrade_confirmation_polls_stop(self) -> None:
        text = source("COCBot/functions/Village/BuilderBase/SuggestedUpgrades.au3")
        main = function_body(text, "MainSuggestedUpgradeCode")
        self.assertIn("If Not $g_bRunState Then Return False", main[:100])
        upgrade = function_body(text, "GetUpgradeButton")
        self.assertIn("If Not $g_bRunState Then Return False", upgrade[:100])
        final_click = upgrade.index("ClickP($aUpgradeButton)")
        stop_poll = upgrade.rfind("If _Sleep(1) Then Return False", 0, final_click)
        self.assertGreater(stop_poll, final_click - 100)

    def test_builder_base_new_building_confirmations_poll_stop(self) -> None:
        body = function_body(source("COCBot/functions/Village/BuilderBase/SuggestedUpgrades.au3"), "NewBuildings")
        self.assertIn("If Not $g_bRunState Then Return False", body[:100])
        confirmations = [match.start() for match in re.finditer(r'QuickMIS\("BC1", \$g_sImgAutoUpgradeNewBldgYes', body)]
        self.assertEqual(3, len(confirmations))
        for confirmation in confirmations:
            click = body.index("Click($g_iQuickMISX, $g_iQuickMISY)", confirmation)
            stop_poll = body.rfind("If _Sleep(1) Then Return False", confirmation, click)
            self.assertGreater(stop_poll, confirmation)


if __name__ == "__main__":
    unittest.main()
