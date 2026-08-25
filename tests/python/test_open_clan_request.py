import json
import re
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "COCBot" / "functions" / "Run" / "OpenClanRequest.au3"
GUI_ACTION = ROOT / "COCBot" / "MBR GUI Action.au3"
FIXTURES = ROOT / "tests" / "fixtures" / "current-client" / "images"
FIXTURE_MANIFEST = ROOT / "tests" / "fixtures" / "current-client" / "manifest.json"
PERMIT_POLICY = ROOT / "COCBot" / "functions" / "Run" / "NoPremiumPermitPolicy.au3"
CLICK = ROOT / "COCBot" / "functions" / "Other" / "Click.au3"
PERMIT_DOC = ROOT / "docs" / "development" / "CLAN_REQUEST_INPUT_PERMITS.md"


def function_block(source: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^Func\s+{re.escape(name)}\b.*?^EndFunc\b[^\r\n]*$", source
    )
    if not match:
        raise AssertionError(f"missing AutoIt function {name}")
    return match.group(0)


def color_near(actual: tuple[int, int, int], expected: int, variation: int) -> bool:
    wanted = ((expected >> 16) & 0xFF, (expected >> 8) & 0xFF, expected & 0xFF)
    return all(abs(a - b) <= variation for a, b in zip(actual, wanted))


class OpenClanRequestContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = ROUTE.read_text(encoding="utf-8")

    def test_route_is_framebuffer_only_and_does_not_reenter_managed_engine(self) -> None:
        executable = "\n".join(
            line for line in self.source.splitlines() if not line.lstrip().startswith(";")
        )
        forbidden_calls = (
            r"\bMBRFunc[A-Za-z0-9_]*\(",
            r"\bfindMultiple\(",
            r"\bImgLoc[A-Za-z0-9_]*\(",
            r"\bOpenArmyOverview\(",
            r"\bcheckMainScreen\(",
            r"\bRequestCC\(",
            r"\bDonateCC\(",
            r"\bAndroidSendText\(",
        )
        for pattern in forbidden_calls:
            self.assertNotRegex(executable, pattern)
        self.assertNotRegex(executable, r"(?<!_)\bSleep\(")
        self.assertIn("OpenHomeCollectorsCapture", self.source)
        self.assertIn("_OpenHomePixelNear", self.source)

    def test_committed_redacted_frames_match_the_production_anchors(self) -> None:
        army = Image.open(FIXTURES / "army.training.ready.png").convert("RGB")
        dialog = Image.open(FIXTURES / "clan.request.available.png").convert("RGB")

        army_anchors = (
            (50, 210, 0x9F6B42, 32),
            (400, 210, 0x956245, 32),
            (800, 210, 0x956245, 32),
            (100, 555, 0x624336, 32),
            (790, 250, 0xFFFCED, 28),
            (790, 400, 0x6DBCF1, 36),
            (740, 500, 0xB0E477, 32),
            (750, 500, 0xB0E477, 32),
            (770, 510, 0x8BD43A, 32),
            (760, 485, 0x8BD43A, 32),
        )
        dialog_anchors = (
            (200, 120, 0xEAEAE1, 28),
            (430, 110, 0x635A57, 32),
            (180, 200, 0xEAEAE1, 28),
            (220, 330, 0xFFFFFF, 20),
            (650, 330, 0xEAEAE1, 28),
            (430, 320, 0x000000, 20),
            (470, 450, 0xE3FA8F, 28),
            (620, 450, 0xE4FB8F, 28),
            (545, 510, 0x77C120, 32),
            (240, 450, 0xFFCB7E, 28),
            (390, 450, 0xFFCB7E, 28),
        )

        for x, y, expected, variation in army_anchors:
            self.assertTrue(
                color_near(army.getpixel((x, y)), expected, variation),
                f"Army fixture anchor {(x, y)} did not match {expected:#08x}",
            )
            self.assertRegex(
                self.source,
                rf"_OpenHomePixelNear\(\s*{x}\s*,\s*{y}\s*,\s*0x{expected:06X}\s*,\s*{variation}\s*\)",
            )

        for x, y, expected, variation in dialog_anchors:
            self.assertTrue(
                color_near(dialog.getpixel((x, y)), expected, variation),
                f"Request fixture anchor {(x, y)} did not match {expected:#08x}",
            )
            self.assertRegex(
                self.source,
                rf"_OpenHomePixelNear\(\s*{x}\s*,\s*{y}\s*,\s*0x{expected:06X}\s*,\s*{variation}\s*\)",
            )

    def test_send_is_one_attempt_with_a_last_moment_stop_poll(self) -> None:
        block = function_block(self.source, "OpenClanRequestIssueSend")
        self.assertEqual(block.count("NoPremiumPointClick("), 1)
        self.assertIn("Int($iSendX) <> $OPEN_CLAN_REQUEST_SEND_X", block)
        self.assertIn("Int($iSendY) <> $OPEN_CLAN_REQUEST_SEND_Y", block)
        self.assertLess(block.rindex("RunControlStopRequested"), block.index("NoPremiumPointClick("))
        self.assertIn("OpenClanRequestDialogReady", block)
        self.assertIn("$NO_PREMIUM_ACTION_CLAN_REQUEST_SEND", block)
        self.assertIn("$OPEN_CLAN_REQUEST_SEND_X = 545", self.source)
        self.assertIn("$OPEN_CLAN_REQUEST_SEND_Y = 478", self.source)

    def test_each_input_has_an_exact_action_point_and_pure_current_frame_predicate(self) -> None:
        policy = PERMIT_POLICY.read_text(encoding="utf-8")
        click = CLICK.read_text(encoding="utf-8-sig")
        actions = (
            ("ARMY", 39, 585, "OpenClanRequestArmyOverviewPointReady", "_OpenClanRequestNeutralHomeFrameReady"),
            ("REQUEST", 761, 498, "OpenClanRequestRequestPointReady", "_OpenClanRequestArmyOverviewFrameReady(True)"),
            ("SEND", 545, 478, "OpenClanRequestSendPointReady", "_OpenClanRequestDialogFrameReady()"),
            ("CANCEL", 316, 478, "OpenClanRequestCancelPointReady", "_OpenClanRequestDialogFrameReady()"),
            ("CLOSE", 792, 187, "OpenClanRequestClosePointReady", "_OpenClanRequestArmyOverviewFrameReady(False)"),
        )
        recognizer = function_block(click, "NoPremiumSurfaceState")
        for suffix, x, y, predicate, anchor in actions:
            action = f"$NO_PREMIUM_ACTION_CLAN_REQUEST_{suffix}"
            self.assertIn(action, policy)
            self.assertRegex(
                policy,
                rf"(?ms)Case {re.escape(action)}\s+Return \$iX = {x} And \$iY = {y}",
            )
            self.assertIn(predicate, recognizer)
            predicate_block = function_block(self.source, predicate)
            self.assertIn(anchor, predicate_block)
            self.assertNotIn("OpenHomeCollectorsCapture", predicate_block)
            self.assertNotRegex(predicate_block, r"(?<![A-Za-z_])Click\(")

    def test_cleanup_is_bounded_and_only_closes_recognized_overlays(self) -> None:
        block = function_block(self.source, "OpenClanRequestCloseAndProveHome")
        self.assertRegex(block, r"For\s+\$[A-Za-z0-9_]+\s*=\s*1\s+To\s+2")
        self.assertLess(block.index("OpenClanRequestDialogReady"), block.index("OpenClanRequestArmyOverviewReady"))
        self.assertIn("OpenClanRequestProveNeutralHome", block)
        self.assertIn("RunControlStopRequested", block)

    def test_botstart_uses_only_the_bounded_framebuffer_callbacks(self) -> None:
        source = GUI_ACTION.read_text(encoding="utf-8")
        block = function_block(source, "_BotStartOpenClanRequest")
        expected = (
            "OpenClanRequestOpenArmyOverview",
            "OpenClanRequestDetectState",
            "OpenClanRequestOpenDialog",
            "OpenClanRequestIssueSend",
            "OpenClanRequestCloseAndProveHome",
        )
        for callback in expected:
            self.assertIn(callback, block)
        self.assertIn("$g_bAndroidAdbScreencap", block)
        self.assertIn("AndroidControlAvailable()", block)
        self.assertNotIn("$g_bAndroidAdbClick", block)
        for legacy in (
            "_ClanRequestLiveOpenArmyOverview",
            "_ClanRequestLiveDetectState",
            "_ClanRequestLiveOpenDialog",
            "_ClanRequestLiveIssueSend",
            "_ClanRequestLiveCloseAndProveHome",
        ):
            self.assertNotIn(legacy, block)

    def test_all_request_inputs_use_exact_adb_capable_point_permits(self) -> None:
        blocks = [
            function_block(self.source, name)
            for name in (
                "OpenClanRequestOpenArmyOverview",
                "OpenClanRequestOpenDialog",
                "OpenClanRequestIssueSend",
                "OpenClanRequestCloseAndProveHome",
            )
        ]
        self.assertEqual(5, sum(block.count("NoPremiumPointClick(") for block in blocks))
        request_transport_lines = [
            line.strip()
            for block in blocks
            for line in block.splitlines()
            if "#OpenClanRequest" in line
        ]
        self.assertEqual(5, sum(", False)" in line for line in request_transport_lines))
        self.assertFalse(any(", True)" in line for line in request_transport_lines))
        executable = "\n".join(
            line for line in self.source.splitlines() if not line.lstrip().startswith(";")
        )
        self.assertNotRegex(executable, r"(?<![A-Za-z_])Click\(")

    def test_army_overview_fixture_keeps_clan_request_fixture_blocked_until_reviewed(self) -> None:
        manifest = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8-sig"))
        fixtures = {item["id"]: item for item in manifest["required_fixtures"]}
        army = fixtures["army.training.ready"]
        dialog = fixtures["clan.request.available"]
        self.assertEqual("redacted", army["status"])
        self.assertIn("village.clan-request", army["capability_ids"])
        self.assertEqual("verified", dialog["status"])
        self.assertIn("village.clan-request", dialog["capability_ids"])
        clan_request_fixtures = [
            item
            for item in manifest["required_fixtures"]
            if "village.clan-request" in item["capability_ids"]
        ]
        self.assertEqual(
            ["army.training.ready"],
            sorted(item["id"] for item in clan_request_fixtures if item["status"] != "verified"),
        )
        documentation = PERMIT_DOC.read_text(encoding="utf-8")
        self.assertIn("fixture-blocked", documentation)
        self.assertIn("army.training.ready", documentation)
        self.assertIn("redacted", documentation)
        self.assertIn("clan.request.available", documentation)


if __name__ == "__main__":
    unittest.main()
