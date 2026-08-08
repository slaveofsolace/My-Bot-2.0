#!/usr/bin/env python3
"""Verify the generated AutoIt game model and its evidence-closed runtime API."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "config/game/current-client.json",
    "config/game/current-client.schema.json",
    "config/game/battle-surfaces.json",
    "config/game/battle-surfaces.schema.json",
    "config/game/guardians.json",
    "config/game/guardians.schema.json",
    "config/game/heroes.json",
    "config/game/heroes.schema.json",
    "config/game/screen-states.json",
    "config/game/screen-states.schema.json",
    "COCBot/functions/Game/GameCatalog.generated.au3",
    "COCBot/functions/Game/GameCatalog.au3",
    "COCBot/functions/Game/ScreenStateRegistry.au3",
    "tests/autoit/GameCatalogTest.au3",
    "tools/generate_game_catalog_autoit.py",
    "tools/validate_game_catalog.py",
    "docs/development/ENGINEERING_NOTES.md",
]


class VerificationError(RuntimeError):
    pass


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def load(path: str) -> Any:
    return json.loads(text(path))


def require(condition: bool, message: str, findings: list[dict[str, str]]) -> None:
    if not condition:
        raise VerificationError(message)
    findings.append({"check": message, "status": "passed"})


def autoit_function_balance(path: str, findings: list[dict[str, str]]) -> None:
    content = text(path)
    funcs = len(re.findall(r"(?im)^\s*Func\s+[A-Za-z_]\w*\s*\(", content))
    ends = len(re.findall(r"(?im)^\s*EndFunc\b", content))
    require(funcs == ends, f"{path}: Func/EndFunc balance ({funcs})", findings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    findings: list[dict[str, str]] = []
    for relative in REQUIRED_FILES:
        require((ROOT / relative).is_file(), f"required file exists: {relative}", findings)

    client = load("config/game/current-client.json")
    battles = load("config/game/battle-surfaces.json")
    guardians = load("config/game/guardians.json")
    heroes = load("config/game/heroes.json")
    screens = load("config/game/screen-states.json")

    require(client["as_of"] == "2026-08-06", "game model has a fixed audit date", findings)
    require(client["verified_through"] == "2026-07-09", "game model declares its official verification boundary", findings)
    require(client["max_town_hall"] == 18, "game model declares Town Hall 18", findings)
    require(heroes["home_village_hero_count"] == 6, "game model declares six Home Village Heroes", findings)
    require(heroes["max_active_slots"] == 4, "game model declares four active Hero slots", findings)
    require(guardians["guardian_count"] == 3, "game model declares three Guardians", findings)
    require(guardians["max_active_guardians"] == 1, "game model declares one active Guardian", findings)
    sound_source = next(item for item in client["sources"] if item["id"] == "sound-of-clash-2026-04-27")
    require(sound_source["url"].endswith("/the-sound-of-clash-update/"), "Sound of Clash source uses the canonical URL", findings)

    generated = text("COCBot/functions/Game/GameCatalog.generated.au3")
    require(generated.startswith("; AUTO-GENERATED FILE. DO NOT EDIT."), "generated AutoIt has a source warning", findings)
    require("$CURRENT_GAME_MAX_TOWN_HALL = 18" in generated, "generated AutoIt carries the Town Hall maximum", findings)
    require("$CURRENT_GAME_HOME_HERO_COUNT = 6" in generated, "generated AutoIt carries the Hero count", findings)
    require(f"Global $g_aCurrentGameSources[{len(client['sources'])}]" in generated, "generated AutoIt source row count matches JSON", findings)
    require(f"Global $g_aCurrentGameHeroes[{len(heroes['heroes'])}]" in generated, "generated AutoIt Hero row count matches JSON", findings)
    require(f"Global $g_aCurrentGameGuardians[{len(guardians['guardians'])}]" in generated, "generated AutoIt Guardian row count matches JSON", findings)
    require(f"Global $g_aCurrentGameBattleSurfaces[{len(battles['surfaces'])}]" in generated, "generated AutoIt battle row count matches JSON", findings)
    require(f"Global $g_aCurrentGameScreenStates[{len(screens['states'])}]" in generated, "generated AutoIt screen row count matches JSON", findings)

    for index, hero in enumerate(heroes["heroes"]):
        require(f'$g_aCurrentGameHeroes[{index}][$eGameHeroId] = "{hero["id"]}"' in generated, f"generated AutoIt contains Hero {hero['id']}", findings)
    for index, guardian in enumerate(guardians["guardians"]):
        require(f'$g_aCurrentGameGuardians[{index}][$eGameGuardianId] = "{guardian["id"]}"' in generated, f"generated AutoIt contains Guardian {guardian['id']}", findings)

    catalog = text("COCBot/functions/Game/GameCatalog.au3")
    for function_name in (
        "CurrentGameCatalogValidate",
        "CurrentGameFindHero",
        "CurrentGameGetHeroUnlockTH",
        "CurrentGameFindGuardian",
        "CurrentGameGuardianRequiresBuilder",
        "CurrentGameFindBattleSurface",
        "CurrentGameGetBattleAttackBudget",
        "CurrentGameBattleSurfaceReady",
    ):
        require(f"Func {function_name}(" in catalog, f"runtime catalog exposes {function_name}", findings)
    require('StringLower($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleRecognitionStatus]) <> "verified"' in catalog, "battle readiness requires verified recognition", findings)
    require('StringLower($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleExecutionStatus]) <> "verified"' in catalog, "battle readiness requires verified execution", findings)
    require("$eGameBattleLegacyFallbackAllowed" in catalog and "Current battle surface enables legacy fallback" in catalog, "catalog validation rejects legacy fallback", findings)

    registry = text("COCBot/functions/Game/ScreenStateRegistry.au3")
    for function_name in (
        "CurrentGameFindScreenState",
        "CurrentGameScreenCanHandle",
        "CurrentGameScreenDefaultAction",
        "CurrentGameScreenRetryLimit",
        "CurrentGameScreenShouldStopRoute",
    ):
        require(f"Func {function_name}(" in registry, f"screen registry exposes {function_name}", findings)
    require('StringLower($g_aCurrentGameScreenStates[$iIndex][$eGameScreenRecognitionStatus]) <> "verified"' in registry, "screen handling requires verified recognition", findings)
    require('StringLower($g_aCurrentGameScreenStates[$iIndex][$eGameScreenHandlerStatus]) <> "verified"' in registry, "screen handling requires a verified handler", findings)

    compatibility = text("COCBot/functions/Other/CurrentClientCompat.au3")
    require('include "..\\game\\gamecatalog.au3"' in compatibility.lower(), "current-client entry point includes the game catalog", findings)
    require('include "..\\game\\screenstateregistry.au3"' in compatibility.lower(), "current-client entry point includes the screen registry", findings)
    require("CurrentGameCatalogValidate" in compatibility, "startup validates the generated catalog", findings)

    test_script = text("tests/autoit/GameCatalogTest.au3")
    for expectation in (
        "Town Hall 18 is the maximum",
        "Dragon Duke unlocks at Town Hall 15",
        "Guardian upgrades require a Builder",
        "Legend III has 24 weekly attacks",
        "Legend II has 30 weekly attacks",
        "Legend I has eight attacks per League Day",
        "Global Chat handler remains closed",
    ):
        require(expectation in test_script, f"AutoIt test covers: {expectation}", findings)

    powershell = text("tools/Test-AutoIt.ps1")
    require("GameCatalogTest.au3" in powershell, "Windows AutoIt matrix runs the game catalog test", findings)

    for path in (
        "COCBot/functions/Game/GameCatalog.generated.au3",
        "COCBot/functions/Game/GameCatalog.au3",
        "COCBot/functions/Game/ScreenStateRegistry.au3",
        "COCBot/functions/Other/CurrentClientCompat.au3",
        "tests/autoit/GameCatalogTest.au3",
    ):
        autoit_function_balance(path, findings)

    combined_runtime = (generated + catalog + registry).lower()
    require("clash of cards" not in combined_runtime, "unverified Clash of Cards claim is absent from runtime code", findings)
    require("chief's chronicles" not in combined_runtime, "unverified Chief's Chronicles claim is absent from runtime code", findings)

    payload = {"schema_version": 1, "checks": len(findings), "findings": findings}
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as exc:
        raise SystemExit(f"current-game verification failed: {exc}") from exc
