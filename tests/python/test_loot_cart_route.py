from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8-sig")


def autoit_function(text: str, name: str) -> str:
    start = text.index(f"Func {name}(")
    return text[start : text.index("EndFunc", start)]


class LootCartRouteContractTests(unittest.TestCase):
    def test_state_machine_latches_exactly_one_open_and_collect_attempt(self) -> None:
        route = source("COCBot/functions/Run/LootCartRoute.au3")
        adapter = autoit_function(route, "LootCartRouteRunAdapter")
        self.assertEqual(adapter.count('$oOutcome.Item("cart_attempts") = 1'), 1)
        self.assertEqual(adapter.count('$oOutcome.Item("collect_attempts") = 1'), 1)
        self.assertIn("Stop requested immediately before Loot Cart Collect", adapter)
        self.assertIn("no post-input capture was attempted", adapter)
        self.assertIn("$LOOT_CART_OUTCOME_COLLECT_ISSUED", adapter)
        self.assertNotIn("$LOOT_CART_OUTCOME_COLLECTED", route)

    def test_route_never_invokes_legacy_chat_fallback_or_confirmation_paths(self) -> None:
        route = source("COCBot/functions/Run/LootCartRoute.au3")
        adapter = autoit_function(route, "LootCartRouteRunAdapter")
        for forbidden in (
            "CollectLootCart(",
            "ClickB(",
            "ClanChat",
            "CloseWindow",
            "PureClick",
            "Click(",
        ):
            self.assertNotIn(forbidden, adapter)
        self.assertNotRegex(adapter, r"\b(?:400|450|530)\s*,\s*(?:300|400|650)\b")

    def test_live_recognizers_require_exact_fresh_visual_targets(self) -> None:
        execution = source("COCBot/functions/Run/RunExecution.au3")
        detect_cart = autoit_function(execution, "_LootCartLiveDetectCart")
        issue_cart = autoit_function(execution, "_LootCartLiveIssueCart")
        detect_collect = autoit_function(execution, "_LootCartLiveDetectCollect")
        issue_collect = autoit_function(execution, "_LootCartLiveIssueCollect")
        prove_home = autoit_function(execution, "_LootCartLiveProveHome")

        self.assertIn("findMultiple($g_sImgCollectLootCart", detect_cart)
        self.assertIn('GetDiamondFromRect("0," & (180 + $g_iMidOffsetY) & ",150," & (320 + $g_iMidOffsetY))', detect_cart)
        self.assertIn('$sSearchArea, $sSearchArea, 0, 1000, 2', detect_cart)
        self.assertIn('"objectname,objectpoints", True', detect_cart)
        self.assertIn("_LootCartLiveParseCart($aCart)", detect_cart)
        parse_cart = autoit_function(execution, "_LootCartLiveParseCart")
        self.assertIn("If UBound($aMatches, 1) <> 1 Then Return 0", parse_cart)
        self.assertEqual(issue_cart.count("Click("), 1)
        self.assertIn("RunEventLogMaintenanceLootCartOpenIssued(1)", issue_cart)

        self.assertIn('findButton("CollectLootCart"', detect_collect)
        self.assertEqual(issue_collect.count("Click("), 1)
        self.assertIn("RunEventLogMaintenanceLootCartCollectIssued(1)", issue_collect)

        self.assertIn("ForceCaptureRegion()", prove_home)
        self.assertIn("IsMainPage(1)", prove_home)
        for forbidden in ("Click(", "CloseWindow", "ClickAway", "ReturnHome"):
            self.assertNotIn(forbidden, prove_home)

    def test_home_route_uses_new_adapter_and_keeps_legacy_loot_flag_disabled(self) -> None:
        execution = source("COCBot/functions/Run/RunExecution.au3")
        home = autoit_function(execution, "HomeMaintenanceRouteExecute")
        apply_intent_start = execution.index("A reviewed plan is closed-world")
        apply_intent_end = execution.index("Switch StringLower", apply_intent_start)
        reset = execution[apply_intent_start:apply_intent_end]

        self.assertIn("LootCartRouteRunAdapter", home)
        self.assertNotIn("CollectLootCart(", home)
        self.assertIn("$g_bChkCollectCartFirst = False", reset)
        self.assertIn("confirmation_inputs=0", source("COCBot/functions/Run/RunEventLog.au3"))
        self.assertIn("gem_conversion=false", source("COCBot/functions/Run/RunEventLog.au3"))


if __name__ == "__main__":
    unittest.main()
