import pathlib
import re
import struct
import unittest
import zlib


ROOT = pathlib.Path(__file__).resolve().parents[2]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def autoit_function(text, name):
    match = re.search(rf"(?ms)^Func {re.escape(name)}\b.*?^EndFunc\s+;==>{re.escape(name)}$", text)
    if not match:
        raise AssertionError(f"missing AutoIt function {name}")
    return match.group(0)


def png_rgb(path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("fixture is not PNG")
    offset = 8
    chunks = []
    width = height = color_type = None
    while offset < len(data):
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + size]
        offset += 12 + size
        if kind == b"IHDR":
            width, height, depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", payload)
            if depth != 8 or color_type not in (2, 6) or interlace != 0:
                raise AssertionError("unsupported fixture PNG format")
        elif kind == b"IDAT":
            chunks.append(payload)
        elif kind == b"IEND":
            break
    channels = 3 if color_type == 2 else 4
    packed = zlib.decompress(b"".join(chunks))
    stride = width * channels
    rows = []
    prior = bytearray(stride)
    cursor = 0
    for _ in range(height):
        filter_type = packed[cursor]
        cursor += 1
        row = bytearray(packed[cursor : cursor + stride])
        cursor += stride
        for index in range(stride):
            left = row[index - channels] if index >= channels else 0
            above = prior[index]
            upper_left = prior[index - channels] if index >= channels else 0
            if filter_type == 1:
                row[index] = (row[index] + left) & 0xFF
            elif filter_type == 2:
                row[index] = (row[index] + above) & 0xFF
            elif filter_type == 3:
                row[index] = (row[index] + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                estimate = left + above - upper_left
                distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
                predictor = (left, above, upper_left)[distances.index(min(distances))]
                row[index] = (row[index] + predictor) & 0xFF
            elif filter_type != 0:
                raise AssertionError(f"unsupported PNG filter {filter_type}")
        rows.append(row)
        prior = row

    def pixel(x, y):
        start = x * channels
        return tuple(rows[y][start : start + 3])

    return width, height, pixel


class OpenHomeCollectorsTest(unittest.TestCase):
    def test_bypasses_restricted_engine_only_after_prepared_contract(self):
        action = source("COCBot/MBR GUI Action.au3")
        start = autoit_function(action, "BotStart")
        self.assertLess(start.index("RunExecutionPrepareStart"), start.index("OpenHomeCollectorsPreparedMode"))
        self.assertLess(start.index("OpenHomeCollectorsPreparedMode"), start.index("MBRFuncProbeEngine"))
        self.assertIn("$iOpenCollectorsMode >= 1 And $iOpenCollectorsMode <= 4", start)
        self.assertIn("_BotStartRunOneShot($iOpenCollectorsMode, $sStartError)", start)
        self.assertIn("$iOpenCollectorsMode = -1", start)
        wrapper = autoit_function(action, "_BotStartRunOneShot")
        for mode, route in (
            (1, "_BotStartOpenHomeCollectors"),
            (2, "_BotStartOpenHomeLootCart"),
            (3, "_BotStartOpenDailyReward"),
            (4, "_BotStartOpenHomeTreasury"),
        ):
            self.assertIn(f"Case {mode}", wrapper)
            self.assertIn(f"{route}($sStartError)", wrapper)

    def test_mode_allows_exact_collectors_loot_cart_treasury_or_daily_reward_and_bluestacks_only(self):
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
        self.assertIn("$iSelected <> 1", mode)
        self.assertIn("$OPEN_HOME_MODE_REJECTED", mode)
        self.assertIn("$OPEN_HOME_MODE_LOOT_CART", mode)
        self.assertIn("$OPEN_HOME_MODE_DAILY_REWARD", mode)
        self.assertIn("$OPEN_HOME_MODE_TREASURY", mode)

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
        self.assertEqual(route.count("NoPremiumPointClick("), 10)

    def test_every_click_is_bounded_by_stop_and_home_proof(self):
        route = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        collect = autoit_function(route, "OpenHomeCollectorsCollectOnePass")
        click = collect.index("If Not NoPremiumPointClick(")
        self.assertLess(collect.rindex("RunControlStopRequested()", 0, click), click)
        self.assertLess(collect.rindex("_CheckPixel($aIsMain, False)", 0, click), click)
        self.assertIn("OpenHomeCollectorsProveHome()", collect[click:])
        self.assertIn("Func OpenHomeCollectorsCollectOnePass($iMaxClicks = 3)", collect)
        self.assertIn("Local $iClickLimit = Int($iMaxClicks)", collect)
        self.assertIn("If $iClickLimit < 1 Then $iClickLimit = 1", collect)
        self.assertIn("If $iClickLimit > 3 Then $iClickLimit = 3", collect)
        self.assertIn("For $iAction = 1 To $iClickLimit", collect)
        self.assertIn("$aIssued[$iType] = True", collect)
        self.assertIn("$iRequiredMask", collect)

        detect = autoit_function(route, "OpenHomeCollectorsDetect")
        self.assertIn("Step 3", detect)
        self.assertIn("$iRequiredMask", detect)
        self.assertIn("RunControlStopRequested()", detect)
        self.assertIn("Return SetError(2", detect)

    def test_home_proof_synchronizes_authoritative_game_readiness(self):
        route = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        proof = autoit_function(route, "OpenHomeCollectorsProveHome")
        self.assertIn("Local $bHomeProven = _CheckPixel($aIsMain, False)", proof)
        self.assertIn("$g_bMainWindowOk = $bHomeProven", proof)
        self.assertLess(proof.index("$g_bMainWindowOk = $bHomeProven"), proof.index("Return $bHomeProven"))

    def test_loot_cart_recognizer_matches_the_verified_home_fixture(self):
        width, height, pixel = png_rgb(ROOT / "tests/fixtures/current-client/images/home.maintenance.ready.png")
        self.assertEqual((width, height), (860, 732))
        expected = {
            (31, 246): 0xC3BDBA,
            (6, 249): 0xB7B0AA,
            (9, 244): 0x65635A,
            (18, 244): 0xB8B2AF,
            (13, 246): 0xBBB4B0,
            (20, 249): 0xBDB6B4,
            (15, 247): 0x75736C,
            (34, 249): 0x828273,
        }
        for point, color in expected.items():
            actual = pixel(*point)
            target = ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)
            self.assertTrue(all(abs(a - b) <= 36 for a, b in zip(actual, target)), (point, actual, target))

        route = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        cue = autoit_function(route, "_OpenHomeLootCartCueAt")
        for color in expected.values():
            self.assertIn(f"0x{color:06X}", cue)
        self.assertNotIn("ImgLoc", cue)

    def test_loot_cart_clicks_are_bounded_and_never_use_a_confirmation(self):
        route = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        issue_open = autoit_function(route, "OpenHomeLootCartIssueOpen")
        issue_collect = autoit_function(route, "OpenHomeLootCartIssueCollect")
        for function in (issue_open, issue_collect):
            click = function.index("NoPremiumPointClick(")
            self.assertLess(function.index("RunControlStopRequested()"), click)
            self.assertLess(function.index("Not $g_bRunState"), click)
            self.assertEqual(function.count("NoPremiumPointClick("), 1)
        self.assertIn("_CheckPixel($aIsMain, False)", issue_open)
        self.assertIn("OpenHomeLootCartCollectPanelReady()", issue_collect)
        self.assertIn("OpenHomeNoGemInputReady()", issue_open)
        self.assertIn("OpenHomeNoGemInputReady()", issue_collect)
        loot_scope = issue_open + issue_collect + autoit_function(route, "OpenHomeLootCartProveHome")
        self.assertNotIn("Okay", loot_scope)
        self.assertNotIn("Confirm", loot_scope)
        self.assertNotIn("isGemOpen(", loot_scope)
        self.assertNotIn("CloseWindow", loot_scope)

    def test_daily_reward_recognizer_matches_the_verified_positive_fixture(self):
        width, height, pixel = png_rgb(ROOT / "tests/fixtures/current-client/images/home.daily-reward.png")
        self.assertEqual((width, height), (860, 732))
        overlay = {
            (759, 173): (0xFFFFFF, 20),
            (746, 173): (0x616161, 36),
            (772, 173): (0x606060, 36),
            (759, 160): (0xACACAC, 36),
            (759, 186): (0x595959, 36),
            (430, 155): (0xA57315, 44),
            (80, 285): (0x844A00, 44),
        }
        claim = {
            (252, 326): (0xCAED87, 44),
            (342, 326): (0xCAED87, 44),
            (297, 310): (0xDEFF8D, 44),
            (297, 342): (0x6F9438, 44),
        }
        for point, (color, variation) in {**overlay, **claim}.items():
            actual = pixel(*point)
            target = ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)
            self.assertTrue(all(abs(a - b) <= variation for a, b in zip(actual, target)), (point, actual, target))

        route = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        overlay_source = autoit_function(route, "OpenHomeDailyRewardOverlayReady")
        claim_source = autoit_function(route, "_OpenHomeDailyRewardClaimCandidateReady")
        find_source = autoit_function(route, "OpenHomeDailyRewardFindClaim")
        for color, _variation in overlay.values():
            self.assertIn(f"0x{color:06X}", overlay_source)
        for color, _variation in claim.values():
            self.assertIn(f"0x{color:06X}", claim_source)
        self.assertIn("Local $aCandidates[7][2]", find_source)
        self.assertIn("[149, 485]", find_source)
        self.assertIn("[628, 483]", find_source)
        self.assertNotIn("[592, 485]", find_source)
        self.assertNotIn("[149, 477]", find_source)
        self.assertNotIn("ImgLoc", overlay_source + claim_source + find_source)

    def test_startup_daily_reward_blocker_reuses_claim_guard_before_battle_start(self):
        route = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        resolver = autoit_function(route, "OpenHomeStartupResolveDailyRewardBlocker")
        gui = source("COCBot/MBR GUI Action.au3")
        start = autoit_function(gui, "BotStart")
        self.assertIn("OpenHomeDailyRewardIssueClaim($aClaim[0], $aClaim[1])", resolver)
        self.assertIn("OpenHomeDailyRewardCloseAndProveHome($bCloseIssued)", resolver)
        self.assertIn("RunEventLogMaintenanceDailyRewardUnconfirmed", resolver)
        self.assertIn("OpenHomeStartupResolveDailyRewardBlocker($sStartupRewardOutcome, $sStartError)", start)
        self.assertLess(start.index("_BotEnsureConfiguredAndroidAndGame"), start.index("OpenHomeStartupResolveDailyRewardBlocker"))
        self.assertLess(start.index("OpenHomeStartupResolveDailyRewardBlocker"), start.index("MBRFuncInitialize"))

    def test_start_reject_reports_terminal_outcome_before_stop_teardown(self):
        gui = source("COCBot/MBR GUI Action.au3")
        reject = autoit_function(gui, "_BotStartReject")
        self.assertIn("RunControlReportStartOutcome(False, $sReason)", reject)
        self.assertIn("btnStop()", reject)
        lines = reject.splitlines()
        outcome_line = next(i for i, line in enumerate(lines) if line.strip() == "RunControlReportStartOutcome(False, $sReason)")
        stop_line = next(i for i, line in enumerate(lines) if line.strip().startswith("If $g_iBotAction") and "btnStop()" in line)
        self.assertLess(outcome_line, stop_line)

    def test_inactivity_reload_dialog_uses_clean_room_anchors_and_exact_point(self):
        route = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        predicate = autoit_function(route, "OpenHomeInactivityReloadDialogReady")
        issue = autoit_function(route, "OpenHomeInactivityReloadIssue")
        wait = autoit_function(route, "OpenHomeStartupRecoveryWait")
        for color in (0x424242, 0x689591, 0x67938F):
            self.assertIn(f"0x{color:06X}", predicate)
        self.assertIn("$NO_PREMIUM_ACTION_RECOVERY_RELOAD_GAME", issue)
        self.assertIn("$bRequireRunState = True", issue)
        self.assertIn("$bRequireRunState = True", wait)
        self.assertIn("281, 418", issue)
        self.assertIn("OpenHomeNoGemInputReady()", issue)
        self.assertIn("OpenHomeStartupRecoveryLaunchGame()", wait)
        self.assertIn('AndroidAdbSendShellCommand("am start -n "', route)
        self.assertNotIn("AndroidHomeButton", route)
        self.assertNotIn("ImgLoc", predicate + issue)
        for forbidden in ("Click(", "PureClick(", "GemClick("):
            self.assertNotIn(forbidden, issue.replace("NoPremiumPointClick(", ""))

    def test_daily_reward_inputs_are_fresh_bounded_and_never_confirm(self):
        route = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        issue = autoit_function(route, "OpenHomeDailyRewardIssueClaim")
        click = issue.index("NoPremiumPointClick(")
        self.assertLess(issue.index("OpenHomeDailyRewardCaptureClaim"), click)
        self.assertGreaterEqual(issue[:click].count("RunControlStopRequested()"), 2)
        self.assertIn("$iClaims <> 1", issue)
        self.assertEqual(issue.count("NoPremiumPointClick("), 1)
        self.assertIn('", False)', issue)
        self.assertNotIn('", True)', issue)

        cleanup = autoit_function(route, "OpenHomeDailyRewardCloseAndProveHome")
        close = cleanup.index("NoPremiumPointClick(")
        self.assertLess(cleanup.rindex("RunControlStopRequested()", 0, close), close)
        self.assertIn("OpenHomeCollectorsProveHome()", cleanup)
        self.assertIn("OpenHomeDailyRewardOverlayReady()", cleanup)
        self.assertIn("OpenHomeDailyRewardClaimedOverlayReady()", cleanup)
        self.assertEqual(cleanup.count("NoPremiumPointClick("), 1)
        self.assertIn('", False)', cleanup)
        self.assertNotIn('", True)', cleanup)
        for forbidden in ("Okay", "Confirm", "GemClick", "findMultiple", "findImage"):
            self.assertNotIn(forbidden, issue + cleanup)

    def test_selected_home_action_panel_cleanup_is_exact_and_no_gem_bounded(self):
        route = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        predicate = autoit_function(route, "OpenHomeSelectedActionPanelReady")
        cleanup = autoit_function(route, "OpenHomeClearSelectedActionPanel")

        for color in (0x387CB0, 0x4F93C7, 0xFFFFB7):
            self.assertIn(f"0x{color:06X}", predicate)
        self.assertIn("_CheckPixel($aIsMain, False)", predicate)
        self.assertIn("$NO_PREMIUM_ACTION_HOME_CLEAR_SELECTION", cleanup)
        self.assertIn("175, 10", cleanup)
        self.assertIn("OpenHomeNoGemInputReady()", cleanup)
        self.assertIn("OpenHomeSelectedActionPanelReady()", cleanup)
        self.assertIn('"#OpenHomeClearSelection", False)', cleanup)
        for forbidden in ("ClickAway", "Click(", "PureClick(", "GemClick(", "CloseWindow"):
            self.assertNotIn(forbidden, cleanup.replace("NoPremiumPointClick(", ""))

    def test_daily_reward_claimed_close_matches_the_verified_positive_fixture(self):
        width, height, pixel = png_rgb(
            ROOT / "tests/fixtures/current-client/images/home.daily-reward.claimed.png"
        )
        self.assertEqual((width, height), (860, 732))
        anchors = {
            (759, 173): (0xFFFFFF, 20),
            (746, 173): (0xF02328, 28),
            (772, 173): (0xF02227, 28),
            (759, 160): (0xF38F8D, 36),
            (759, 186): (0xDC2125, 28),
            (430, 155): (0xA57315, 44),
            (80, 285): (0x844A00, 44),
        }
        for point, (color, variation) in anchors.items():
            actual = pixel(*point)
            target = ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)
            self.assertTrue(all(abs(a - b) <= variation for a, b in zip(actual, target)), (point, actual, target))

        route = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        predicate = autoit_function(route, "OpenHomeDailyRewardClaimedOverlayReady")
        for color, _variation in anchors.values():
            self.assertIn(f"0x{color:06X}", predicate)
        self.assertNotIn("ImgLoc", predicate)

    def test_start_path_requires_exact_framebuffer_and_control_surface(self):
        action = source("COCBot/MBR GUI Action.au3")
        runner = autoit_function(action, "_BotStartOpenHomeCollectors")
        for proof in (
            "HomeMaintenanceRouteAccountMatches",
            "_BotOpenHomeEnsureExactBlueStacks($sAttachmentError)",
            "$g_bAndroidAdbScreencap",
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
        self.assertIn("OpenHomeCollectorsCollectOnePass(1)", runner)

        loot_runner = autoit_function(action, "_BotStartOpenHomeLootCart")
        for proof in (
            "HomeMaintenanceRouteAccountMatches",
            "_BotOpenHomeEnsureExactBlueStacks($sAttachmentError)",
            "$g_bAndroidAdbScreencap",
            "AndroidControlAvailable()",
            "GetBlueStacks5ModernAdbSurfacePosition()",
            "OpenHomeCollectorsProveHome()",
            "LootCartRouteRunAdapter",
            "OpenHomeClearSelectedActionPanel",
        ):
            self.assertIn(proof, loot_runner)
        for forbidden in (
            "MBRFunc",
            "ForumAuthentication",
            "OpenAndroid",
            "InitiateLayout",
            "ZoomOut",
            "BotDetectFirstTime",
            "btnStop",
        ):
            self.assertNotIn(forbidden, loot_runner)

        treasury_runner = autoit_function(action, "_BotStartOpenHomeTreasury")
        for proof in (
            "HomeMaintenanceRouteAccountMatches",
            "_BotOpenHomeEnsureExactBlueStacks($sAttachmentError)",
            "$g_bAndroidAdbScreencap",
            "AndroidControlAvailable()",
            "GetBlueStacks5ModernAdbSurfacePosition()",
            "OpenHomeCollectorsProveHome()",
            "TreasuryRouteRunAdapter",
            "OpenHomeTreasuryDetectCastle",
            "OpenHomeTreasuryCleanup",
        ):
            self.assertIn(proof, treasury_runner)
        for forbidden in (
            "MBRFunc",
            "ForumAuthentication",
            "OpenAndroid",
            "InitiateLayout",
            "ZoomOut",
            "BotDetectFirstTime",
            "btnStop",
        ):
            self.assertNotIn(forbidden, treasury_runner)

        daily_runner = autoit_function(action, "_BotStartOpenDailyReward")
        for proof in (
            "HomeMaintenanceRouteAccountMatches",
            "_BotOpenHomeEnsureExactBlueStacks($sAttachmentError)",
            "$g_bAndroidAdbScreencap",
            "$g_bAndroidAdbClick",
            "AndroidControlAvailable()",
            "GetBlueStacks5ModernAdbSurfacePosition()",
            "OpenHomeDailyRewardCaptureClaim",
            "OpenHomeDailyRewardIssueClaim",
            "OpenHomeDailyRewardCloseAndProveHome",
            "OpenHomeClearSelectedActionPanel",
            "RunEventLogMaintenanceDailyRewardClickIssued",
            "RunEventLogMaintenanceHomeVerified",
        ):
            self.assertIn(proof, daily_runner)
        for forbidden in (
            "MBRFunc",
            "ForumAuthentication",
            "OpenAndroid",
            "InitiateLayout",
            "ZoomOut",
            "BotDetectFirstTime",
            "btnStop",
            "GemClick",
            "ClickP(",
            "PureClick(",
            "findMultiple(",
            "findImage(",
        ):
            self.assertNotIn(forbidden, daily_runner)

        for runner in (runner, loot_runner, treasury_runner):
            self.assertNotIn("$g_bAndroidAdbClick", runner)
            self.assertIn("AndroidControlAvailable()", runner)
        self.assertIn("$g_bAndroidAdbClick", daily_runner)
        self.assertIn("AndroidControlAvailable()", daily_runner)

    def test_terminal_outcome_restores_idle_without_legacy_stop(self):
        bridge = source("COCBot/functions/Run/RunControlBridge.au3")
        outcome = autoit_function(bridge, "RunControlReportOneShotOutcome")
        self.assertIn("$g_bRunState = False", outcome)
        self.assertIn("$g_iBotAction = $eBotNoAction", outcome)
        self.assertIn("$g_sRunControlActiveStartRequestId = \"\"", outcome)
        self.assertNotIn("BotStop", outcome)
        self.assertNotIn("ResumeAndroid", outcome)

    def test_terminal_outcome_survives_native_restart_without_stale_online_claim(self):
        bridge = source("COCBot/functions/Run/RunControlBridge.au3")
        self.assertIn("Global Const $RUN_CONTROL_TERMINAL_OUTCOME_TTL_SECONDS = 120", bridge)

        terminal_predicate = autoit_function(bridge, "_RunControlOutcomeIsTerminal")
        for outcome in ("completed", "failed", "passed", "rejected", "stopped"):
            self.assertIn(outcome, terminal_predicate)
        self.assertNotIn("accepted", terminal_predicate)
        self.assertNotIn("started", terminal_predicate)

        restore = autoit_function(bridge, "_RunControlRestoreRecentTerminalOutcome")
        for contract in (
            "RunControlStatusPath()",
            "_RunControlCommandAgeSeconds($sPath, $sTimestampError)",
            "$RUN_CONTROL_TERMINAL_OUTCOME_TTL_SECONDS",
            "RunPlanFileLoad($sPath, $sLoadError)",
            '"last_command_message"',
            "$g_sRunControlLastCommandId = $sRequestId",
            "$g_sRunControlLastCommand = $sCommand",
            "$g_sRunControlLastOutcome = $sOutcome",
            "$g_sRunControlMessage = $sMessage",
        ):
            self.assertIn(contract, restore)
        self.assertIn("^[A-Za-z0-9._-]{1,80}$", restore)
        self.assertIn("^(start|launch-game|check-engine|stop)$", restore)

        initialize = autoit_function(bridge, "RunControlInitialize")
        self.assertIn("Local $bRestoredTerminalOutcome = False", initialize)
        self.assertIn(
            "If $g_sRunControlLastOutcome = \"\" Then $bRestoredTerminalOutcome = _RunControlRestoreRecentTerminalOutcome()",
            initialize,
        )
        self.assertIn(
            "If Not $bRestoredTerminalOutcome And $g_sRunControlLastOutcome <> \"rejected\" Then $g_sRunControlMessage = \"Native engine is ready\"",
            initialize,
        )

        shutdown = autoit_function(bridge, "RunControlShutdown")
        self.assertIn(
            "If Not _RunControlOutcomeIsTerminal($g_sRunControlLastOutcome) Then FileDelete(RunControlStatusPath())",
            shutdown,
        )

    def test_one_shot_home_inputs_use_their_declared_transport(self):
        for relative, expected_count in (
            ("COCBot/functions/Run/OpenHomeCollectors.au3", 3),
            ("COCBot/functions/Run/OpenHomeTreasury.au3", 3),
        ):
            click_lines = [
                line
                for line in source(relative).splitlines()
                if "NoPremiumPointClick(" in line and "#OpenHomeDailyReward" not in line
                and "#OpenHomeInactivityReload" not in line
                and "#OpenHomeWelcomeBackClose" not in line
                and "#OpenHomeClearSelection" not in line
                and "#OpenRegularBattleEntry" not in line
            ]
            self.assertEqual(expected_count, len(click_lines), relative)
            self.assertTrue(all(", True)" in line for line in click_lines), click_lines)

        daily = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        direct_adb_lines = [
            line
            for line in daily.splitlines()
            if (
                "#OpenHomeDailyReward" in line
                or "#OpenHomeInactivityReload" in line
                or "#OpenHomeWelcomeBackClose" in line
                or "#OpenHomeClearSelection" in line
                or "#OpenRegularBattleEntry" in line
            )
            and "NoPremiumPointClick(" in line
        ]
        self.assertEqual(7, len(direct_adb_lines))
        self.assertTrue(all(", False)" in line for line in direct_adb_lines), direct_adb_lines)

        click = autoit_function(source("COCBot/functions/Other/Click.au3"), "Click")
        self.assertIn("$bForceControl = False", source("COCBot/functions/Other/Click.au3"))
        self.assertIn("$g_bAndroidAdbClick = True And Not $bForceControl", click)


if __name__ == "__main__":
    unittest.main()
