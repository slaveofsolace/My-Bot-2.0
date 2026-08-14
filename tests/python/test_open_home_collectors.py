import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def autoit_function(text, name):
    match = re.search(rf"(?ms)^Func {re.escape(name)}\b.*?^EndFunc\s+;==>{re.escape(name)}$", text)
    if not match:
        raise AssertionError(f"missing AutoIt function {name}")
    return match.group(0)


class OpenHomeCollectorsTest(unittest.TestCase):
    def test_bypasses_restricted_engine_only_after_prepared_contract(self):
        action = source("COCBot/MBR GUI Action.au3")
        start = autoit_function(action, "BotStart")
        self.assertLess(start.index("RunExecutionPrepareStart"), start.index("OpenHomeCollectorsPreparedMode"))
        self.assertLess(start.index("OpenHomeCollectorsPreparedMode"), start.index("MBRFuncProbeEngine"))
        self.assertIn("If $iOpenCollectorsMode = -1 Then", start)

    def test_mode_is_exact_collectors_only_and_bluestacks_only(self):
        route = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        mode = autoit_function(route, "OpenHomeCollectorsPreparedMode")
        self.assertIn('events_collect_resources', mode)
        for field in (
            "events_collect_daily_reward",
            "events_collect_loot_cart",
            "events_collect_treasury",
        ):
            self.assertIn(field, mode)
        self.assertIn('<> "bluestacks5"', mode)
        self.assertIn("Return -1", mode)

    def test_adapter_is_template_free_and_has_no_spending_actuator(self):
        route = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        forbidden_calls = (
            "findImage(",
            "findMultiple(",
            "returnMultipleMatchesOwnVillage(",
            "MBRFunc(",
            "GemClick(",
            "BuildingClick(",
            "PureClick(",
            "OpenAndroid(",
            "RebootAndroid(",
            "TrainSystem(",
            "DonateCC(",
            "RequestCC(",
        )
        for token in forbidden_calls:
            self.assertNotIn(token, route)
        self.assertNotIn("$g_sImg", route)
        self.assertLess(route.index("ForceCaptureRegion()"), route.index("AndroidScreencap("))
        self.assertIn("AndroidScreencap(", route)
        self.assertEqual(route.count("Click("), 1)

    def test_every_click_is_bounded_by_stop_and_home_proof(self):
        route = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        collect = autoit_function(route, "OpenHomeCollectorsCollectOnePass")
        click = collect.index("If Not Click(")
        self.assertLess(collect.rindex("RunControlStopRequested()", 0, click), click)
        self.assertLess(collect.rindex("_CheckPixel($aIsMain, False)", 0, click), click)
        self.assertIn("OpenHomeCollectorsProveHome()", collect[click:])
        self.assertIn("For $iAction = 1 To 3", collect)
        self.assertIn("$aIssued[$iType] = True", collect)

    def test_start_path_requires_exact_existing_adb_surface(self):
        action = source("COCBot/MBR GUI Action.au3")
        runner = autoit_function(action, "_BotStartOpenHomeCollectors")
        for proof in (
            "HomeMaintenanceRouteAccountMatches",
            "WinGetAndroidHandle() = 0",
            "$g_bAndroidAdbScreencap",
            "$g_bAndroidAdbClick",
            "AndroidControlAvailable()",
            "GetBlueStacks5ModernAdbSurfacePosition()",
            "OpenHomeCollectorsProveHome()",
        ):
            self.assertIn(proof, runner)
        for forbidden in (
            "MBRFunc",
            "ForumAuthentication",
            "OpenAndroid",
            "InitiateLayout",
            "ZoomOut",
            "BotDetectFirstTime",
            "btnStop",
        ):
            self.assertNotIn(forbidden, runner)

    def test_terminal_outcome_restores_idle_without_legacy_stop(self):
        bridge = source("COCBot/functions/Run/RunControlBridge.au3")
        outcome = autoit_function(bridge, "RunControlReportOneShotOutcome")
        self.assertIn("$g_bRunState = False", outcome)
        self.assertIn("$g_iBotAction = $eBotNoAction", outcome)
        self.assertIn("$g_sRunControlActiveStartRequestId = \"\"", outcome)
        self.assertNotIn("BotStop", outcome)
        self.assertNotIn("ResumeAndroid", outcome)


if __name__ == "__main__":
    unittest.main()
