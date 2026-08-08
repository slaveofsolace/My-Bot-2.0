#!/usr/bin/env python3
"""Generate the AutoIt current-game catalog from sourced JSON data.

The JSON files are authoritative. Generated AutoIt is committed so Windows builds
do not need Python at runtime. Use --check in CI to prevent drift.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
GAME_DIR = ROOT / "config/game"
DEFAULT_OUTPUT = ROOT / "COCBot/functions/Game/GameCatalog.generated.au3"

INPUTS = {
    "client": GAME_DIR / "current-client.json",
    "battles": GAME_DIR / "battle-surfaces.json",
    "guardians": GAME_DIR / "guardians.json",
    "heroes": GAME_DIR / "heroes.json",
    "screens": GAME_DIR / "screen-states.json",
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def au3_string(value: Any) -> str:
    if value is None:
        value = ""
    return '"' + str(value).replace('"', '""') + '"'


def au3_bool(value: Any) -> str:
    return "True" if value is True else "False"


def joined(values: Iterable[str] | None) -> str:
    return "|".join(values or [])


def emit_assignments(
    lines: list[str],
    array_name: str,
    rows: list[list[tuple[str, str]]],
) -> None:
    for row_index, row in enumerate(rows):
        for column_name, value in row:
            lines.append(f"\t{array_name}[{row_index}][{column_name}] = {value}")


def render() -> str:
    client = load(INPUTS["client"])
    battles = load(INPUTS["battles"])
    guardians = load(INPUTS["guardians"])
    heroes = load(INPUTS["heroes"])
    screens = load(INPUTS["screens"])

    if client.get("schema_version") != 1:
        raise ValueError("current-client schema_version must be 1")
    if client.get("max_town_hall") != 18:
        raise ValueError("current-client max_town_hall must be 18")
    if heroes.get("home_village_hero_count") != 6:
        raise ValueError("hero catalog must contain six Home Village Heroes")
    if heroes.get("max_active_slots") != 4:
        raise ValueError("hero catalog must allow four active Hero slots")

    source_rows: list[list[tuple[str, str]]] = []
    for source in client["sources"]:
        source_rows.append([
            ("$eGameSourceId", au3_string(source["id"])),
            ("$eGameSourceDate", au3_string(source["published_date"])),
            ("$eGameSourceTitle", au3_string(source["title"])),
            ("$eGameSourceUrl", au3_string(source["url"])),
        ])

    hero_rows: list[list[tuple[str, str]]] = []
    for hero in heroes["heroes"]:
        hero_rows.append([
            ("$eGameHeroId", au3_string(hero["id"])),
            ("$eGameHeroLabel", au3_string(hero["label"])),
            ("$eGameHeroUnlockTownHall", str(int(hero["unlock_town_hall"]))),
            ("$eGameHeroMovement", au3_string(hero["movement"])),
            ("$eGameHeroSourceId", au3_string(hero["unlock_source_id"])),
            ("$eGameHeroSourceConfidence", au3_string(hero["source_confidence"])),
            ("$eGameHeroFixtureIds", au3_string(joined(hero["fixture_ids"]))),
            ("$eGameHeroAvailabilityDate", au3_string(hero.get("availability_date", ""))),
            ("$eGameHeroActiveSlotEligible", au3_bool(hero["active_slot_eligible"])),
        ])

    guardian_rows: list[list[tuple[str, str]]] = []
    for guardian in guardians["guardians"]:
        guardian_rows.append([
            ("$eGameGuardianId", au3_string(guardian["id"])),
            ("$eGameGuardianLabel", au3_string(guardian["label"])),
            ("$eGameGuardianUnlockTownHall", str(int(guardian["unlock_town_hall"]))),
            ("$eGameGuardianSourceId", au3_string(guardian["source_id"])),
            ("$eGameGuardianBuilderRequired", au3_bool(guardian["builder_required"])),
            ("$eGameGuardianUnavailableWhileUpgrading", au3_bool(guardian["unavailable_while_upgrading"])),
            ("$eGameGuardianCompletedLevelDefends", au3_bool(guardian["completed_level_defends_while_upgrading"])),
            ("$eGameGuardianFixtureIds", au3_string(joined(guardian["fixture_ids"]))),
        ])

    battle_rows: list[list[tuple[str, str]]] = []
    for surface in battles["surfaces"]:
        budget = surface["attack_budget"]
        min_th = -1 if surface["minimum_town_hall"] is None else int(surface["minimum_town_hall"])
        budget_value = -1 if budget["value"] is None else int(budget["value"])
        battle_rows.append([
            ("$eGameBattleId", au3_string(surface["id"])),
            ("$eGameBattleLabel", au3_string(surface["label"])),
            ("$eGameBattleSourceId", au3_string(surface["source_id"])),
            ("$eGameBattleEngineRoute", au3_string(surface.get("engine_route"))),
            ("$eGameBattleParentSurface", au3_string(surface.get("parent_surface"))),
            ("$eGameBattleMinimumTownHall", str(min_th)),
            ("$eGameBattleSchedule", au3_string(surface["schedule"])),
            ("$eGameBattleBudgetKind", au3_string(budget["kind"])),
            ("$eGameBattleBudgetValue", str(budget_value)),
            ("$eGameBattleBudgetUnit", au3_string(budget.get("unit"))),
            ("$eGameBattleTrophyEffect", au3_string(surface["trophy_effect"])),
            ("$eGameBattleFixtureIds", au3_string(joined(surface["fixture_ids"]))),
            ("$eGameBattleRecognitionStatus", au3_string(surface["recognition_status"])),
            ("$eGameBattleExecutionStatus", au3_string(surface["execution_status"])),
            ("$eGameBattleLegacyFallbackAllowed", au3_bool(surface["legacy_fallback_allowed"])),
            ("$eGameBattleShadowBase", au3_bool(surface.get("shadow_base", False))),
        ])

    screen_rows: list[list[tuple[str, str]]] = []
    for state in screens["states"]:
        screen_rows.append([
            ("$eGameScreenId", au3_string(state["id"])),
            ("$eGameScreenCategory", au3_string(state["category"])),
            ("$eGameScreenSourceId", au3_string(state["source_id"])),
            ("$eGameScreenCapabilityIds", au3_string(joined(state["capability_ids"]))),
            ("$eGameScreenFixtureIds", au3_string(joined(state["fixture_ids"]))),
            ("$eGameScreenBlocking", au3_bool(state["blocking"])),
            ("$eGameScreenRecognitionStatus", au3_string(state["recognition_status"])),
            ("$eGameScreenHandlerStatus", au3_string(state["handler_status"])),
            ("$eGameScreenSafeDefaultAction", au3_string(state["safe_default_action"])),
            ("$eGameScreenRetryLimit", str(int(state["retry_limit"]))),
            ("$eGameScreenAppearsAfterSeconds", str(int(state.get("appears_after_seconds", -1)))),
            ("$eGameScreenSpeedMultiplier", str(int(state.get("speed_multiplier", -1)))),
        ])

    lines = [
        "; AUTO-GENERATED FILE. DO NOT EDIT.",
        "; Generator: tools/generate_game_catalog_autoit.py",
        "; Inputs: config/game/current-client.json, config/game/battle-surfaces.json, config/game/guardians.json, config/game/heroes.json, config/game/screen-states.json",
        ";",
        "; This file is distributed under the terms of the GNU GPL v3.",
        "#include-once",
        "",
        f"Global Const $CURRENT_GAME_SCHEMA_VERSION = {int(client['schema_version'])}",
        f"Global Const $CURRENT_GAME_AS_OF = {au3_string(client['as_of'])}",
        f"Global Const $CURRENT_GAME_VERIFIED_THROUGH = {au3_string(client['verified_through'])}",
        f"Global Const $CURRENT_GAME_MAX_TOWN_HALL = {int(client['max_town_hall'])}",
        f"Global Const $CURRENT_GAME_HOME_HERO_COUNT = {int(client['home_village_hero_count'])}",
        f"Global Const $CURRENT_GAME_MAX_ACTIVE_HERO_SLOTS = {int(client['max_active_hero_slots'])}",
        f"Global Const $CURRENT_GAME_GUARDIAN_COUNT = {int(guardians['guardian_count'])}",
        f"Global Const $CURRENT_GAME_MAX_ACTIVE_GUARDIANS = {int(guardians['max_active_guardians'])}",
        "",
        "Global Enum $eGameSourceId, $eGameSourceDate, $eGameSourceTitle, $eGameSourceUrl, $eGameSourceColumnCount",
        "Global Enum $eGameHeroId, $eGameHeroLabel, $eGameHeroUnlockTownHall, $eGameHeroMovement, $eGameHeroSourceId, $eGameHeroSourceConfidence, $eGameHeroFixtureIds, $eGameHeroAvailabilityDate, $eGameHeroActiveSlotEligible, $eGameHeroColumnCount",
        "Global Enum $eGameGuardianId, $eGameGuardianLabel, $eGameGuardianUnlockTownHall, $eGameGuardianSourceId, $eGameGuardianBuilderRequired, $eGameGuardianUnavailableWhileUpgrading, $eGameGuardianCompletedLevelDefends, $eGameGuardianFixtureIds, $eGameGuardianColumnCount",
        "Global Enum $eGameBattleId, $eGameBattleLabel, $eGameBattleSourceId, $eGameBattleEngineRoute, $eGameBattleParentSurface, $eGameBattleMinimumTownHall, $eGameBattleSchedule, $eGameBattleBudgetKind, $eGameBattleBudgetValue, $eGameBattleBudgetUnit, $eGameBattleTrophyEffect, $eGameBattleFixtureIds, $eGameBattleRecognitionStatus, $eGameBattleExecutionStatus, $eGameBattleLegacyFallbackAllowed, $eGameBattleShadowBase, $eGameBattleColumnCount",
        "Global Enum $eGameScreenId, $eGameScreenCategory, $eGameScreenSourceId, $eGameScreenCapabilityIds, $eGameScreenFixtureIds, $eGameScreenBlocking, $eGameScreenRecognitionStatus, $eGameScreenHandlerStatus, $eGameScreenSafeDefaultAction, $eGameScreenRetryLimit, $eGameScreenAppearsAfterSeconds, $eGameScreenSpeedMultiplier, $eGameScreenColumnCount",
        "",
        f"Global $g_aCurrentGameSources[{len(source_rows)}][$eGameSourceColumnCount]",
        f"Global $g_aCurrentGameHeroes[{len(hero_rows)}][$eGameHeroColumnCount]",
        f"Global $g_aCurrentGameGuardians[{len(guardian_rows)}][$eGameGuardianColumnCount]",
        f"Global $g_aCurrentGameBattleSurfaces[{len(battle_rows)}][$eGameBattleColumnCount]",
        f"Global $g_aCurrentGameScreenStates[{len(screen_rows)}][$eGameScreenColumnCount]",
        "Global $__g_bCurrentGameCatalogInitialized = False",
        "",
        "Func _InitializeCurrentGameCatalogGenerated()",
        "\tIf $__g_bCurrentGameCatalogInitialized Then Return",
    ]
    emit_assignments(lines, "$g_aCurrentGameSources", source_rows)
    emit_assignments(lines, "$g_aCurrentGameHeroes", hero_rows)
    emit_assignments(lines, "$g_aCurrentGameGuardians", guardian_rows)
    emit_assignments(lines, "$g_aCurrentGameBattleSurfaces", battle_rows)
    emit_assignments(lines, "$g_aCurrentGameScreenStates", screen_rows)
    lines += [
        "\t$__g_bCurrentGameCatalogInitialized = True",
        "EndFunc   ;==>_InitializeCurrentGameCatalogGenerated",
        "",
        "_InitializeCurrentGameCatalogGenerated()",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    rendered = render()
    output = args.output if args.output.is_absolute() else ROOT / args.output

    if args.check:
        if not output.is_file():
            raise SystemExit(f"generated catalog is missing: {output.relative_to(ROOT)}")
        current = output.read_text(encoding="utf-8-sig")
        if current != rendered:
            raise SystemExit(
                "generated AutoIt catalog is stale; run "
                "python tools/generate_game_catalog_autoit.py"
            )
        print(f"Generated AutoIt catalog is current: {output.relative_to(ROOT)}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
