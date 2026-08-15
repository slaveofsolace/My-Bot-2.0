import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8-sig")


def autoit_function(text: str, name: str) -> str:
    match = re.search(rf"(?ms)^Func {re.escape(name)}\b.*?^EndFunc\s+;==>{re.escape(name)}$", text)
    if not match:
        raise AssertionError(f"missing AutoIt function {name}")
    return match.group(0)


class TreasuryRouteStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.route = source("COCBot/functions/Run/TreasuryRoute.au3")
        cls.execution = source("COCBot/functions/Run/RunExecution.au3")
        cls.open_treasury = source("COCBot/functions/Run/OpenHomeTreasury.au3")

    def test_adapter_is_bounded_and_does_not_use_the_legacy_treasury_actuator(self) -> None:
        adapter = autoit_function(self.route, "TreasuryRouteRunAdapter")
        for forbidden in (
            "TreasuryCollect(",
            "LocateClanCastle",
            "ClearScreen",
            "ClickOkay",
            "ClickAway",
            "Random",
            "For ",
            "While ",
            "Until ",
        ):
            self.assertNotIn(forbidden, adapter)
        self.assertEqual(adapter.count('_TreasuryRouteIssue($oOutcome, "castle"'), 1)
        self.assertEqual(adapter.count('_TreasuryRouteIssue($oOutcome, "entry"'), 1)
        self.assertEqual(adapter.count('_TreasuryRouteIssue($oOutcome, "collect"'), 1)
        self.assertEqual(adapter.count('_TreasuryRouteIssue($oOutcome, "confirm"'), 1)
        self.assertIn("_TreasuryRouteFinishUnlessStopped", adapter)
        self.assertNotIn("Return _TreasuryRouteFinish(", adapter)
        self.assertIn("$TREASURY_STATE_CASTLE_SELECTED", adapter)

    def test_template_free_not_full_adapter_has_exact_context_and_no_transfer_input(self) -> None:
        selected = autoit_function(self.open_treasury, "_OpenHomeTreasurySelectedFrameReady")
        window = autoit_function(self.open_treasury, "_OpenHomeTreasuryWindowFrameReady")
        bars = autoit_function(self.open_treasury, "_OpenHomeTreasuryAllBarEndsGray")
        detect = autoit_function(self.open_treasury, "OpenHomeTreasuryDetectCollect")
        cleanup = autoit_function(self.open_treasury, "OpenHomeTreasuryCleanup")
        self.assertGreaterEqual(selected.count("_OpenHomePixelNear("), 7)
        self.assertGreaterEqual(window.count("_OpenHomePixelNear("), 8)
        self.assertGreaterEqual(bars.count("_OpenHomePixelNear("), 5)
        self.assertIn("$TREASURY_STATE_NOT_FULL", detect)
        self.assertIn("$TREASURY_STATE_COLLECT_MISSING", detect)
        self.assertEqual(autoit_function(self.open_treasury, "OpenHomeTreasuryIssueCollect").count("Return False"), 1)
        self.assertEqual(autoit_function(self.open_treasury, "OpenHomeTreasuryIssueConfirm").count("Return False"), 1)
        self.assertIn("#OpenHomeTreasuryClose", cleanup)
        for forbidden in ("findButton(", "findMultiple(", "DllCallMyBot(", "ClickOkay(", "LocateClanCastle(", "Gem("):
            self.assertNotIn(forbidden, self.open_treasury)

    def test_live_recognition_is_exact_and_refuses_full_home_storage(self) -> None:
        castle = autoit_function(self.execution, "_TreasuryLiveDetectCastle")
        entry = autoit_function(self.execution, "_TreasuryLiveDetectEntry")
        collect = autoit_function(self.execution, "_TreasuryLiveDetectCollect")
        confirm = autoit_function(self.execution, "_TreasuryLiveDetectConfirm")
        self.assertIn("IsMainPage(1)", castle)
        self.assertIn("_CaptureRegions()", castle)
        self.assertIn("$aIsGoldFull", castle)
        self.assertIn("$aIsElixirFull", castle)
        self.assertIn("$aIsDarkElixirFull", castle)
        self.assertIn("$g_bNoCapturePixel", castle)
        self.assertIn("$g_aiClanCastlePos", castle)
        self.assertNotIn("LocateClanCastle", castle)
        self.assertIn('findButton("Treasury", Default, 1, True)', entry)
        self.assertIn("$aTreasuryWindow", collect)
        self.assertIn('findButton("Collect", Default, 1, True)', collect)
        self.assertIn("$aTreasuryWindow", confirm)
        self.assertIn('findButton("Okay", Default, 1, True)', confirm)

    def test_live_inputs_are_receipted_contextual_and_never_use_gems(self) -> None:
        functions = [
            "_TreasuryLiveIssueCastle",
            "_TreasuryLiveIssueEntry",
            "_TreasuryLiveIssueCollect",
            "_TreasuryLiveIssueConfirm",
            "_TreasuryLiveCleanup",
        ]
        bodies = "\n".join(autoit_function(self.execution, name) for name in functions)
        self.assertIn("BuildingClick", autoit_function(self.execution, "_TreasuryLiveIssueCastle"))
        self.assertIn("Local $bIssued = Click(", autoit_function(self.execution, "_TreasuryLiveIssueConfirm"))
        self.assertIn("Return $bIssued", autoit_function(self.execution, "_TreasuryLiveIssueConfirm"))
        self.assertIn("CloseWindow2(1, 200)", autoit_function(self.execution, "_TreasuryLiveCleanup"))
        for forbidden in ("ClickOkay(", "ClickAway(", "Gem(", "LocateClanCastle", "TreasuryCollect("):
            self.assertNotIn(forbidden, bodies)

    def test_events_report_issued_input_not_a_confirmed_resource_transfer(self) -> None:
        event_log = source("COCBot/functions/Run/RunEventLog.au3")
        confirmed = autoit_function(event_log, "RunEventLogMaintenanceTreasuryConfirmIssued")
        self.assertIn("maintenance.treasury.confirm-issued", confirmed)
        self.assertIn("transfer_confirmed=false", confirmed)
        self.assertNotIn("maintenance.treasury.completed", event_log)


if __name__ == "__main__":
    unittest.main()
