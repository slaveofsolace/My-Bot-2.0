import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import planner_ui  # noqa: E402


def clan_request_plan() -> dict:
    plan = planner_ui.default_plan()
    plan.update(
        {
            "run.surface": "regular",
            "run.strategy": "home.clan-request",
            "run.attack_script": "profile-current",
            "run.town_hall": 0,
            "run.heroes": [],
            "run.duration_minutes": 0,
            "run.max_battles": 0,
            "run.stop_on_star_bonus": False,
            "run.max_failures": 0,
            "run.diagnostic_mode": True,
            "run.diagnostic_note": "supervised Clan request fixture",
            "target.gold": 0,
            "target.elixir": 0,
            "target.dark_elixir": 0,
            "army.source": "recipe",
            "army.recipe_name": "",
            "army.manage_training": False,
            "army.wait_for_full": False,
            "army.train_spells": False,
            "army.train_sieges": False,
            "search.min_gold": 0,
            "search.min_elixir": 0,
            "search.min_dark": 0,
            "search.max_seconds": 0,
            "search.town_hall_filter": "any",
            "pacing.retry_attempts": 0,
            "pacing.break_every_minutes": 0,
            "donate.mode": "off",
            "donate.keep_army": True,
            "donate.max_per_run": 0,
            "donate.request_when_short": True,
            "events.clan_games": False,
            "events.clan_games_point_cap": 0,
            "events.laboratory": "off",
            "events.collect_resources": False,
            "events.collect_loot_cart": False,
            "events.collect_treasury": False,
            "upgrade.policy": "disabled",
            "account.queue": "",
            "runtime.emulator": "bluestacks5",
            "runtime.instance": "Pie64",
            "notify.channel": "log-only",
        }
    )
    return plan


def function_body(source: str, name: str) -> str:
    match = re.search(rf"(?ms)^Func {re.escape(name)}\b.*?^EndFunc\s+;==>{re.escape(name)}$", source)
    if not match:
        raise AssertionError(f"missing AutoIt function {name}")
    return match.group(0)


class ClanRequestRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.route = (ROOT / "COCBot/functions/Run/ClanRequestRoute.au3").read_text(encoding="utf-8")
        cls.execution = (ROOT / "COCBot/functions/Run/RunExecution.au3").read_text(encoding="utf-8")
        cls.contract = (ROOT / "COCBot/functions/Run/RunExecutionContract.au3").read_text(encoding="utf-8")
        cls.run_bot = (ROOT / "MyBot.run.au3").read_text(encoding="utf-8")
        cls.gui_action = (ROOT / "COCBot/MBR GUI Action.au3").read_text(encoding="utf-8")

    def test_contract_is_request_only_and_exactly_bound(self) -> None:
        validate = function_body(self.route, "ClanRequestRouteValidate")
        for token in (
            '$CLAN_REQUEST_ROUTE_STRATEGY = "home.clan-request"',
            '$oPlan.Item("donate_mode")',
            'Not $oPlan.Item("donate_request_when_short")',
            '$oPlan.Item("events_collect_resources")',
            '$oPlan.Item("events_collect_loot_cart")',
            '$oPlan.Item("events_collect_treasury")',
            '$oPlan.Item("events_clan_games")',
            '$oPlan.Item("army_manage_training")',
            '$oPlan.Item("upgrade_policy")',
            '$oPlan.Item("account_queue_id")',
            '$oPacing.Item("retry_attempts")',
            '$sEmulator = "auto" Or $sInstance = ""',
            'exact active profile/account binding',
        ):
            self.assertIn(token, self.route if token.startswith("$CLAN") else validate)
        self.assertIn("ClanRequestRouteValidate", self.contract)

    def test_start_binds_and_runtime_rechecks_current_profile(self) -> None:
        prepare = function_body(self.execution, "RunExecutionPrepareStart")
        execute = function_body(self.execution, "ClanRequestRouteExecute")
        binder = function_body(self.execution, "RunExecutionBindCurrentProfileForHomeRoute")
        self.assertLess(prepare.index("RunExecutionBindCurrentProfileForHomeRoute"), prepare.index("RunIntentCanStart"))
        self.assertIn("RunIntentSetProfile", binder)
        self.assertIn("$g_sProfileCurrentName", binder)
        self.assertIn("ClanRequestRouteAccountMatches($g_oRunExecutionIntent, $g_sProfileCurrentName)", execute)

    def test_adapter_latches_one_send_after_immediate_stop_poll(self) -> None:
        adapter = function_body(self.route, "ClanRequestRouteRunAdapter")
        stop_index = adapter.index('Call($sStopRequestedCallback)', adapter.index("Fresh Send button"))
        attempt_index = adapter.index('$oOutcome.Item("send_attempts") = 1')
        send_index = adapter.index("Call($sIssueSendCallback")
        receipt_index = adapter.index('$oOutcome.Item("send_issued") = True')
        self.assertLess(stop_index, attempt_index)
        self.assertLess(attempt_index, send_index)
        self.assertLess(send_index, receipt_index)
        self.assertEqual(adapter.count("Call($sIssueSendCallback"), 1)
        self.assertIn('$oOutcome.Item("send_attempts") = 1', adapter)
        self.assertIn("Available did not transition to AlreadyMade", adapter)
        cancel = function_body(self.route, "_ClanRequestRouteCancel")
        self.assertNotIn("Close", cancel)
        self.assertNotIn("Call(", cancel)
        self.assertIn("Stop requested after Send", adapter)

    def test_live_route_does_not_call_legacy_request_or_donation_logic(self) -> None:
        execute = function_body(self.execution, "ClanRequestRouteExecute")
        issue = function_body(self.execution, "_ClanRequestLiveIssueSend")
        open_overview = function_body(self.execution, "_ClanRequestLiveOpenArmyOverview")
        live_slice = execute + issue + open_overview
        self.assertNotIn("RequestCC(", live_slice)
        self.assertNotIn("DonateCC", live_slice)
        self.assertNotIn("CheckCCArmy", live_slice)
        self.assertNotIn("AndroidSendText", live_slice)
        self.assertNotIn("CheckHeroOrder", live_slice)
        self.assertNotIn("ZoomOut", live_slice)
        self.assertIn('OpenArmyOverview(True, "ClanRequestRoute", False)', open_overview)
        self.assertEqual(issue.count("Click("), 1)
        self.assertIn('Return Click(Int($iSendX), Int($iSendY), 1, 120, "#ClanRequestSend")', issue)

    def test_profile_request_flag_is_snapshotted_applied_and_restored(self) -> None:
        capture = function_body(self.execution, "_RunExecutionCaptureProfileSnapshot")
        apply_intent = function_body(self.execution, "_RunExecutionApplyIntent")
        restore = function_body(self.execution, "_RunExecutionRestoreProfile")
        self.assertIn("$g_bRunExecutionSnapshotRequestTroopsEnable = $g_bRequestTroopsEnable", capture)
        clan_branch = apply_intent[
            apply_intent.index("If $sStrategy = $CLAN_REQUEST_ROUTE_STRATEGY Then") :
            apply_intent.index("EndIf", apply_intent.index("If $sStrategy = $CLAN_REQUEST_ROUTE_STRATEGY Then"))
        ]
        self.assertIn("$g_bRequestTroopsEnable = True", clan_branch)
        self.assertIn("$g_bChkDonate = False", clan_branch)
        self.assertIn("$g_bDonateLikeCrazy = False", clan_branch)
        self.assertIn("$g_bRequestTroopsEnable = $g_bRunExecutionSnapshotRequestTroopsEnable", restore)

    def test_stop_paths_do_not_invoke_cleanup_callback_after_latch(self) -> None:
        adapter = function_body(self.route, "ClanRequestRouteRunAdapter")
        cancel = function_body(self.route, "_ClanRequestRouteCancel")
        close_live = function_body(self.execution, "_ClanRequestLiveCloseAndProveHome")
        self.assertNotIn("Call(", cancel)
        self.assertNotIn("CloseWindow2", cancel)
        self.assertIn("If _ClanRequestLiveStopRequested() Then Return False", close_live)
        for detail in (
            "Stop requested after Send",
            "Stop requested during the Send attempt",
            "Stop requested while reading post-send state",
            "Stop requested after post-send observation",
        ):
            pos = adapter.index(detail)
            terminal = adapter.index("Return $oOutcome", pos)
            self.assertNotIn("sCloseAndProveHomeCallback", adapter[pos:terminal])

    def test_request_waits_are_control_polled_not_raw_sleep(self) -> None:
        for name in (
            "_ClanRequestLiveOpenArmyOverview",
            "_ClanRequestLiveDetectState",
            "_ClanRequestLiveOpenDialog",
            "_ClanRequestLiveCloseAndProveHome",
        ):
            body = function_body(self.execution, name)
            self.assertNotRegex(body, r"(?m)^\s*Sleep\(")
        self.assertIn("_Sleep(250, True, True, False)", self.execution)
        self.assertIn("_Sleep(300, True, False, False)", self.execution)

    def test_dispatch_is_terminal_before_generic_paths(self) -> None:
        run_bot = function_body(self.run_bot, "runBot")
        clan = run_bot.index("If ClanRequestRouteActive() Then")
        passive = run_bot.index("If RunExecutionPlanActive() And Not RunExecutionShouldManageTraining() Then")
        generic = run_bot.index("InitiateSwitchAcc()")
        self.assertLess(clan, passive)
        self.assertLess(clan, generic)
        self.assertIn("ClanRequestRouteExecute()", run_bot[clan:passive])
        self.assertIn("Return", run_bot[clan:passive])

        bot_start = function_body(self.gui_action, "BotStart")
        request_dispatch = bot_start.index("ClanRequestRouteSelected($oPreparedIntent)")
        managed_probe = bot_start.index("MBRFuncProbeEngine")
        self.assertLess(request_dispatch, managed_probe)
        self.assertIn("_BotStartOpenClanRequest", bot_start[request_dispatch:managed_probe])

    def test_open_request_path_never_enters_generic_or_managed_startup(self) -> None:
        open_request = function_body(self.gui_action, "_BotStartOpenClanRequest")
        for forbidden in (
            "MBRFunc",
            "ForumAuthentication",
            "ResumeAndroid",
            "SaveConfig",
            "readConfig",
            "applyConfig",
            "OpenAndroid",
            "Initiate(",
            "btnStop",
        ):
            self.assertNotIn(forbidden, open_request)
        self.assertIn("RunExecutionApplyPrepared", open_request)
        self.assertIn("OpenHomeCollectorsProveHome", open_request)
        self.assertIn("ClanRequestRouteRunAdapter", open_request)
        self.assertIn("RunExecutionComplete", open_request)
        self.assertIn("RunControlReportOneShotOutcome", open_request)

    def test_event_schema_has_truthful_terminal_states(self) -> None:
        schema = json.loads((ROOT / "config/run-event.schema.json").read_text(encoding="utf-8"))
        event_types = schema["properties"]["type"]["enum"]
        for event_type in (
            "maintenance.clan-request.started",
            "maintenance.clan-request.unavailable",
            "maintenance.clan-request.unconfirmed",
            "maintenance.clan-request.committed",
            "maintenance.clan-request.home-verified",
        ):
            self.assertIn(event_type, event_types)

    def test_truthful_request_plan_passes_server_preflight(self) -> None:
        self.assertEqual(planner_ui.engine_preflight(clan_request_plan()), [])

    def test_request_preflight_rejects_missing_send_authority_and_exact_instance(self) -> None:
        no_request = clan_request_plan()
        no_request["donate.request_when_short"] = False
        self.assertTrue(any("Request when available" in item for item in planner_ui.engine_preflight(no_request)))

        ambiguous = clan_request_plan()
        ambiguous["runtime.emulator"] = "auto"
        ambiguous["runtime.instance"] = ""
        self.assertTrue(any("exact non-Auto emulator and instance" in item for item in planner_ui.engine_preflight(ambiguous)))

        unsafe = clan_request_plan()
        unsafe["runtime.instance"] = "Pie64&wrong"
        self.assertTrue(any("unsupported characters" in item for item in planner_ui.engine_preflight(unsafe)))

    def test_generated_metadata_exposes_gated_request_only_route_and_wording(self) -> None:
        metadata = json.loads((ROOT / "config/ui/run-planner.settings.json").read_text(encoding="utf-8-sig"))
        settings = {
            setting["id"]: setting
            for section in metadata["sections"]
            for setting in section["settings"]
        }
        route = next(option for option in settings["run.strategy"]["options"] if option["value"] == "home.clan-request")
        self.assertEqual(route["availability"], "gated")
        self.assertFalse(route["runtime_verified"])
        self.assertEqual(settings["donate.request_when_short"]["label"], "Request when available")
        native_metadata = (ROOT / "COCBot/GUI/RunPlannerMetadata.generated.au3").read_text(encoding="utf-8-sig")
        self.assertIn('= "home.clan-request"', native_metadata)
        self.assertIn('= "Home maintenance - Clan request only"', native_metadata)

    def test_browser_has_unsaved_complete_request_safety_patch(self) -> None:
        browser = (ROOT / "ui/planner.js").read_text(encoding="utf-8")
        start = browser.index("'home.clan-request': {")
        end = browser.index("\n  },", start) + len("\n  },")
        patch = browser[start:end]
        for token in (
            "'donate.mode': 'off'",
            "'donate.keep_army': true",
            "'donate.request_when_short': true",
            "'events.collect_resources': false",
            "'events.collect_loot_cart': false",
            "'events.collect_treasury': false",
            "'pacing.retry_attempts': 0",
            "'pacing.break_every_minutes': 0",
        ):
            self.assertIn(token, patch)
        self.assertNotIn("runtime.emulator", patch)
        self.assertNotIn("runtime.instance", patch)


if __name__ == "__main__":
    unittest.main()
