from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def safe_regions(fixture_id: str) -> list[dict]:
    metadata = json.loads(
        (ROOT / f"tests/fixtures/current-client/metadata/{fixture_id}.json").read_text(encoding="utf-8-sig")
    )
    return metadata["replay_contract"]["safe_regions"]


class BattleEntryRecognitionTests(unittest.TestCase):
    def test_regular_battle_entry_runtime_predicate_matches_reviewed_region(self) -> None:
        prepare_search = source("COCBot/functions/Search/PrepareSearch.au3")

        self.assertIn("Func PrepareSearchCurrentRegularEntryReady(", prepare_search)
        self.assertIn("Return _IsCurrentMultiplayerPanelOpen($bNeedCapture)", prepare_search)
        self.assertIn("Func PrepareSearchCurrentRegularFindMatchRegionReady(", prepare_search)
        self.assertIn("$iX < 54 Or $iX > 272", prepare_search)
        self.assertIn("$iY < (461 + $g_iMidOffsetY) Or $iY > (530 + $g_iMidOffsetY)", prepare_search)
        self.assertIn("Return PrepareSearchCurrentRegularEntryReady(True)", prepare_search)
        self.assertIn("_GetPixelColor(60, 470 + $g_iMidOffsetY, False)", prepare_search)
        self.assertIn("_GetPixelColor(75, 500 + $g_iMidOffsetY, False)", prepare_search)
        self.assertIn("_GetPixelColor(135, 486 + $g_iMidOffsetY, False)", prepare_search)
        self.assertIn("$bFindMatchLabel Or $bCurrentFindMatchLabel", prepare_search)

        self.assertEqual(
            safe_regions("battle.regular.entry"),
            [{"id": "find-match", "x": 54, "y": 461, "width": 219, "height": 70}],
        )

    def test_builder_battle_entry_runtime_predicate_matches_reviewed_region(self) -> None:
        collectors = source("COCBot/functions/Run/OpenHomeCollectors.au3")

        self.assertIn("Func OpenBuilderBattleEntryReady()", collectors)
        self.assertIn("_OpenHomePixelNear(610, 430, 0xB9E884, 36)", collectors)
        self.assertIn("_OpenHomePixelNear(650, 455, 0x6BA22E, 36)", collectors)
        self.assertIn("_OpenHomePixelNear(700, 470, 0x83CA38, 36)", collectors)
        self.assertIn("Func OpenBuilderBattleFindNowRegionReady(", collectors)
        self.assertIn("$iX < 560 Or $iX > 741", collectors)
        self.assertIn("$iY < 416 Or $iY > 479", collectors)

        self.assertEqual(
            safe_regions("builder.battle.entry"),
            [{"id": "find-now", "x": 560, "y": 416, "width": 182, "height": 64}],
        )


if __name__ == "__main__":
    unittest.main()
