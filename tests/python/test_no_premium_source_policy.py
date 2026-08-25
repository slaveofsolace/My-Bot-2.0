import re
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def autoit_function(text: str, name: str) -> str:
    match = re.search(rf"(?ms)^Func {re.escape(name)}\b.*?^EndFunc\b", text)
    if not match:
        raise AssertionError(f"missing AutoIt function {name}")
    return match.group(0)


def active_autoit(text: str) -> str:
    without_blocks = re.sub(r"(?ims)^\s*#cs\b.*?^\s*#ce\b.*?$", "", text)
    return "\n".join(line for line in without_blocks.splitlines() if not line.lstrip().startswith(";"))


def autoit_callers(text: str, callee: str) -> set[str]:
    callers: set[str] = set()
    current = "<top-level>"
    token = re.compile(rf"\b{re.escape(callee)}\(")
    for line in active_autoit(text).splitlines():
        declaration = re.match(r"\s*Func\s+(\w+)\b", line, re.IGNORECASE)
        if declaration:
            current = declaration.group(1)
            continue
        if re.match(r"\s*EndFunc\b", line, re.IGNORECASE):
            current = "<top-level>"
            continue
        if token.search(line):
            callers.add(current)
    return callers


class NoPremiumSourcePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.click = source("COCBot/functions/Other/Click.au3")
        cls.android = source("COCBot/functions/Android/Android.au3")
        cls.drag = source("COCBot/functions/Other/ClickDrag.au3")
        cls.policy = source("COCBot/functions/Run/NoPremiumPermitPolicy.au3")

    def test_policy_is_compile_time_enabled_and_terminal(self) -> None:
        self.assertIn("Global Const $NO_PREMIUM_POLICY_ENABLED = True", self.click)
        blocked = autoit_function(self.click, "NoPremiumActionBlocked")
        for token in (
            '$g_bNoPremiumPolicyTripped = True',
            'RunEventLogWrite("safety.premium-blocked"',
            'Assign("g_sRunExecutionMessage", $sMessage, $ASSIGN_FORCEGLOBAL)',
            "RunControlReportRunFailure($sMessage)",
            'Assign("g_bRunControlStopRequested", True, $ASSIGN_FORCEGLOBAL)',
            "$g_bRunState = False",
            "$g_iBotAction = $eBotStop",
            "RunControlWriteStatus(True)",
            'input_issued=false',
        ):
            self.assertIn(token, blocked)
        for forbidden in ("Click(", "ClickP(", "_ControlClick(", "AndroidClick(", "CloseWindow"):
            self.assertNotIn(forbidden, blocked)

    def test_passive_surface_recognizer_covers_gem_and_shop_anchors(self) -> None:
        recognizer = autoit_function(self.click, "NoPremiumSurfaceState")
        for anchor in (
            "$aIsGemWindow1",
            "$aIsGemWindow2",
            "$aIsGemWindow3",
            "$aIsGemWindow4",
            "$g_aShopWindowOpen",
        ):
            self.assertIn(anchor, recognizer)
        self.assertIn("$NO_PREMIUM_SURFACE_UNKNOWN", recognizer)
        for token in (
            "_GDIPlus_ImageGetWidth($g_hBitmap)",
            "_GDIPlus_ImageGetHeight($g_hBitmap)",
            "$iFrameWidth <> $g_iGAME_WIDTH",
            "$iFrameHeight <> $g_iGAME_HEIGHT",
            "premium-surface recognition frame is unavailable or non-canonical",
        ):
            self.assertIn(token, recognizer)
        for forbidden in ("Click(", "ClickP(", "CloseWindow", "isGemOpen(", "findButton(", "DllCall"):
            self.assertNotIn(forbidden, recognizer)

    def test_both_click_transports_gate_before_input(self) -> None:
        control = autoit_function(self.click, "_ControlClick")
        adb = autoit_function(self.android, "AndroidMinitouchClick")
        self.assertLess(control.index("TestCapture()"), control.index("NoPremiumPreInputGate"))
        self.assertLess(control.index("NoPremiumPreInputGate"), control.index("Return ControlClick("))
        self.assertLess(control.index("NoPremiumPreInputGate"), control.index("_SendMessage("))
        self.assertLess(adb.index("TestCapture()"), adb.index("NoPremiumPreInputGate"))
        self.assertLess(adb.index("NoPremiumPreInputGate"), adb.index("TCPSend($g_bAndroidAdbMinitouchSocket, $send)"))
        self.assertGreater(adb.index("NoPremiumPreInputGate"), adb.index("AndroidAdbLaunchShellInstance"))
        self.assertLess(adb.index("queued minitouch click cannot consume"), adb.index("NoPremiumPreInputGate"))

        gate = autoit_function(self.click, "NoPremiumPreInputGate")
        for token in (
            "Static $bEvaluating = False",
            "OpenHomeCollectorsCapture()",
            "$NO_PREMIUM_SURFACE_UNKNOWN",
            "NoPremiumSurfaceState($sReason, $sPermitAction, $iExpectedX, $iExpectedY)",
            "$g_bNoPremiumPolicyTripped",
        ):
            self.assertIn(token, gate)
        self.assertLess(gate.index("OpenHomeCollectorsCapture()"), gate.index("NoPremiumSurfaceState($sReason, $sPermitAction"))
        for forbidden in ("Click(", "ClickP(", "_ControlClick(", "AndroidClick(", "CloseWindow"):
            self.assertNotIn(forbidden, gate)

    def test_all_game_click_drag_and_swipe_transports_gate_before_input(self) -> None:
        wrappers = {
            "AndroidMinitouchClickDrag": (self.android, "TCPSend("),
            "AndroidSlowClick": (self.android, "AndroidAdbSendShellCommand("),
            "AndroidFastClick": (self.android, "_AndroidFastClick("),
            "AndroidInputSwipe": (self.android, "AndroidAdbSendShellCommand("),
            "_PostMessage_ClickDrag": (self.drag, "DllCall("),
        }
        for name, (text, sink) in wrappers.items():
            with self.subTest(wrapper=name):
                body = autoit_function(text, name)
                self.assertLess(body.index("TestCapture()"), body.index("NoPremiumPreInputGate"))
                self.assertLess(body.index("NoPremiumPreInputGate"), body.index(sink))

        disabled_multi_egress = {
            "AndroidAdbScript": "AndroidAdbSendShellCommandScript(",
            "AndroidSwipeNotWorking": "ReleaseClicks(",
        }
        for name, sink in disabled_multi_egress.items():
            with self.subTest(disabled_wrapper=name):
                body = autoit_function(self.android, name)
                self.assertLess(body.index("NoPremiumActionBlocked"), body.index(sink))

        manual = autoit_function(source("COCBot/MBR GUI Control.au3"), "GUIControl_WM_MOUSE")
        self.assertIn("If $iMsg = $WM_MOUSEMOVE Then", manual)
        self.assertIn("NoPremiumActionBlocked(", manual)
        for sink in (
            "Minitouch(",
            "_SendMessage(",
            "_WinAPI_PostMessage(",
            "AndroidAdbSendShellCommand(",
            "ControlSend(",
            "ControlClick(",
        ):
            self.assertNotIn(sink, manual)
        minitouch = autoit_function(self.android, "Minitouch")
        self.assertIn("If $iAction = 1 Then", minitouch)
        self.assertLess(minitouch.index("NoPremiumPreInputGate"), minitouch.index("TCPSend("))

        shortcuts = source("COCBot/functions/Android/AndroidMenuShortcuts.au3")
        for name in ("AndroidBackButton", "AndroidHomeButton"):
            body = autoit_function(shortcuts, name)
            self.assertLess(body.index("TestCapture()"), body.index("NoPremiumPreInputGate"))
            self.assertLess(body.index("NoPremiumPreInputGate"), body.index("AndroidAdbSendShellCommand("))

    def test_permits_are_positive_one_shot_and_no_route_is_silently_enabled(self) -> None:
        recognizer = autoit_function(self.click, "NoPremiumSurfaceState")
        grant = autoit_function(self.click, "NoPremiumGrantInputPermit")
        gate = autoit_function(self.click, "NoPremiumPreInputGate")
        for token in (
            "$NO_PREMIUM_ACTION_COLLECTOR_GOLD",
            "$NO_PREMIUM_ACTION_LOOT_CART_OPEN",
            "$NO_PREMIUM_ACTION_DAILY_REWARD_CLAIM",
            "$NO_PREMIUM_ACTION_TREASURY_CLOSE",
            "$NO_PREMIUM_ACTION_CLAN_REQUEST_SEND",
            "$NO_PREMIUM_ACTION_HOME_CLEAR_SCREEN",
            "$NO_PREMIUM_ACTION_STARTUP_POPUP_CLOSE",
            "no exact reviewed action and target permit",
        ):
            self.assertIn(token, recognizer)
        self.assertNotIn('Case "home"', recognizer)
        self.assertNotIn('Case "builder-home"', recognizer)
        for token in (
            "NoPremiumClearInputPermit()",
            "NoPremiumPermitActionKnown($sAction)",
            "NoPremiumPermitTargetValid($sAction, $iExpectedX, $iExpectedY)",
            "NoPremiumSurfaceState($sReason, $sAction, $iExpectedX, $iExpectedY)",
            "$g_sNoPremiumInputPermitAction = StringLower(String($sAction))",
            "$g_iNoPremiumInputPermitX = Int($iExpectedX)",
            "$g_iNoPremiumInputPermitY = Int($iExpectedY)",
            "TimerInit()",
        ):
            self.assertIn(token, grant)
        self.assertLess(grant.index("NoPremiumClearInputPermit()"), grant.index("OpenHomeCollectorsCapture()"))
        self.assertLess(gate.index("NoPremiumClearInputPermit()"), gate.index("OpenHomeCollectorsCapture()"))
        self.assertLess(gate.index("OpenHomeCollectorsCapture()"), gate.index("Return True"))
        self.assertIn("TimerDiff($hPermitTimer)", gate)
        self.assertIn("NoPremiumPermitPointMatches($iExpectedX, $iExpectedY, $iActualX, $iActualY)", gate)
        self.assertIn('StringLower(String($sTransport)) <> "window-control"', gate)
        self.assertIn('StringLower(String($sTransport)) <> "adb-minitouch-click"', gate)

        callers: list[str] = []
        for path in (ROOT / "COCBot").rglob("*.au3"):
            for line in active_autoit(path.read_text(encoding="utf-8-sig", errors="replace")).splitlines():
                if "NoPremiumGrantInputPermit(" in line and not re.match(r"\s*Func\s+NoPremiumGrantInputPermit\b", line):
                    callers.append(f"{path.relative_to(ROOT).as_posix()}:{line.strip()}")
        self.assertEqual(2, len(callers))
        self.assertTrue(all(item.startswith("COCBot/functions/Other/Click.au3:") for item in callers), callers)

    def test_reviewed_point_click_has_no_random_or_legacy_problem_cleanup_and_one_egress(self) -> None:
        reviewed = autoit_function(self.click, "NoPremiumPointClick")
        self.assertIn("RunPacingGateAction()", reviewed)
        self.assertLess(reviewed.index("RunPacingGateAction()"), reviewed.index("NoPremiumGrantInputPermit("))
        self.assertLess(reviewed.index("RunControlStopRequested()"), reviewed.index("NoPremiumGrantInputPermit("))
        self.assertGreaterEqual(reviewed.count("NoPremiumClearInputPermit()"), 3)
        self.assertEqual(2, reviewed.count("NoPremiumGrantInputPermit("))
        self.assertEqual(1, reviewed.count("AndroidClick("))
        self.assertEqual(1, reviewed.count("_ControlClick("))
        self.assertIn("AndroidClick(Int($iX), Int($iY), 1, $iSpeed, False)", reviewed)
        for forbidden in ("Random(", "isProblemAffect", "checkMainScreen"):
            self.assertNotIn(forbidden, reviewed)
        self.assertNotRegex(reviewed, r"(?<![A-Za-z_])Click\(")

        route_callers: dict[str, set[str]] = {}
        for relative in (
            "COCBot/functions/Run/OpenHomeCollectors.au3",
            "COCBot/functions/Run/OpenHomeTreasury.au3",
            "COCBot/functions/Run/OpenClanRequest.au3",
            "COCBot/functions/Run/OpenBuilderBaseCollectors.au3",
        ):
            text = source(relative)
            route_callers[relative] = autoit_callers(text, "NoPremiumPointClick")
        self.assertEqual(
            {
                "OpenHomeCollectorsCollectOnePass",
                "OpenHomeInactivityReloadIssue",
                "OpenHomeDailyRewardIssueClaim",
                "OpenHomeDailyRewardCloseAndProveHome",
                "OpenHomeLootCartIssueOpen",
                "OpenHomeLootCartIssueCollect",
            },
            route_callers["COCBot/functions/Run/OpenHomeCollectors.au3"],
        )
        self.assertEqual(
            {"OpenHomeTreasuryIssueCastle", "OpenHomeTreasuryIssueEntry", "OpenHomeTreasuryCleanup"},
            route_callers["COCBot/functions/Run/OpenHomeTreasury.au3"],
        )
        self.assertEqual(
            {
                "OpenClanRequestOpenArmyOverview",
                "OpenClanRequestOpenDialog",
                "OpenClanRequestIssueSend",
                "OpenClanRequestCloseAndProveHome",
            },
            route_callers["COCBot/functions/Run/OpenClanRequest.au3"],
        )
        self.assertEqual(
            {
                "OpenBuilderBaseSwitchToBuilder",
                "OpenBuilderBaseReturnHome",
                "OpenBuilderBaseCollectorsCollectOnePass",
            },
            route_callers["COCBot/functions/Run/OpenBuilderBaseCollectors.au3"],
        )
        self.assertEqual(
            {"_checkObstacles"},
            autoit_callers(source("COCBot/functions/Main Screen/checkObstacles.au3"), "NoPremiumPointClick"),
        )
        clan_request_active = active_autoit(source("COCBot/functions/Run/OpenClanRequest.au3"))
        self.assertNotRegex(clan_request_active, r"(?<![A-Za-z_])Click\(")

        all_callers: set[str] = set()
        for path in (ROOT / "COCBot").rglob("*.au3"):
            active = active_autoit(path.read_text(encoding="utf-8-sig", errors="replace"))
            if "NoPremiumPointClick(" in active and "Func NoPremiumPointClick(" not in active:
                all_callers.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            {
                "COCBot/functions/Run/OpenHomeCollectors.au3",
                "COCBot/functions/Run/OpenHomeTreasury.au3",
                "COCBot/functions/Run/OpenClanRequest.au3",
                "COCBot/functions/Run/OpenBuilderBaseCollectors.au3",
                "COCBot/functions/Main Screen/checkObstacles.au3",
            },
            all_callers,
        )

        clear = autoit_function(self.click, "NoPremiumClickAway")
        self.assertIn("$NO_PREMIUM_ACTION_HOME_CLEAR_SCREEN", clear)
        self.assertIn("NoPremiumPointClick(", clear)
        self.assertNotIn("Random(", clear)
        self.assertNotRegex(autoit_function(source("COCBot/functions/Image Search/IsWindowOpen.au3"), "ClearScreen"), r"(?<![A-Za-z_])ClickAway\(")

    def test_action_contract_is_exact_point_bound_and_rejects_generic_routes(self) -> None:
        known = autoit_function(self.policy, "NoPremiumPermitActionKnown")
        target = autoit_function(self.policy, "NoPremiumPermitTargetValid")
        point = autoit_function(self.policy, "NoPremiumPermitPointMatches")
        age = autoit_function(self.policy, "NoPremiumPermitAgeValid")
        self.assertEqual(23, len(re.findall(r'^Global Const \$NO_PREMIUM_ACTION_', self.policy, re.MULTILINE)))
        for forbidden in ('"home"', '"builder-home"', '"full-profile"', '"confirm"'):
            self.assertNotIn(forbidden, known)
        for exact in (
            "$iX = 431 And $iY = 608",
            "$iX = 759 And $iY = 173",
            "$iX = 281 And $iY = 418",
            "$iX = 574 And $iY = 608",
            "$iX = 699 And $iY = 182",
            "$iX = 39 And $iY = 585",
            "$iX = 761 And $iY = 498",
            "$iX = 545 And $iY = 478",
            "$iX = 316 And $iY = 478",
            "$iX = 792 And $iY = 187",
            "$iX = 145 And $iY = 620",
            "$iX >= 500 And $iX <= 530 And $iY >= 405 And $iY <= 435",
            "$iX >= 320 And $iX <= 350 And $iY >= 395 And $iY <= 420",
            "$iX = 821 And $iY = 465",
            "$iX >= 235 And $iX <= 245 And $iY >= 10 And $iY <= 30",
            "$iX >= 640 And $iX <= 650 And $iY >= 10 And $iY <= 30",
            "$iX >= 360 And $iX <= 510 And $iY >= 450 And $iY <= 540",
        ):
            self.assertIn(exact, target)
        self.assertIn("$NO_PREMIUM_ACTION_EXACT_TRAINING_ARMY", known)
        self.assertIn("$NO_PREMIUM_ACTION_BUILDER_SWITCH", known)
        self.assertIn("$NO_PREMIUM_ACTION_BUILDER_COLLECT_GOLD", known)
        self.assertIn("$NO_PREMIUM_ACTION_BUILDER_COLLECT_ELIXIR", known)
        self.assertIn("$NO_PREMIUM_ACTION_BUILDER_RETURN_HOME", known)
        self.assertIn("$NO_PREMIUM_ACTION_HOME_CLEAR_SCREEN", known)
        self.assertIn("$NO_PREMIUM_ACTION_STARTUP_POPUP_CLOSE", known)
        self.assertIn("Case $NO_PREMIUM_ACTION_EXACT_TRAINING_ARMY", target)
        self.assertIn("Case $NO_PREMIUM_ACTION_BUILDER_SWITCH", target)
        self.assertIn("Case $NO_PREMIUM_ACTION_BUILDER_COLLECT_GOLD", target)
        self.assertIn("Case $NO_PREMIUM_ACTION_BUILDER_COLLECT_ELIXIR", target)
        self.assertIn("Case $NO_PREMIUM_ACTION_BUILDER_RETURN_HOME", target)
        self.assertIn("Case $NO_PREMIUM_ACTION_HOME_CLEAR_SCREEN", target)
        self.assertIn("Case $NO_PREMIUM_ACTION_STARTUP_POPUP_CLOSE", target)
        self.assertIn("Int($iExpectedX) = Int($iActualX)", point)
        self.assertIn("Int($iExpectedY) = Int($iActualY)", point)
        self.assertIn("$iAgeMs >= 0", age)
        self.assertIn("$iAgeMs <= $NO_PREMIUM_INPUT_PERMIT_MAX_AGE_MS", age)

    def test_internal_adb_sinks_have_an_exact_reviewed_call_graph(self) -> None:
        self.assertEqual({"AndroidClick", "AndroidMinitouchClick"}, autoit_callers(self.android, "AndroidMinitouchClick"))
        self.assertEqual({"AndroidFastClick"}, autoit_callers(self.android, "_AndroidFastClick"))
        self.assertEqual({"_AndroidFastClick"}, autoit_callers(self.android, "AndroidFastClick"))
        self.assertEqual(set(), autoit_callers(self.android, "AndroidSlowClick"))
        self.assertEqual({"AndroidZoomOut"}, autoit_callers(self.android, "AndroidAdbScript"))
        self.assertEqual(
            {"AndroidClickDrag", "AndroidMinitouchClickDrag"},
            autoit_callers(self.android, "AndroidMinitouchClickDrag"),
        )

    def test_one_permit_cannot_authorize_multi_click_or_retry_egress(self) -> None:
        for name in ("Click", "PureClick", "PureClickTrain"):
            body = autoit_function(self.click, name)
            self.assertIn("$times > 1", body)
            self.assertLess(body.index("$times > 1"), body.index("_ControlClick(") if "_ControlClick(" in body else body.index("AndroidClick("))

        for name in ("AndroidSlowClick", "AndroidFastClick", "AndroidMinitouchClick"):
            body = autoit_function(self.android, name)
            self.assertIn("$times > 1 Or $x = Default Or $y = Default", body)
            self.assertLess(body.index("$times > 1"), body.index("NoPremiumPreInputGate"))

        swipe = autoit_function(self.android, "AndroidInputSwipe")
        self.assertIn('AndroidAdbSendShellCommand("input swipe "', swipe)
        self.assertNotIn(";input tap", swipe)
        self.assertIn("Return AndroidFastClick(", autoit_function(self.android, "_AndroidFastClick"))
        self.assertIn("Return AndroidMinitouchClick(", autoit_function(self.android, "AndroidMinitouchClick"))

    def test_window_zoom_keyboard_wheel_and_click_fallbacks_are_disabled(self) -> None:
        zoom = source("COCBot/functions/Android/ZoomOut.au3")
        sinks = {
            "DefaultZoomOut": "ControlSend(",
            "ZoomOutCtrlWheelScroll": "ControlSend(",
            "ZoomOutCtrlClick": "ControlSend(",
            "AndroidOnlyZoomOut": "AndroidZoomOut(",
        }
        for name, sink in sinks.items():
            with self.subTest(wrapper=name):
                body = autoit_function(zoom, name)
                self.assertLess(body.index("TestCapture()"), body.index("NoPremiumActionBlocked"))
                self.assertLess(body.index("NoPremiumActionBlocked"), body.index(sink))

    def test_nox_raw_control_click_is_unreachable_window_chrome_only(self) -> None:
        nox = source("COCBot/functions/Android/AndroidNox.au3")
        redraw = autoit_function(nox, "RedrawNoxWindow")
        self.assertLess(redraw.index("Return SetError(1)"), redraw.index("ControlClick("))
        self.assertEqual(2, redraw.count("ControlClick("))
        self.assertEqual(2, redraw.count("$aPos[2] - 46, 18"))
        self.assertNotIn("$g_hAndroidControl", redraw)

    def test_no_transport_bypass_is_added_outside_reviewed_wrappers(self) -> None:
        control_callers: set[str] = set()
        raw_control_callers: set[str] = set()
        for path in (ROOT / "COCBot").rglob("*.au3"):
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            active = active_autoit(text)
            rel = path.relative_to(ROOT).as_posix()
            if "_ControlClick(" in active:
                control_callers.add(rel)
            if re.search(r"(?<!_)\bControlClick\(", active):
                raw_control_callers.add(rel)
            if rel != "COCBot/functions/Android/Android.au3":
                for bypass in ("AndroidMinitouchClick(", "AndroidSlowClick(", "AndroidFastClick(", 'input tap '):
                    self.assertNotIn(bypass, active, f"unreviewed ADB input bypass in {rel}")

        self.assertEqual(
            {
                "COCBot/functions/Android/ZoomOut.au3",
                "COCBot/functions/Other/Click.au3",
            },
            control_callers,
        )
        self.assertEqual(
            {
                "COCBot/functions/Android/AndroidNox.au3",
                "COCBot/functions/Other/Click.au3",
            },
            raw_control_callers,
        )

    def test_named_gem_click_helpers_have_no_input_sink(self) -> None:
        click_zone = source("COCBot/functions/Other/ClickZoneR.au3")
        for body in (autoit_function(self.click, "GemClick"), autoit_function(click_zone, "GemClickR")):
            self.assertIn("NoPremiumActionBlocked", body)
            for forbidden in ("_ControlClick(", "AndroidClick(", "ControlClick(", "_SendMessage("):
                self.assertNotIn(forbidden, body)

        gem_callers: set[str] = set()
        for path in (ROOT / "COCBot").rglob("*.au3"):
            active = "\n".join(
                line for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
                if not line.lstrip().startswith(";")
            )
            if "GemClick(" in active:
                gem_callers.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            {
                "COCBot/functions/Image Search/imglocCheckWall.au3",
                "COCBot/functions/Other/Click.au3",
            },
            gem_callers,
        )

    def test_gem_boost_confirmation_sinks_are_unreachable(self) -> None:
        barracks = autoit_function(source("COCBot/functions/Village/BoostBarracks.au3"), "BoostTrainBuilding")
        structure = autoit_function(source("COCBot/functions/Village/BoostStructure.au3"), "BoostStructure")
        self.assertLess(
            barracks.index("Return NoPremiumActionBlocked"),
            barracks.index("OpenArmyOverview"),
        )
        self.assertLess(
            structure.index("Return NoPremiumActionBlocked"),
            structure.index("BuildingClickP"),
        )
        self.assertNotIn("ClickP($aGemWindowBtn", barracks)
        self.assertNotIn('"#0464"', structure)

    def test_all_native_premium_boost_selectors_are_zero_disabled_and_nonpersisting(self) -> None:
        selectors = (
            "Barracks",
            "SpellFactory",
            "Workshop",
            "BarbarianKing",
            "ArcherQueen",
            "MinionPrince",
            "Warden",
            "Champion",
            "Everything",
        )
        read_config = autoit_function(source("COCBot/functions/Config/readConfig.au3"), "ReadConfig_600_22")
        apply_source = source("COCBot/functions/Config/applyConfig.au3")
        apply_policy = autoit_function(apply_source, "ApplyNoPremiumBoostPolicy")
        apply_config = autoit_function(apply_source, "ApplyConfig_600_22")
        gui = autoit_function(source("COCBot/GUI/MBR GUI Design Child Attack - Troops.au3"), "CreateTrainBoost")
        run_execution = source("COCBot/functions/Run/RunExecution.au3")
        for selector in selectors:
            with self.subTest(selector=selector):
                global_name = f"$g_iCmbBoost{selector}"
                control_name = f"$g_hCmbBoost{selector}"
                self.assertIn(f"{global_name} = 0", read_config)
                self.assertIn(f"{global_name} = 0", apply_policy)
                self.assertIn(control_name, apply_policy)
                self.assertRegex(
                    gui,
                    rf"(?s){re.escape(control_name)}\s*=\s*GUICtrlCreateCombo\(.*?GUICtrlSetData\(-1,\s*\"0\",\s*\"0\"\).*?GUICtrlSetState\(-1,\s*\$GUI_DISABLE\)",
                )
                self.assertNotIn(f"{global_name} = $g_iRunExecutionSnapshotCmbBoost{selector}", run_execution)
        self.assertEqual(2, apply_config.count("ApplyNoPremiumBoostPolicy()"))
        self.assertIn("$GUI_DISABLE", apply_policy)
        for selector in selectors:
            self.assertNotIn(f"_GUICtrlComboBox_GetCurSel($g_hCmbBoost{selector})", apply_config)
        self.assertNotIn("Use with caution", gui)
        self.assertNotIn("with GEMS", gui)
        self.assertNotIn("No limit", gui)

    def test_sell_rewards_cannot_be_rearmed_or_confirmed(self) -> None:
        globals_source = source("COCBot/MBR Global Variables.au3")
        read_config = source("COCBot/functions/Config/readConfig.au3")
        save_config = source("COCBot/functions/Config/saveConfig.au3")
        apply_config = source("COCBot/functions/Config/applyConfig.au3")
        gui = source("COCBot/GUI/MBR GUI Design Child Village - Misc.au3")
        run_execution = source("COCBot/functions/Run/RunExecution.au3")
        rewards = autoit_function(
            source("COCBot/functions/Village/Personal Challenges/DailyChallenges.au3"),
            "CollectDailyRewards",
        )

        self.assertIn("Global $g_bChkSellRewards = False", globals_source)
        self.assertNotRegex(read_config, r"IniReadS\(\$g_bChkSellRewards\b")
        self.assertIn('_Ini_Add("other", "ChkSellRewards", 0)', save_config)
        self.assertNotIn("$g_bChkSellRewards = (GUICtrlRead", apply_config)
        self.assertNotIn("$g_bChkSellRewards = $g_bRunExecutionSnapshotChkSellRewards", run_execution)
        self.assertGreaterEqual(apply_config.count("$g_bChkSellRewards = False"), 1)
        self.assertIn("$GUI_DISABLE", apply_config)
        self.assertIn("$GUI_DISABLE", gui)
        self.assertNotIn("ClickP($aPersonalChallengeOkBtn", rewards)
        self.assertIn("ClickP($aPersonalChallengeCancelBtn", rewards)

    def test_known_offer_and_deal_routes_stop_without_input(self) -> None:
        obstacles = source("COCBot/functions/Main Screen/checkObstacles.au3")
        free_items = autoit_function(
            source("COCBot/functions/Village/FreeMagicItems.au3"),
            "CollectFreeMagicItems",
        )
        self.assertEqual(2, obstacles.count('FindImageInPlace2("SCOffers"'))
        self.assertEqual(2, obstacles.count('NoPremiumActionBlocked("store offer surface recognized'))
        self.assertNotIn("ClickP($aiSCOffer", obstacles)
        self.assertLess(free_items.index("NoPremiumActionBlocked"), free_items.index("ClearScreen()"))
        self.assertLess(free_items.index("NoPremiumActionBlocked"), free_items.index("OpenTraderWindow()"))

    def test_verified_nonpremium_fixtures_do_not_false_match_pixel_gate(self) -> None:
        anchors = (
            ((608, 240), (0xEB, 0x16, 0x17), 20),
            ((610, 246), (0xCD, 0x16, 0x1A), 20),
            ((625, 246), (0xCE, 0x15, 0x19), 20),
            ((640, 246), (0xCD, 0x15, 0x1C), 20),
            ((804, 54), (0xC0, 0x05, 0x08), 15),
        )

        def near(pixel: tuple[int, int, int], expected: tuple[int, int, int], tolerance: int) -> bool:
            return all(abs(actual - wanted) <= tolerance for actual, wanted in zip(pixel, expected))

        fixtures = sorted((ROOT / "tests/fixtures/current-client/images").glob("*.png"))
        self.assertTrue(fixtures)
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                with Image.open(fixture) as opened:
                    image = opened.convert("RGB")
                    matches = [near(image.getpixel(point), expected, tolerance) for point, expected, tolerance in anchors]
                self.assertFalse(matches[0] or all(matches[1:4]) or matches[4])


if __name__ == "__main__":
    unittest.main()
