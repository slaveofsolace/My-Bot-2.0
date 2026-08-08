#!/usr/bin/env python3
"""Validate the sourced current-game catalog and its cross-file contracts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
GAME_DIR = ROOT / "config/game"
CAPABILITIES_PATH = ROOT / "config/current-client-capabilities.json"
FIXTURES_PATH = ROOT / "tests/fixtures/current-client/manifest.json"
PROHIBITED_UNVERIFIED = ("clash of cards", "chief's chronicles")
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_date(value: str, label: str, errors: list[str]) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        errors.append(f"{label} must be an ISO date")
        return None


def unique_ids(items: list[dict[str, Any]], label: str, errors: list[str]) -> set[str]:
    seen: set[str] = set()
    for index, item in enumerate(items):
        item_id = item.get("id")
        if not isinstance(item_id, str) or not ID_PATTERN.fullmatch(item_id):
            errors.append(f"{label}[{index}] has invalid id {item_id!r}")
            continue
        if item_id in seen:
            errors.append(f"duplicate {label} id: {item_id}")
        seen.add(item_id)
    return seen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    client = load(GAME_DIR / "current-client.json")
    battles = load(GAME_DIR / "battle-surfaces.json")
    guardians = load(GAME_DIR / "guardians.json")
    heroes = load(GAME_DIR / "heroes.json")
    screens = load(GAME_DIR / "screen-states.json")
    capabilities = load(CAPABILITIES_PATH)
    fixtures = load(FIXTURES_PATH)

    as_of = parse_date(client.get("as_of"), "current-client.as_of", errors)
    verified_through = parse_date(client.get("verified_through"), "current-client.verified_through", errors)
    if as_of and verified_through and verified_through > as_of:
        errors.append("verified_through cannot be after as_of")
    if client.get("max_town_hall") != 18:
        errors.append("max_town_hall must be 18")
    if client.get("home_village_hero_count") != 6 or client.get("max_active_hero_slots") != 4:
        errors.append("current client must declare six Heroes and four active slots")

    sources = client.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("current-client sources must be a non-empty list")
        sources = []
    source_ids = unique_ids(sources, "sources", errors)
    for source in sources:
        source_date = parse_date(source.get("published_date"), f"source {source.get('id')} date", errors)
        if as_of and source_date and source_date > as_of:
            errors.append(f"source {source.get('id')} is newer than the audit date")
        parsed = urlparse(str(source.get("url", "")))
        if parsed.scheme != "https" or parsed.netloc != "supercell.com" or "/games/clashofclans/blog/" not in parsed.path:
            errors.append(f"source {source.get('id')} is not an official Clash of Clans Supercell URL")
        if len(str(source.get("title", "")).strip()) < 5:
            errors.append(f"source {source.get('id')} title is missing")

    updates = client.get("updates")
    if not isinstance(updates, list) or not updates:
        errors.append("current-client updates must be a non-empty list")
        updates = []
    update_ids = unique_ids(updates, "updates", errors)
    allowed_catalogs = {"battle-surfaces", "guardians", "heroes", "screen-states"}
    for update in updates:
        if update.get("source_id") not in source_ids:
            errors.append(f"update {update.get('id')} references an unknown source")
        effective = parse_date(update.get("effective_date"), f"update {update.get('id')} effective_date", errors)
        if as_of and effective and effective > as_of:
            errors.append(f"update {update.get('id')} is newer than the audit date")
        facts = update.get("facts")
        if not isinstance(facts, list) or not facts or not all(isinstance(item, str) and len(item.strip()) >= 15 for item in facts):
            errors.append(f"update {update.get('id')} requires substantive facts")
        affected = update.get("affected_catalogs")
        if not isinstance(affected, list) or not affected or not set(affected).issubset(allowed_catalogs):
            errors.append(f"update {update.get('id')} has invalid affected_catalogs")

    serialized_catalogs = json.dumps([client, battles, guardians, heroes, screens], ensure_ascii=False).lower()
    for claim in PROHIBITED_UNVERIFIED:
        occurrences = serialized_catalogs.count(claim)
        if occurrences != 1:
            errors.append(f"unverified claim {claim!r} must appear exactly once, only in the exclusion register")
    exclusions = client.get("excluded_unverified_claims")
    if not isinstance(exclusions, list) or {str(item.get("name", "")).lower() for item in exclusions} != set(PROHIBITED_UNVERIFIED):
        errors.append("excluded_unverified_claims must document both removed August claims")

    capability_ids = {item.get("id") for item in capabilities.get("capabilities", []) if isinstance(item, dict)}
    fixture_ids = {item.get("id") for item in fixtures.get("required_fixtures", []) if isinstance(item, dict)}

    surfaces = battles.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        errors.append("battle surfaces must be a non-empty list")
        surfaces = []
    surface_ids = unique_ids(surfaces, "battle surfaces", errors)
    allowed_routes = {None, "regular", "ranked", "legend", "builder"}
    allowed_recognition = {"fixture-required", "verified"}
    allowed_execution = {"blocked", "not-implemented", "verified"}
    for surface in surfaces:
        surface_id = surface.get("id")
        if surface.get("source_id") not in source_ids:
            errors.append(f"battle surface {surface_id} references an unknown source")
        if surface.get("engine_route") not in allowed_routes:
            errors.append(f"battle surface {surface_id} has invalid engine_route")
        parent = surface.get("parent_surface")
        if parent is not None and parent not in surface_ids:
            errors.append(f"battle surface {surface_id} has unknown parent {parent}")
        budget = surface.get("attack_budget")
        if not isinstance(budget, dict) or set(budget) != {"kind", "value", "unit"}:
            errors.append(f"battle surface {surface_id} has invalid attack_budget")
        if surface.get("recognition_status") not in allowed_recognition:
            errors.append(f"battle surface {surface_id} has invalid recognition_status")
        if surface.get("execution_status") not in allowed_execution:
            errors.append(f"battle surface {surface_id} has invalid execution_status")
        if surface.get("legacy_fallback_allowed") is not False:
            errors.append(f"battle surface {surface_id} must default legacy fallback to false")
        for fixture_id in surface.get("fixture_ids", []):
            if fixture_id not in fixture_ids:
                errors.append(f"battle surface {surface_id} references missing fixture {fixture_id}")

    by_surface = {item.get("id"): item for item in surfaces}
    regular = by_surface.get("regular", {})
    ranked = by_surface.get("ranked", {})
    if regular.get("minimum_town_hall") != 2 or regular.get("trophy_effect") != "none" or regular.get("attack_budget", {}).get("kind") != "unlimited":
        errors.append("regular battle rules do not match the official Ranked update")
    if ranked.get("minimum_town_hall") != 7 or ranked.get("schedule") != "weekly-tournament" or ranked.get("attack_budget", {}).get("kind") != "ui-reported":
        errors.append("ranked battle rules do not match the official Ranked update")
    expected_legend = {
        "legend-iii": (24, "per-week"),
        "legend-ii": (30, "per-week"),
        "legend-i": (8, "per-league-day"),
    }
    for surface_id, (value, unit) in expected_legend.items():
        budget = by_surface.get(surface_id, {}).get("attack_budget", {})
        if budget.get("value") != value or budget.get("unit") != unit:
            errors.append(f"{surface_id} attack budget does not match the official April 2026 update")

    hero_items = heroes.get("heroes")
    if not isinstance(hero_items, list):
        errors.append("heroes must be a list")
        hero_items = []
    hero_ids = unique_ids(hero_items, "heroes", errors)
    expected_heroes = {"barbarian-king", "archer-queen", "minion-prince", "grand-warden", "royal-champion", "dragon-duke"}
    if hero_ids != expected_heroes:
        errors.append("hero catalog must contain exactly the six current Home Village Heroes")
    if heroes.get("home_village_hero_count") != 6 or heroes.get("max_active_slots") != 4:
        errors.append("hero catalog count or active slot limit is incorrect")
    expected_unlocks = {
        "barbarian-king": 4,
        "archer-queen": 8,
        "minion-prince": 9,
        "grand-warden": 11,
        "royal-champion": 13,
        "dragon-duke": 15,
    }
    for hero in hero_items:
        hero_id = hero.get("id")
        if hero.get("unlock_town_hall") != expected_unlocks.get(hero_id):
            errors.append(f"hero {hero_id} has an unexpected unlock Town Hall")
        if hero.get("unlock_source_id") not in source_ids:
            errors.append(f"hero {hero_id} references an unknown source")
        if hero.get("active_slot_eligible") is not True:
            errors.append(f"hero {hero_id} must be active-slot eligible")
        for fixture_id in hero.get("fixture_ids", []):
            if fixture_id not in fixture_ids:
                errors.append(f"hero {hero_id} references missing fixture {fixture_id}")

    guardian_items = guardians.get("guardians")
    if not isinstance(guardian_items, list):
        errors.append("guardians must be a list")
        guardian_items = []
    guardian_ids = unique_ids(guardian_items, "guardians", errors)
    if guardian_ids != {"smasher", "longshot", "logger"}:
        errors.append("guardian catalog must contain exactly Smasher, Longshot, and Logger")
    if guardians.get("guardian_count") != 3 or guardians.get("max_active_guardians") != 1:
        errors.append("guardian catalog count or active limit is incorrect")
    for guardian in guardian_items:
        guardian_id = guardian.get("id")
        if guardian.get("unlock_town_hall") != 18:
            errors.append(f"guardian {guardian_id} must unlock at Town Hall 18")
        if guardian.get("source_id") not in source_ids:
            errors.append(f"guardian {guardian_id} references an unknown source")
        for rule in ("builder_required", "unavailable_while_upgrading", "completed_level_defends_while_upgrading"):
            if guardian.get(rule) is not True:
                errors.append(f"guardian {guardian_id} must declare {rule}=true")
        for fixture_id in guardian.get("fixture_ids", []):
            if fixture_id not in fixture_ids:
                errors.append(f"guardian {guardian_id} references missing fixture {fixture_id}")

    states = screens.get("states")
    if not isinstance(states, list) or not states:
        errors.append("screen states must be a non-empty list")
        states = []
    state_ids = unique_ids(states, "screen states", errors)
    safe_actions = {"observe", "ignore", "stop-route", "close-known", "return-home"}
    for state in states:
        state_id = state.get("id")
        if state.get("source_id") not in source_ids:
            errors.append(f"screen state {state_id} references an unknown source")
        if state.get("recognition_status") not in {"fixture-required", "verified"}:
            errors.append(f"screen state {state_id} has invalid recognition_status")
        if state.get("handler_status") not in {"not-implemented", "implemented", "verified"}:
            errors.append(f"screen state {state_id} has invalid handler_status")
        if state.get("safe_default_action") not in safe_actions:
            errors.append(f"screen state {state_id} has invalid safe_default_action")
        if not isinstance(state.get("retry_limit"), int) or state.get("retry_limit") < 0 or state.get("retry_limit") > 10:
            errors.append(f"screen state {state_id} has invalid retry_limit")
        for capability_id in state.get("capability_ids", []):
            if capability_id not in capability_ids:
                errors.append(f"screen state {state_id} references missing capability {capability_id}")
        for fixture_id in state.get("fixture_ids", []):
            if fixture_id not in fixture_ids:
                errors.append(f"screen state {state_id} references missing fixture {fixture_id}")

    required_states = {
        "army.recipes.home", "army.cookbook.tab", "defense.crafted.management",
        "battle.regular.entry", "battle.ranked.entry", "battle.revenge.entry",
        "battle.legend.tier", "battle.fast-forward", "village.town-hall-18",
        "village.guardian.management", "heroes.hall.six", "heroes.dragon-duke",
        "heroes.journey", "chat.global.closed", "chat.global.open",
        "builder.extra-builder.shop", "shop.chain-offers",
    }
    if state_ids != required_states:
        errors.append("screen-state catalog does not match the required current-client surface set")

    for document in (
        ROOT / "docs/audit/BASELINE_AUDIT_2026-08-06.md",
        ROOT / "docs/compatibility/GAME_UPDATE_MATRIX.md",
    ):
        lowered = document.read_text(encoding="utf-8-sig").lower()
        for claim in PROHIBITED_UNVERIFIED:
            if claim in lowered:
                errors.append(f"{document.relative_to(ROOT)} still presents removed claim {claim!r}")

    report = {
        "schema_version": 1,
        "sources": len(source_ids),
        "updates": len(update_ids),
        "battle_surfaces": len(surface_ids),
        "guardians": len(guardian_ids),
        "heroes": len(hero_ids),
        "screen_states": len(state_ids),
        "errors": errors,
        "warnings": warnings,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
