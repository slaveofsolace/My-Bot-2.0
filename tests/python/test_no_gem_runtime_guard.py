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


class NoGemRuntimeGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.home = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        cls.treasury = source("COCBot/functions/Run/OpenHomeTreasury.au3")
        cls.request = source("COCBot/functions/Run/OpenClanRequest.au3")

    def test_guard_is_passive_and_fails_closed_without_a_frame(self) -> None:
        guard = autoit_function(self.home, "OpenHomeNoGemInputReady")
        self.assertIn("If $g_hBitmap = 0 Then Return False", guard)
        for anchor in ("$aIsGemWindow1", "$aIsGemWindow2", "$aIsGemWindow3", "$aIsGemWindow4"):
            self.assertIn(anchor, guard)
        for forbidden in ("Click(", "CloseWindow", "isGemOpen(", "DllCall"):
            self.assertNotIn(forbidden, guard)

    def test_every_reachable_template_free_click_checks_the_fresh_guard(self) -> None:
        guarded = {
            self.home: (
                "OpenHomeCollectorsCollectOnePass",
                "OpenHomeDailyRewardIssueClaim",
                "OpenHomeDailyRewardCloseAndProveHome",
                "OpenHomeLootCartIssueOpen",
                "OpenHomeLootCartIssueCollect",
            ),
            self.treasury: (
                "OpenHomeTreasuryIssueCastle",
                "OpenHomeTreasuryIssueEntry",
                "OpenHomeTreasuryCleanup",
            ),
            self.request: (
                "OpenClanRequestOpenArmyOverview",
                "OpenClanRequestOpenDialog",
                "OpenClanRequestIssueSend",
                "OpenClanRequestCloseAndProveHome",
            ),
        }
        for text, functions in guarded.items():
            for name in functions:
                with self.subTest(function=name):
                    body = autoit_function(text, name)
                    self.assertIn("OpenHomeNoGemInputReady()", body)
                    self.assertIn("SetError(6", body)
                    self.assertLess(body.index("OpenHomeNoGemInputReady()"), body.index("Click("))

    def test_route_failures_name_the_no_gem_reason_instead_of_a_generic_click_error(self) -> None:
        loot_route = source("COCBot/functions/Run/LootCartRoute.au3")
        request_route = source("COCBot/functions/Run/ClanRequestRoute.au3")
        action = source("COCBot/MBR GUI Action.au3")
        self.assertGreaterEqual(loot_route.count("Passive no-gem guard recognized a gem surface"), 2)
        self.assertGreaterEqual(request_route.count("Passive no-gem guard recognized a gem surface"), 3)
        self.assertGreaterEqual(action.lower().count("passive no-gem guard recognized a gem surface"), 2)

    def test_verified_route_fixtures_do_not_false_match_the_gem_surface(self) -> None:
        anchors = (
            ((608, 240), (0xEB, 0x16, 0x17), 20),
            ((610, 246), (0xCD, 0x16, 0x1A), 20),
            ((625, 246), (0xCE, 0x15, 0x19), 20),
            ((640, 246), (0xCD, 0x15, 0x1C), 20),
        )

        def near(pixel: tuple[int, int, int], expected: tuple[int, int, int], tolerance: int) -> bool:
            return all(abs(actual - wanted) <= tolerance for actual, wanted in zip(pixel, expected))

        image_root = ROOT / "tests/fixtures/current-client/images"
        fixtures = sorted(image_root.glob("*.png"))
        self.assertTrue(fixtures)
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                with Image.open(fixture) as opened:
                    image = opened.convert("RGB")
                    matches = [near(image.getpixel(point), expected, tolerance) for point, expected, tolerance in anchors]
                self.assertFalse(matches[0] or all(matches[1:]))


if __name__ == "__main__":
    unittest.main()
