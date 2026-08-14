#!/usr/bin/env python3
"""Build the Run Planner metadata from the game catalogs.

The prose lives here; the identifiers, labels, and availability come from config/game/*.json so the planner cannot
drift from the catalog it is meant to describe. Run this after changing a catalog, then validate_ui_metadata.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "config/ui/run-planner.settings.json"
PACING_SECTION = ROOT / "config/ui/run-planner.pacing.json"
PRESETS_SOURCE = ROOT / "config/ui/run-planner.presets.json"
ATTACK_SCRIPTS = ROOT / "CSV/Attack"
HIDDEN_SCRIPT_TOKENS = ("human-like",)


def load(name: str) -> dict:
    return json.loads((ROOT / "config/game" / name).read_text(encoding="utf-8-sig"))


def load_document(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


SURFACE_PROSE = {
    "regular": (
        "Ordinary matchmaking. Attacks are unlimited and Trophies are not at stake, which makes this the surface to "
        "use while you are still confirming that a build behaves the way you expect.",
        ["Town Hall 2 or above"],
    ),
    "ranked": (
        "Tournament matchmaking with a limited number of attacks per tournament. The bot will not start until it has "
        "read how many attacks you actually have left, because the published limit is not your remaining count.",
        ["Town Hall 7 or above", "Remaining attacks visible on the Ranked screen"],
    ),
    "revenge": (
        "Attacks a Shadow Base from your defence log. Each entry can be attacked once and the opportunity expires, so "
        "this surface is driven by what is in the log rather than by a repeating schedule.",
        ["An eligible entry in the defence log"],
    ),
    "legend-iii": (
        "The entry Legend tier, with a weekly attack budget. The budget shown in the catalog is the published maximum "
        "for the tier, not the attacks you have left this week.",
        ["Legend III placement"],
    ),
    "legend-ii": (
        "The middle Legend tier, with a larger weekly attack budget than Legend III.",
        ["Legend II placement"],
    ),
    "legend-i": (
        "The top Legend tier, budgeted per League Day rather than per week, so the remaining count resets on a "
        "different schedule from the lower tiers.",
        ["Legend I placement"],
    ),
    "builder": (
        "Builder Base matchmaking. Runs against the Builder Base economy and upgrade flow rather than the Home "
        "Village one, including the additional Builder.",
        ["Builder Hall unlocked"],
    ),
}

HERO_PROSE = {
    "barbarian-king": "Ground Hero, and the first one you unlock.",
    "archer-queen": "Ranged ground Hero with high single-target damage.",
    "minion-prince": "Air Hero, so terrain and ground defences affect it differently from the King or Queen.",
    "grand-warden": "Support Hero whose movement follows the mode you set, ground or air.",
    "royal-champion": "Ground Hero that targets defences first.",
    "dragon-duke": "Air Hero added in the February 2026 update.",
}


def option(value, label, summary, description, availability, capability_ids, prerequisites,
           recommended=False, warning="", disabled_reason="", runtime_verified=False):
    if availability != "available" and not disabled_reason:
        raise ValueError(f"{value}: an unavailable option needs a disabled reason")
    return {
        "value": value,
        "label": label,
        "summary": summary,
        "description": description,
        "availability": availability,
        "runtime_verified": bool(runtime_verified),
        "disabled_reason": disabled_reason,
        "capability_ids": capability_ids,
        "prerequisites": prerequisites,
        "recommended": recommended,
        "warning": warning,
    }


def build_surface_options(surfaces: dict) -> list[dict]:
    options = []
    for surface in surfaces["surfaces"]:
        sid = surface["id"]
        prose, prerequisites = SURFACE_PROSE[sid]
        budget = surface.get("attack_budget", {})
        kind = budget.get("kind")

        if kind == "unlimited":
            summary = "Unlimited attacks, no Trophy risk."
        elif kind == "fixed":
            summary = f"Limited to {budget['value']} attacks {str(budget.get('unit') or '').replace('-', ' ')}."
        elif kind == "single-opportunity":
            summary = "One attack per defence log entry."
        else:
            summary = "Attack count is reported by the client."

        regular = sid == "regular"
        if regular:
            prose += (
                " A bounded source adapter and an older-binary supervised gameplay receipt exist. The 2026-08-14 "
                "bea12973 LocalRuntime checkpoint passed package installation, Windows shortcut launch, idle host "
                "integrity, and exact-current no-input managed-engine initialization. This source revision is "
                "post-checkpoint and unbuilt; managed Start and gameplay were not exercised, and current-client "
                "fixtures and live human review are still absent."
            )
            prerequisites = prerequisites + ["Allow unverified with a supervised diagnostic acknowledgement"]
        options.append(option(
            value=sid,
            label=surface["label"],
            summary=summary,
            description=prose,
            availability="gated" if regular else "planned",
            disabled_reason=(
                "The 2026-08-14 bea12973 LocalRuntime checkpoint passed no-input managed-engine initialization, "
                "but not managed Start or gameplay. This post-checkpoint source revision is unbuilt; current-client "
                "fixtures and live human review are still absent."
            ) if regular else (
                "The native execution contract has no adapter for this battle surface; selecting it cannot start a run."
            ),
            capability_ids=["battle.legend-tiers"] if sid.startswith("legend") else (
                ["builder-base.battles"] if sid == "builder" else (
                    ["battle.revenge"] if sid == "revenge" else ["battle.regular-ranked-split"])),
            prerequisites=prerequisites,
            recommended=(sid == "regular"),
            runtime_verified=False,
        ))
    return options


def build_hero_options(heroes: dict) -> list[dict]:
    options = []
    for hero in heroes["heroes"]:
        hid = hero["id"]
        unlock = hero["unlock_town_hall"]
        supported_by_inherited_engine = hid != "dragon-duke"
        hero_option = option(
            value=hid,
            label=hero["label"],
            summary=f"Unlocks at Town Hall {unlock}. Movement: {hero['movement']}.",
            description=(
                f"{HERO_PROSE[hid]} Available from Town Hall {unlock}. The Hero Hall holds six Heroes but only "
                f"{heroes['max_active_slots']} can be active at once, so selecting this Hero may require freeing a slot."
            ),
            availability="gated" if supported_by_inherited_engine else "planned",
            disabled_reason=(
                "Hero Hall recognition has not been captured on the current client, so the bot cannot confirm which "
                "Heroes are actually in your active slots."
            ) if supported_by_inherited_engine else (
                "Dragon Duke is not present in the inherited five-Hero deployment engine."
            ),
            capability_ids=["heroes.dragon-duke"] if hid == "dragon-duke" else ["heroes.six-slot-layout"],
            prerequisites=[f"Town Hall {unlock} or above"],
            recommended=(hid == "barbarian-king"),
        )
        # Machine-readable unlock data keeps the browser and loopback validator on the same
        # official current-client catalog as the native HeroLoadout contract.
        hero_option["unlock_town_hall"] = unlock
        hero_option["active_slot_eligible"] = bool(hero.get("active_slot_eligible"))
        options.append(hero_option)
    return options


def build_attack_script_options() -> list[dict]:
    options = [option(
        value="profile-current",
        label="Use profile selection",
        summary="Keeps the script already selected in the active profile.",
        description=(
            "Does not replace the active profile's script for this run. Use this with Standard deployment, or when "
            "the profile already names the exact CSV deployment you want."
        ),
        availability="gated",
        disabled_reason=(
            "The profile selection is wired, but its resolved deployment has not completed supervised "
            "current-client proof."
        ),
        capability_ids=[],
        prerequisites=[],
        recommended=True,
    )]
    for path in sorted(ATTACK_SCRIPTS.glob("*.csv"), key=lambda item: item.stem.casefold()):
        # One inherited filename makes a prohibited behaviour claim. The file remains available to the
        # compatibility host, but the modern planner does not repeat or endorse that wording.
        if any(token in path.stem.casefold() for token in HIDDEN_SCRIPT_TOKENS):
            continue
        options.append(option(
            value=path.stem,
            label=path.stem,
            summary="Selects this exact bundled CSV for the current run only.",
            description=(
                f"Loads CSV/Attack/{path.name} as a one-run deployment override. The file's presence proves engine "
                "compatibility, not that its army is suitable for every Town Hall or current game layout."
            ),
            availability="gated",
            disabled_reason=(
                "The file is wired as a one-run override, but this exact deployment has not completed supervised "
                "current-client proof."
            ),
            capability_ids=[],
            prerequisites=["The active profile army matches the script"],
        ))
    return options


def build_presets(source: dict) -> dict:
    common = source.get("common_values", {})
    items = []
    for preset in source.get("presets", []):
        values = dict(common)
        values.update(preset.get("values", {}))
        items.append({
            "id": preset["id"],
            "town_hall": preset["town_hall"],
            "label": preset["label"],
            "summary": preset["summary"],
            "description": (
                f"{preset['description']} This preset attempts one supervised battle with the current trained army "
                "and never changes its training queue."
            ),
            "compatibility": preset["compatibility"],
            "source_note": preset["source_note"],
            "values": values,
        })
    return {
        "title": source["title"],
        "description": source["description"],
        "preserved_settings": list(source.get("preserved_settings", [])),
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the generated metadata would change")
    args = parser.parse_args()
    surfaces = load("battle-surfaces.json")
    heroes = load("heroes.json")
    presets = build_presets(load_document(PRESETS_SOURCE))

    settings = {
        "schema_version": 1,
        "surface": "run-planner",
        "title": "Run Planner",
        "description": (
            "Describes one run: where it attacks, when it stops, and what it does in between. Every control says "
            "whether the bot has actually been shown working."
        ),
        "presets": presets,
        "sections": [
            {
                "id": "destination",
                "tab_label": "Battle",
                "order": 10,
                "title": "Destination",
                "description": (
                    "Picks the exact battle surface. This is stored as an exact surface rather than a general mode, "
                    "so choosing Legend I cannot end up running the Legend III path."
                ),
                "settings": [
                    {
                        "id": "run.surface",
                        "type": "select",
                        "label": "Battle surface",
                        "summary": "The exact screen the run attacks from.",
                        "description": (
                            "Regular and Ranked are separate surfaces with separate rules, and the three Legend tiers "
                            "have different attack budgets. Picking the exact one keeps the bot from falling back to "
                            "whatever the old coordinates happen to respond to."
                        ),
                        "default": "regular",
                        "required": True,
                        "engine_binding": "RunIntent.surface_id",
                        "options": build_surface_options(surfaces),
                    },
                    {
                        "id": "run.strategy",
                        "type": "select",
                        "label": "Attack strategy",
                        "summary": "Which deployment routine runs once a base is found.",
                        "description": (
                            "Strategies come from the existing attack code. The CSV strategies are the inherited "
                            "scripted deployments; the others depend on recognition that has not been re-confirmed yet."
                        ),
                        "default": "legacy.csv",
                        "required": True,
                        "engine_binding": "RunPlan.strategy",
                        "options": [
                            option("legacy.csv", "Scripted (CSV)",
                                   "Runs a deployment script from the Strategies folder.",
                                   "Uses the CSV deployment scripts that ship with the bot. This is the most "
                                   "predictable option because the deployment order is written down rather than "
                                   "decided from the base layout.",
                                   "gated", [], ["At least one CSV strategy present"], recommended=True,
                                   disabled_reason="The CSV actuator is wired, but a complete current-client deployment has not passed supervised review."),
                            option("legacy.standard", "Standard deployment",
                                   "The built-in side and line deployment routine.",
                                   "An older-binary supervised run confirmed Standard could issue the trained-army and selected-"
                                   "Hero deployment, observe an empty troop bar, and return home. That single "
                                   "completion confirms the route and actuator, not strategy quality; it did not "
                                   "exercise planned ability or spell actions. The 2026-08-14 bea12973 LocalRuntime "
                                   "checkpoint passed install, idle launch, and exact-current no-input managed-engine "
                                   "initialization. This source revision is post-checkpoint and unbuilt; neither the "
                                   "checkpoint nor current source proves managed Start or current-client gameplay.",
                                   "gated", [], ["A ready trained army", "A supervised diagnostic operator"],
                                   disabled_reason="The 2026-08-14 bea12973 LocalRuntime checkpoint passed no-input managed-engine initialization, but not managed Start or gameplay. This post-checkpoint source revision is unbuilt; current-client fixtures and live human review remain absent.",
                                   warning="The historical gameplay receipt proves an older build only; the bea12973 checkpoint proves the current managed engine can initialize without emulator or game input."),
                            option("smart.local", "Smart Attack (research-guided)",
                                   "Concentrates the current army using a Town Hall-aware local policy.",
                                   "The deterministic Town Hall policy is versioned in config/game/smart-attack-"
                                   "strategies.json and executed locally. One older-binary bounded supervised TH17 run observed "
                                   "three zoom gestures, 240 red-line points, deterministic BL-side selection, "
                                   "23-to-zero troop deployment, four selected Hero phase commands, Rage 3-to-zero, "
                                   "one Freeze decrement, and an automatic one-battle stop. The 2026-08-14 bea12973 "
                                   "LocalRuntime checkpoint passed install, idle launch, and exact-current no-input "
                                   "managed-engine initialization. This source revision is post-checkpoint and unbuilt; "
                                   "neither the checkpoint nor current source verifies managed Start, current-"
                                   "client gameplay, fixtures, live human review, strategy quality, or every Town Hall and army.",
                                   "gated", [], ["A ready trained army", "A supervised diagnostic operator"],
                                   disabled_reason="The 2026-08-14 bea12973 LocalRuntime checkpoint passed no-input managed-engine initialization, but not managed Start or gameplay. This post-checkpoint source revision is unbuilt; current-client fixtures and live human review remain absent.",
                                    warning="Historical TH17 mechanics evidence exists; bea12973 adds exact-current no-input managed-engine initialization, not gameplay proof."),
                             option("home.collectors", "Home maintenance",
                                    "Run selected one-shot Home Village collection tasks without matchmaking.",
                                    "Runs a bounded Home pass for collectors, the Loot Cart, a full Treasury, and, when explicitly "
                                    "enabled, the startup Daily Reward. It re-proves Home and stops. It cannot search, attack, "
                                    "train, donate, upgrade, enter the Laboratory, run Clan Games, or rotate accounts.",
                                    "gated", ["village.collectors", "village.loot-cart", "village.treasury", "events.daily-reward"], ["At least one Home task enabled", "A supervised diagnostic operator"],
                                    disabled_reason="Current-client collector, Loot Cart, Treasury, and Daily Reward handling still need supervised runtime receipts.",
                                    warning="Diagnostic only until supervised current-client Home maintenance receipts are recorded."),
                            option("home.clan-request", "Home maintenance - Clan request only",
                                   "Request Clan Castle reinforcements once, without donating or matchmaking.",
                                   "Runs one bounded request-only pass on the exact active profile and emulator instance. "
                                   "It requires a fresh Available button, permits one Send, proves the fresh transition "
                                   "to AlreadyMade, re-proves Home Village, then stops. It never enters donation, army "
                                   "editing, training, collectors, upgrades, events, account rotation, or battle paths.",
                                   "gated", ["village.clan-request"], ["Request when available enabled", "Exact emulator instance", "A supervised diagnostic operator"],
                                   disabled_reason="Current-client Clan request recognition still needs a supervised runtime receipt.",
                                   warning="Diagnostic only: this may post one real Clan request. Send is never retried."),
                            option("legacy.smart-farm", "Smart farm",
                                   "Targets collectors and storages based on the base layout.",
                                   "Reads the base to choose where to drop, which needs current building recognition "
                                   "including the Town Hall 18 additions.",
                                   "planned", ["village.town-hall-18"], ["Current building recognition"],
                                   disabled_reason="The native execution contract has no Smart farm adapter."),
                            option("builder.baby-dragon", "Builder Base routine",
                                   "Deployment routine for Builder Base battles.",
                                   "A Builder Base specific deployment. It is not implemented against the current "
                                   "Builder Base layout yet.",
                                   "planned", ["builder-base.battles"], ["Builder Base recognition"],
                                   disabled_reason="Not implemented for the current Builder Base layout."),
                        ],
                    },
                    {
                        "id": "run.attack_script",
                        "type": "select",
                        "label": "Attack script",
                        "summary": "The exact bundled CSV deployment used for this run.",
                        "description": (
                            "A named script overrides both dead-base and live-base CSV selection in memory for one "
                            "run, then the saved profile selection is restored. Choosing a file never changes the "
                            "profile and never starts the bot."
                        ),
                        "default": "profile-current",
                        "required": True,
                        "engine_binding": "RunPlan.attack_script",
                        "options": build_attack_script_options(),
                    },
                ],
            },
            {
                "id": "heroes",
                "tab_label": "Heroes",
                "order": 15,
                "title": "Heroes",
                "description": (
                    "Chooses which Heroes the run treats as active. The Hero Hall holds six but only four can be "
                    "active at once, so this is a selection rather than a fixed list."
                ),
                "settings": [
                    {
                        "id": "run.town_hall",
                        "type": "integer",
                        "label": "Planned Town Hall",
                        "summary": "Exact Home Village Town Hall expected for this run; zero detects it at Start.",
                        "description": (
                            "Every Town Hall starting point writes its exact level here. A Custom plan may keep zero, "
                            "which means the native engine must freshly detect the current account before validating "
                            "Hero unlocks. A nonzero value must exactly match that fresh detection or Start fails "
                            "before training, maintenance, search, or deployment."
                        ),
                        "default": 0,
                        "required": False,
                        "engine_binding": "RunPlan.planned_town_hall",
                        "unit": "Town Hall (0 = detect at Start)",
                        "validation": {"minimum": 0, "maximum": 18, "step": 1},
                    },
                    {
                        "id": "run.heroes",
                        "type": "multi-select",
                        "label": "Active Heroes",
                        "summary": "Up to four Heroes from the six in the Hero Hall.",
                        "description": (
                            "Heroes below your Town Hall level are released automatically rather than left selected, "
                            "so the run never plans around a Hero you cannot field. In current-trained-army mode the "
                            "selected Heroes are deployed when their attack-bar slots are present, but the bot does not "
                            "open Hero Hall or wait for Hero training."
                        ),
                        "default": "barbarian-king",
                        "required": False,
                        "engine_binding": "HeroLoadout.hero_ids",
                        "options": build_hero_options(heroes),
                        "max_selected": heroes["max_active_slots"],
                    },
                ],
            },
            {
                "id": "environment",
                "tab_label": "Emulator",
                "order": 20,
                "title": "Emulator",
                "description": (
                    "Chooses which Android emulator the run drives and which instance of it, since a single machine "
                    "commonly has several instances configured."
                ),
                "settings": [
                    {
                        "id": "runtime.emulator",
                        "type": "select",
                        "label": "Emulator",
                        "summary": "Which emulator the bot attaches to.",
                        "description": (
                            "Leave this on automatic unless you run more than one emulator. MEmu, LDPlayer 9 and "
                            "MuMu have native adapters, but each still needs a dated controlled run on its current "
                            "release before support can be promoted."
                        ),
                        "default": "auto",
                        "required": True,
                        "engine_binding": "RunPlan.emulator",
                        "options": [
                            option("auto", "Detect automatically",
                                   "Uses whichever supported emulator is already running.",
                                   "Looks for a running, supported emulator and attaches to it. This is the right "
                                   "choice for a single-instance setup.",
                                   "available", [], [], recommended=True),
                            option("bluestacks5", "BlueStacks 5",
                                   "The inherited BlueStacks 5 backend.",
                                   "An older binary was exercised on BlueStacks 5.22.252.1008/Pie64 through exact window binding, ADB "
                                   "readiness, current-client game readiness, and bounded Start/Stop smoke tests. "
                                   "The 2026-08-14 bea12973 LocalRuntime checkpoint was installed, launched through "
                                   "its Windows shortcut, and kept connected-but-idle. After a fresh reboot its exact "
                                   "backend passed the no-input managed-engine check while BlueStacks remained not "
                                   "launched. No managed Start, emulator attachment, or gameplay was exercised. This "
                                   "source revision is post-checkpoint and unbuilt.",
                                   "gated", ["emulator.bluestacks5"], ["BlueStacks 5 installed", "Exact instance selected", "A supervised diagnostic operator"],
                                   disabled_reason="The 2026-08-14 bea12973 LocalRuntime checkpoint passed connected idle launch and no-input managed-engine initialization, but did not attach BlueStacks or run gameplay. This post-checkpoint source revision is unbuilt; capture/input fixtures and live human review remain absent.",
                                   warning="Treat BlueStacks gameplay as unverified; bea12973 proves engine initialization only, with BlueStacks deliberately not launched."),
                            option("memu", "MEmu",
                                   "Inherited exact-instance MEmu backend.",
                                   "Discovers MEmu VM instances, reads their ADB host and port from VM information, "
                                   "uses the emulator-owned ADB when available, and selects background capture from "
                                   "the active renderer. The architecture was compared with the MIT MyBotPy MEmu "
                                   "implementation, but no code or templates were imported and no local MEmu runtime "
                                   "test is available on this machine.",
                                   "gated", ["emulator.memu"], ["MEmu installed", "Exact instance selected"],
                                   disabled_reason="Adapter is statically checked but has not passed a current MEmu 9.5.3 hardware smoke test.",
                                   warning="Do not assume that ADB connection alone proves capture, clicks, drag, zoom, or recovery."),
                            option("nox", "Nox",
                                   "The inherited Nox backend.",
                                   "Carried over from the upstream bot and not re-tested against current Nox builds.",
                                   "gated", [], ["Nox installed"],
                                   disabled_reason="Not re-tested against current Nox builds."),
                            option("ldplayer9", "LDPlayer 9",
                                   "New adapter with multi-instance ADB addressing.",
                                   "Discovers installed instances and addresses them on port 5554 plus twice the "
                                   "instance index, which is how LDPlayer 9 assigns ADB ports to multiple instances.",
                                   "gated", ["emulator.ldplayer9"], ["LDPlayer 9 installed"],
                                   disabled_reason="Adapter is written but has not been run against real hardware.",
                                   warning="Expect to report problems from the first few runs."),
                            option("mumu", "MuMu Player 12",
                                   "New adapter reading per-instance ADB ports.",
                                   "Reads each instance's ADB endpoint from the emulator rather than assuming a fixed "
                                   "port, and adapts background capture to the active renderer.",
                                   "gated", ["emulator.mumu"], ["MuMu Player 12 installed"],
                                   disabled_reason="Adapter is written but has not been run against real hardware.",
                                   warning="Expect to report problems from the first few runs."),
                        ],
                    },
                    {
                        "id": "runtime.instance",
                        "type": "instance-select",
                        "label": "Instance",
                        "summary": "Which emulator instance to attach to.",
                        "description": (
                            "Choose the exact named instance shown by the attached emulator. BlueStacks 5 requires an "
                            "explicit instance so capture, input, and the native controller dock cannot target "
                            "different accounts."
                        ),
                        "default": "",
                        "required": False,
                        "engine_binding": "RunPlan.emulator_instance",
                        "empty_state": "Select the exact attached instance.",
                        "validation": {"max_length": 64},
                    },
                ],
            },
            {
                "id": "limits",
                "tab_label": "Limits",
                "order": 30,
                "title": "Stop conditions",
                "description": (
                    "Decides when the run ends. Any condition that is set can stop the run; leaving a value at zero "
                    "turns that condition off."
                ),
                "settings": [
                    {
                        "id": "run.duration_minutes",
                        "type": "integer",
                        "label": "Run for",
                        "summary": "Stop after this many minutes. Zero means no time limit.",
                        "description": (
                            "Measured from the moment the run starts, not from when the first battle begins, so time "
                            "spent waiting for troops counts against it."
                        ),
                        "default": 0,
                        "required": False,
                        "engine_binding": "RunPlan.duration_minutes",
                        "unit": "minutes",
                        "validation": {"minimum": 0, "maximum": 1440, "step": 1},
                    },
                    {
                        "id": "run.max_battles",
                        "type": "integer",
                        "label": "Battle limit",
                        "summary": "Stop after this many battles. Zero means no limit.",
                        "description": (
                            "Counts every battle the run starts, won or lost. On a surface with a limited attack "
                            "budget the remaining count still applies on top of this."
                        ),
                        "default": 1,
                        "required": False,
                        "engine_binding": "RunPlan.max_battles",
                        "unit": "battles",
                        "validation": {"minimum": 0, "maximum": 500, "step": 1},
                    },
                    {
                        "id": "run.stop_on_star_bonus",
                        "type": "boolean",
                        "label": "Stop at Star Bonus",
                        "summary": "Stop once the Star Bonus is earned.",
                        "description": (
                            "Ends the run as soon as the Star Bonus is complete, which is the usual stopping point "
                            "for a daily farming session."
                        ),
                        "default": False,
                        "required": False,
                        "engine_binding": "RunPlan.stop_on_star_bonus",
                    },
                    {
                        "id": "run.max_failures",
                        "type": "integer",
                        "label": "Failure limit",
                        "summary": "Stop after this many consecutive problems.",
                        "description": (
                            "A failure is a battle that could not be completed, not a battle that was lost. Keep this "
                            "low while testing an unverified surface so a broken run stops quickly."
                        ),
                        "default": 3,
                        "required": True,
                        "engine_binding": "RunPlan.max_failures",
                        "unit": "failures",
                        "validation": {"minimum": 0, "maximum": 100, "step": 1},
                    },
                ],
            },
            {
                "id": "resources",
                "tab_label": "Loot",
                "order": 40,
                "title": "Resource targets",
                "description": (
                    "Stops the run once a resource total has been collected. Each target is counted across the run, "
                    "and zero turns the target off."
                ),
                "settings": [
                    {
                        "id": "target.gold",
                        "type": "integer",
                        "label": "Gold",
                        "summary": "Stop once this much Gold has been collected.",
                        "description": "Counts Gold taken during the run, not the Gold currently in your storages.",
                        "default": 0,
                        "required": False,
                        "engine_binding": "RunPlan.target_gold",
                        "unit": "gold",
                        "validation": {"minimum": 0, "maximum": 2000000000, "step": 1000},
                    },
                    {
                        "id": "target.elixir",
                        "type": "integer",
                        "label": "Elixir",
                        "summary": "Stop once this much Elixir has been collected.",
                        "description": "Counts Elixir taken during the run, not the Elixir currently in your storages.",
                        "default": 0,
                        "required": False,
                        "engine_binding": "RunPlan.target_elixir",
                        "unit": "elixir",
                        "validation": {"minimum": 0, "maximum": 2000000000, "step": 1000},
                    },
                    {
                        "id": "target.dark_elixir",
                        "type": "integer",
                        "label": "Dark Elixir",
                        "summary": "Stop once this much Dark Elixir has been collected.",
                        "description": (
                            "Counts Dark Elixir taken during the run. Dark Elixir loot is much smaller than Gold or "
                            "Elixir, so this target wants a correspondingly smaller number."
                        ),
                        "default": 0,
                        "required": False,
                        "engine_binding": "RunPlan.target_dark_elixir",
                        "unit": "dark elixir",
                        "validation": {"minimum": 0, "maximum": 2000000000, "step": 100},
                    },
                ],
            },
            {
                "id": "maintenance",
                "tab_label": "Upkeep",
                "order": 50,
                "title": "Between battles",
                "description": "What the run does with the resources it collects, and which accounts it rotates through.",
                "settings": [
                    {
                        "id": "upgrade.policy",
                        "type": "select",
                        "label": "Upgrades",
                        "summary": "What the bot spends resources on between battles.",
                        "description": (
                            "Upgrade handling reads menus and costs from the client. Anything beyond walls needs "
                            "current recognition of the upgrade screens, which has not been re-confirmed."
                        ),
                        "default": "disabled",
                        "required": True,
                        "engine_binding": "RunPlan.upgrade_policy",
                        "options": [
                            option("disabled", "Nothing",
                                   "Collect resources and leave them alone.",
                                   "The run does not spend anything. This is the right setting while you are "
                                   "confirming that a surface works at all.",
                                   "available", [], [], recommended=True),
                            option("walls", "Walls only",
                                   "Spend surplus on wall upgrades.",
                                   "Puts spare resources into walls, which is the least risky upgrade because it "
                                   "does not occupy a Builder.",
                                   "gated", ["village.upgrades-home", "village.town-hall-18"], ["Current wall recognition"],
                                   disabled_reason="Wall levels have not been re-confirmed for the current client."),
                            option("suggested", "Suggested upgrades",
                                   "Follow the in-game suggested upgrade list.",
                                   "Uses the game's own suggestions, which requires reading the upgrade menu as it "
                                   "currently appears.",
                                   "planned", ["village.upgrades-home"], ["Upgrade menu recognition"],
                                   disabled_reason="The native execution contract has no suggested-upgrade adapter."),
                            option("all", "Everything",
                                   "Walls, buildings, laboratory, and Heroes.",
                                   "The full upgrade routine across every category. It depends on the six-Hero "
                                   "layout and the Town Hall 18 building set.",
                                   "planned", ["village.upgrades-home", "village.laboratory", "village.town-hall-18", "heroes.six-slot-layout"],
                                   ["Current upgrade and Hero recognition"],
                                   disabled_reason="Not implemented against the current upgrade and Hero screens."),
                        ],
                    },
                    {
                        "id": "account.queue",
                        "type": "profile-queue",
                        "label": "Account queue",
                        "summary": "Local bot profiles to rotate through, in order.",
                        "description": (
                            "References bot profiles stored on this machine. No credentials, tokens, or Supercell ID "
                            "details are kept here; the queue only records which local profile to switch to next."
                        ),
                        "default": "",
                        "required": False,
                        "engine_binding": "AccountQueue.profile_ids",
                        "native_fixed_value": "",
                        "native_fixed_reason": "Planner-driven account rotation has no native adapter; the current inspected account is pinned for the run.",
                        "empty_state": "No profiles queued. Stays on this profile.",
                        "validation": {"max_items": 32},
                    },
                ],
            },
            {
                "id": "army",
                "tab_label": "Army",
                "order": 22,
                "title": "Army",
                "description": (
                    "How the army gets built between battles. Training no longer has wait times, so this is about "
                    "what to build rather than how long to wait for it."
                ),
                "settings": [
                    {
                        "id": "army.source",
                        "type": "select",
                        "label": "Army source",
                        "summary": "Where the troop composition comes from.",
                        "description": (
                            "Army Recipes replaced the old training queue, so a saved recipe is now the natural unit "
                            "of army setup rather than a per-troop count."
                        ),
                        "default": "recipe",
                        "required": True,
                        "engine_binding": "RunPlan.army_source",
                        "options": [
                            option("recipe", "Saved Army Recipe",
                                   "Use one of the recipes saved in game.",
                                   "Picks a saved Army Recipe and trains it. This is how the current client expects "
                                   "armies to be set up, and it survives balance changes better than a fixed list.",
                                   "gated", ["army.recipes"], ["At least one saved recipe"],
                                   recommended=True,
                                   disabled_reason="Army Recipe screen recognition has not been captured."),
                            option("cookbook", "Cookbook entry",
                                   "Use an entry from the Cookbook tab.",
                                   "The Cookbook holds shared and suggested armies. Selecting from it needs the third "
                                   "army tab to be recognised.",
                                   "planned", ["army.cookbook"], ["Cookbook tab available"],
                                   disabled_reason="The native execution contract has no Cookbook army adapter."),
                            option("legacy-list", "Fixed troop list",
                                   "The inherited per-troop composition.",
                                   "Trains a fixed list of troops the way the older bot did. Kept because it does not "
                                   "depend on recipe recognition, but it ignores anything the game has changed since.",
                                   "planned", [], ["Troop training screen recognition"],
                                   disabled_reason="The native execution contract has no fixed-list army-source adapter."),
                        ],
                    },
                    {
                        "id": "army.recipe_name",
                        "type": "text",
                        "label": "Recipe name",
                        "summary": "Which saved recipe to train.",
                        "description": (
                            "The exact recipe name as it appears in game. Left blank, the run uses whichever recipe "
                            "is already selected rather than switching."
                        ),
                        "default": "",
                        "required": False,
                        "engine_binding": "RunPlan.army_recipe_name",
                        "native_fixed_value": "",
                        "native_fixed_reason": "Named Army Recipe selection is not wired; the run can only use the active profile army.",
                        "validation": {"max_length": 64},
                    },
                    {
                        "id": "army.manage_training",
                        "type": "boolean",
                        "label": "Manage training",
                        "summary": "Keep this run from changing the training queue.",
                        "description": (
                            "Planned combat uses one army already trained in game. The bot checks whether that army "
                            "is ready, then attempts one battle without boosting Super Troops, inspecting or editing "
                            "Quick Train, removing troops, queuing troops or spells, or building siege machines."
                        ),
                        "default": False,
                        "required": False,
                        "engine_binding": "RunPlan.army_manage_training",
                        "native_fixed_value": False,
                        "native_fixed_reason": (
                            "The inherited profile training routine exposes unbounded hidden actuators; planned "
                            "runs use the closed-world current-army one-battle route."
                        ),
                        "availability": "unsupported",
                        "runtime_verified": False,
                        "capability_ids": ["army.training"],
                        "prerequisites": ["A plan-owned exact training recipe and bounded training-screen actuator"],
                        "disabled_reason": (
                            "The inherited training routine selects profile-owned Quick Train or custom-army paths "
                            "and may boost, delete, or queue units outside the plan."
                        ),
                        "warning": "Diagnostic acknowledgement cannot enable managed training in this build.",
                    },
                    {
                        "id": "army.wait_for_full",
                        "type": "boolean",
                        "label": "Wait for a full army",
                        "summary": "Do not attack with a partly trained army.",
                        "description": (
                            "Holds the run until the army is complete. Worth leaving on: attacking short-handed "
                            "wastes the attack more often than the wait costs."
                        ),
                        "default": True,
                        "required": False,
                        "engine_binding": "RunPlan.army_wait_for_full",
                    },
                    {
                        "id": "army.train_spells",
                        "type": "boolean",
                        "label": "Train spells",
                        "summary": "Brew spells as well as troops.",
                        "description": "Includes the spell portion of the army. Turn off to save Elixir on cheap farming runs.",
                        "default": False,
                        "required": False,
                        "engine_binding": "RunPlan.army_train_spells",
                    },
                    {
                        "id": "army.train_sieges",
                        "type": "boolean",
                        "label": "Build sieges",
                        "summary": "Build a siege machine each run.",
                        "description": "Builds the siege machine the recipe calls for. Only useful where a Clan Castle troop matters.",
                        "default": False,
                        "required": False,
                        "engine_binding": "RunPlan.army_train_sieges",
                    },
                ],
            },
            {
                "id": "search",
                "tab_label": "Search",
                "order": 26,
                "title": "Base search",
                "description": (
                    "What counts as a base worth attacking. Every filter that is set has to pass before the run "
                    "commits to an attack; a zero means the filter is off."
                ),
                "settings": [
                    {
                        "id": "search.min_gold",
                        "type": "integer",
                        "label": "Minimum Gold",
                        "summary": "Skip bases offering less Gold than this.",
                        "description": "Reads available loot before committing. Set to zero to attack regardless of Gold on offer.",
                        "default": 0,
                        "required": False,
                        "engine_binding": "RunPlan.search_min_gold",
                        "unit": "gold",
                        "validation": {"minimum": 0, "maximum": 2000000, "step": 10000},
                    },
                    {
                        "id": "search.min_elixir",
                        "type": "integer",
                        "label": "Minimum Elixir",
                        "summary": "Skip bases offering less Elixir than this.",
                        "description": "Same idea as the Gold filter, applied to Elixir. Zero turns it off.",
                        "default": 0,
                        "required": False,
                        "engine_binding": "RunPlan.search_min_elixir",
                        "unit": "elixir",
                        "validation": {"minimum": 0, "maximum": 2000000, "step": 10000},
                    },
                    {
                        "id": "search.min_dark",
                        "type": "integer",
                        "label": "Min Dark Elixir",
                        "summary": "Skip bases offering less Dark Elixir than this.",
                        "description": (
                            "Dark Elixir loot is an order of magnitude smaller than Gold or Elixir, so this wants a "
                            "correspondingly smaller number."
                        ),
                        "default": 0,
                        "required": False,
                        "engine_binding": "RunPlan.search_min_dark",
                        "unit": "dark elixir",
                        "validation": {"minimum": 0, "maximum": 50000, "step": 100},
                    },
                    {
                        "id": "search.max_seconds",
                        "type": "integer",
                        "label": "Give up after",
                        "summary": "Stop searching once this long has passed.",
                        "description": (
                            "A long search costs a Gold search fee each skip. This caps how long the run will hunt "
                            "before taking what it can find. Zero means no cap."
                        ),
                        "default": 0,
                        "required": False,
                        "engine_binding": "RunPlan.search_max_seconds",
                        "native_fixed_value": 0,
                        "native_fixed_reason": "The inherited search loop has no safe elapsed-time exit, so this value must remain zero.",
                        "unit": "seconds",
                        "validation": {"minimum": 0, "maximum": 3600, "step": 15},
                    },
                    {
                        "id": "search.town_hall_filter",
                        "type": "select",
                        "label": "Town Hall filter",
                        "summary": "Which defender Town Hall levels to accept.",
                        "description": (
                            "Filtering by defender Town Hall needs the bot to read the Town Hall on the search screen, "
                            "which changed with Town Hall 18."
                        ),
                        "default": "any",
                        "required": True,
                        "engine_binding": "RunPlan.search_town_hall_filter",
                        "options": [
                            option("any", "Any Town Hall",
                                   "Accept whatever matchmaking offers.",
                                   "No filtering. The safest setting while search-screen recognition is unconfirmed, "
                                   "because it does not depend on reading the defender's Town Hall at all.",
                                   "available", [], [], recommended=True),
                            option("lower-only", "Lower than mine",
                                   "Only bases below your Town Hall level.",
                                   "Prefers weaker defenders. Requires reading the defender Town Hall reliably.",
                                   "planned", ["village.town-hall-18"], ["Search screen Town Hall recognition"],
                                   disabled_reason="The native execution contract currently accepts only Any Town Hall."),
                            option("same-or-lower", "Same or lower",
                                   "Bases at or below your Town Hall level.",
                                   "A looser version of the above, trading some safety for a shorter search.",
                                   "planned", ["village.town-hall-18"], ["Search screen Town Hall recognition"],
                                   disabled_reason="The native execution contract currently accepts only Any Town Hall."),
                        ],
                    },
                ],
            },
            {
                "id": "donate",
                "tab_label": "Donate",
                "order": 44,
                "title": "Donating",
                "description": (
                    "Answering clan mate requests between battles. Donation happens through clan chat, whose "
                    "navigation changed when Global Chat arrived."
                ),
                "settings": [
                    {
                        "id": "donate.mode",
                        "type": "select",
                        "label": "Donate",
                        "summary": "Whether and how to answer requests.",
                        "description": (
                            "Donating earns Clan XP and keeps a clan happy, but it costs training resources and time "
                            "between attacks."
                        ),
                        "default": "off",
                        "required": True,
                        "engine_binding": "RunPlan.donate_mode",
                        "options": [
                            option("off", "Do not donate",
                                   "Ignore requests entirely.",
                                   "Skips the clan chat step completely, which is also the fastest option between "
                                   "battles and the one least dependent on chat recognition.",
                                   "available", [], [], recommended=True),
                            option("matching", "Only matching requests",
                                   "Donate when the request text matches.",
                                   "Reads the request and donates only what was asked for. Depends on reading clan "
                                   "chat, which moved when Global Chat was added.",
                                   "gated", ["village.donations", "chat.global-chat"], ["Clan chat recognition"],
                                   disabled_reason="Clan chat recognition has not been captured since Global Chat."),
                            option("anything", "Donate anything",
                                   "Fill any request with whatever is available.",
                                   "Donates without matching the request. Fast, and reliably annoys clan mates who "
                                   "asked for something specific.",
                                   "gated", ["village.donations", "chat.global-chat"], ["Clan chat recognition"],
                                   disabled_reason="Clan chat recognition has not been captured since Global Chat.",
                                   warning="Expect complaints if your clan cares what it receives."),
                        ],
                    },
                    {
                        "id": "donate.keep_army",
                        "type": "boolean",
                        "label": "Protect attack army",
                        "summary": "Protect troops the run needs to attack with.",
                        "description": (
                            "Refuses any donation that would leave the army short. Worth keeping on, since donating "
                            "the army away and then attacking with what is left wastes the attack."
                        ),
                        "default": True,
                        "required": False,
                        "engine_binding": "RunPlan.donate_keep_army",
                        "native_fixed_value": True,
                        "native_fixed_reason": "The native planner always protects the attack army; allowing donations to consume it is not wired.",
                    },
                    {
                        "id": "donate.max_per_run",
                        "type": "integer",
                        "label": "Donation limit",
                        "summary": "Stop donating after this many per run. Zero means no limit.",
                        "description": "Caps how much time and Elixir a single run puts into donating.",
                        "default": 0,
                        "required": False,
                        "engine_binding": "RunPlan.donate_max_per_run",
                        "native_fixed_value": 0,
                        "native_fixed_reason": "Per-run donation accounting is not wired, so the limit must remain zero.",
                        "unit": "donations",
                        "validation": {"minimum": 0, "maximum": 500, "step": 5},
                    },
                    {
                        "id": "donate.request_when_short",
                        "type": "boolean",
                        "label": "Request when available",
                        "summary": "Ask the clan for Clan Castle reinforcements when the request button is available.",
                        "description": "Allows the explicit request-only route to post at most one request after fresh Available recognition.",
                        "default": False,
                        "required": False,
                        "engine_binding": "RunPlan.donate_request_when_short",
                        "availability": "gated",
                        "runtime_verified": False,
                        "capability_ids": ["village.clan-request"],
                        "prerequisites": ["Current Clan Castle request dialog recognition"],
                        "disabled_reason": "The request path is inherited but has no current-client supervised receipt.",
                        "warning": "A diagnostic run may post a real clan request.",
                    },
                ],
            },
            {
                "id": "events",
                "tab_label": "Events",
                "order": 46,
                "title": "Events and lab",
                "description": (
                    "The recurring things worth doing between attacks: Clan Games challenges and keeping the "
                    "laboratory busy."
                ),
                "settings": [
                    {
                        "id": "events.clan_games",
                        "type": "boolean",
                        "label": "Play Clan Games",
                        "summary": "Pick up and complete Clan Games challenges.",
                        "description": (
                            "Clan Games run on a schedule and reward magic items. Automating them means reading the "
                            "challenge list and tracking points, neither of which has been re-confirmed."
                        ),
                        "default": False,
                        "required": False,
                        "engine_binding": "RunPlan.events_clan_games",
                        "availability": "gated",
                        "runtime_verified": False,
                        "capability_ids": ["events.clan-games"],
                        "prerequisites": ["Current Clan Games challenge list and progress recognition"],
                        "disabled_reason": "Clan Games logic is inherited but has not been replayed on the current client.",
                        "warning": "A diagnostic run can accept or abandon a real challenge.",
                    },
                    {
                        "id": "events.clan_games_point_cap",
                        "type": "integer",
                        "label": "Stop at points",
                        "summary": "Stop once this many Clan Games points are earned.",
                        "description": (
                            "Clan Games caps individual scoring, and going past the cap earns nothing. Set this to "
                            "your clan's agreed limit. Zero means play until the event ends."
                        ),
                        "default": 0,
                        "required": False,
                        "engine_binding": "RunPlan.events_clan_games_point_cap",
                        "native_fixed_value": 0,
                        "native_fixed_reason": "Clan Games point accounting is not wired, so this cap must remain zero.",
                        "unit": "points",
                        "validation": {"minimum": 0, "maximum": 10000, "step": 100},
                    },
                    {
                        "id": "events.laboratory",
                        "type": "select",
                        "label": "Laboratory",
                        "summary": "What to research when the lab is free.",
                        "description": (
                            "Keeping the laboratory busy is most of long-term progress. Choosing what it researches "
                            "means reading upgrade costs and levels off the lab screen."
                        ),
                        "default": "off",
                        "required": True,
                        "engine_binding": "RunPlan.events_laboratory",
                        "options": [
                            option("off", "Leave it alone",
                                   "Do not start research.",
                                   "The run ignores the laboratory. Right setting while lab recognition is unconfirmed.",
                                   "available", [], [], recommended=True),
                            option("cheapest", "Cheapest available",
                                   "Always start the cheapest research.",
                                   "Keeps the lab permanently busy at the lowest cost. Needs the lab screen read "
                                   "accurately, including the Town Hall 18 additions.",
                                   "planned", ["village.laboratory"], ["Laboratory screen recognition"],
                                   disabled_reason="The native execution contract currently accepts only Laboratory off."),
                            option("priority-list", "Follow a priority list",
                                   "Work down a configured order.",
                                   "Researches in the order you specify, skipping anything unaffordable. Needs both "
                                   "lab recognition and a stored priority list.",
                                   "planned", ["village.laboratory"], ["Laboratory screen recognition"],
                                   disabled_reason="Priority lists are not implemented yet."),
                        ],
                    },
                    {
                        "id": "events.collect_resources",
                        "type": "boolean",
                        "label": "Collect collectors",
                        "summary": "Empty mines and collectors each pass.",
                        "description": (
                            "This is executed only by Home maintenance. The route skips full "
                            "storages, Loot Cart, Treasury, matchmaking, donations, upgrades, Laboratory, and Clan Games."
                        ),
                        "default": False,
                        "required": False,
                        "engine_binding": "RunPlan.events_collect_resources",
                        "availability": "gated",
                        "runtime_verified": False,
                        "capability_ids": ["village.collectors"],
                        "prerequisites": ["Current home-village collector recognition"],
                        "disabled_reason": "The bounded route is wired, but collector and full-storage handling lack a supervised current-client receipt.",
                        "warning": "Select Home maintenance and use a supervised diagnostic.",
                    },
                    {
                        "id": "events.collect_daily_reward",
                        "type": "boolean",
                        "label": "Claim startup Daily Reward",
                        "summary": "Claim at most one visible Daily Reward, then return Home.",
                        "description": (
                            "Only Home maintenance may use this. It recognizes the startup reward window, permits one "
                            "Claim input, never accepts a sell-or-convert-for-gems dialog, closes any remaining popup, "
                            "re-proves Home, and stops."
                        ),
                        "default": False,
                        "required": False,
                        "engine_binding": "RunPlan.events_collect_daily_reward",
                        "availability": "gated",
                        "runtime_verified": False,
                        "capability_ids": ["events.daily-reward"],
                        "prerequisites": ["Current startup Daily Reward recognition", "No-gems policy"],
                        "disabled_reason": "The bounded route needs one supervised current-client claim receipt.",
                        "warning": "This can claim a real account reward. It never converts a full reward into gems.",
                    },
                    {
                        "id": "events.collect_loot_cart",
                        "type": "boolean",
                        "label": "Collect Loot Cart",
                        "summary": "Open one recognized Loot Cart and press its exact Collect button once.",
                        "description": (
                            "Only Home maintenance may use this. It requires exactly one fresh cart match, permits one "
                            "cart-open input and one exact Collect input, passively re-proves Home, and stops. It never "
                            "opens chat, uses fallback coordinates, accepts a confirmation, or converts anything into gems."
                        ),
                        "default": False,
                        "required": False,
                        "engine_binding": "RunPlan.events_collect_loot_cart",
                        "availability": "gated",
                        "runtime_verified": False,
                        "capability_ids": ["village.loot-cart"],
                        "prerequisites": ["Current Loot Cart recognition", "Exact Collect-button recognition", "No-gems policy"],
                        "disabled_reason": "The bounded route needs one supervised current-client Loot Cart receipt.",
                        "warning": "This can transfer real Loot Cart resources. It never clicks confirmation or gem-conversion actions.",
                    },
                    {
                        "id": "events.collect_treasury",
                        "type": "boolean",
                        "label": "Collect full Treasury",
                        "summary": "Transfer a full Treasury through one exact, contextual confirmation.",
                        "description": (
                            "Only Home maintenance may use this. It requires an exact cached Clan Castle, refuses visibly "
                            "full Home storages, verifies the selected building and Treasury window, requires the Treasury "
                            "full indicator, and permits one Castle, entry, Collect, contextual Okay, and recognized close "
                            "input. It never locates a building, retries, uses fallback coordinates, or uses gems."
                        ),
                        "default": False,
                        "required": False,
                        "engine_binding": "RunPlan.events_collect_treasury",
                        "availability": "gated",
                        "runtime_verified": False,
                        "capability_ids": ["village.treasury"],
                        "prerequisites": ["Current Treasury recognition", "Exact cached Clan Castle", "No-gems policy"],
                        "disabled_reason": "The bounded route needs one supervised current-client Treasury receipt.",
                        "warning": "This can transfer real Treasury resources after one contextual Okay input; it never uses gems.",
                    },
                ],
            },
            {
                "id": "notify",
                "tab_label": "Notify",
                "order": 55,
                "title": "Notifications",
                "description": (
                    "Getting told when something happens, so a run does not need watching. These are bot features "
                    "rather than game ones, so they do not depend on client recognition."
                ),
                "settings": [
                    {
                        "id": "notify.on_stop",
                        "type": "boolean",
                        "label": "On run stop",
                        "summary": "Send a message whenever a run ends.",
                        "description": "Fires on every stop, including a clean finish, so a silent bot means it is still going.",
                        "default": False,
                        "required": False,
                        "engine_binding": "RunPlan.notify_on_stop",
                    },
                    {
                        "id": "notify.on_error",
                        "type": "boolean",
                        "label": "On errors",
                        "summary": "Send a message when the run hits a problem.",
                        "description": (
                            "Worth turning on before any diagnostic run, since an unverified surface is exactly the "
                            "case where you want to hear about a failure quickly."
                        ),
                        "default": True,
                        "required": False,
                        "engine_binding": "RunPlan.notify_on_error",
                    },
                    {
                        "id": "notify.channel",
                        "type": "select",
                        "label": "Send to",
                        "summary": "Where notifications go.",
                        "description": "Uses the credentials already stored in the bot's own settings. Nothing is stored in the run plan.",
                        "default": "log-only",
                        "required": True,
                        "engine_binding": "RunPlan.notify_channel",
                        "options": [
                            option("log-only", "Bot log only",
                                   "Write to the log and nowhere else.",
                                   "No external service involved. The message lands in the log window and the JSONL "
                                   "event stream, which is enough when you are at the machine.",
                                   "available", [], [], recommended=True),
                            option("telegram", "Telegram",
                                   "Send through the inherited Telegram integration.",
                                   "Uses the Telegram bot token configured in the bot's own settings. Carried over "
                                   "from upstream and not re-tested against the current Telegram API.",
                                   "planned", [], ["Telegram token configured in bot settings"],
                                   disabled_reason="The native execution contract currently accepts only Bot log notifications."),
                            option("windows-toast", "Windows notification",
                                   "Raise a desktop notification.",
                                   "A local desktop notification. Only useful if you are at the machine, in which "
                                   "case the log usually tells you more.",
                                   "planned", [], [], disabled_reason="Not implemented."),
                        ],
                    },
                ],
            },
            {
                "id": "diagnostics",
                "tab_label": "Debug",
                "order": 60,
                "title": "Diagnostics",
                "description": (
                    "Controls whether the run is allowed to attempt work that has not been demonstrated on the "
                    "current client, so that its behaviour can actually be observed."
                ),
                "settings": [
                    {
                        "id": "run.diagnostic_mode",
                        "type": "boolean",
                        "label": "Allow unverified",
                        "summary": "Run surfaces with no capture yet.",
                        "description": (
                            "A surface that refuses to start cannot be debugged, so this lets the run proceed anyway. "
                            "It changes nothing about what the bot has actually been shown to do: the session, its "
                            "snapshot, and every log line stay marked unverified, and that mark cannot be cleared "
                            "for the rest of the run."
                        ),
                        "default": False,
                        "required": False,
                        "engine_binding": "BattleRoute.diagnostic_enabled",
                    },
                    {
                        "id": "run.diagnostic_note",
                        "type": "text",
                        "label": "Diagnostic note",
                        "summary": "Who is watching this run, recorded with the results.",
                        "description": (
                            "Required before an unverified surface will start. It is written into the session so a "
                            "log read later makes clear the run was being observed rather than left unattended."
                        ),
                        "default": "",
                        "required": False,
                        "engine_binding": "BattleRoute.diagnostic_acknowledgement",
                        "empty_state": "Required before an unverified surface will start.",
                        "validation": {"max_length": 120},
                    },
                ],
            },
        ],
    }

    settings["sections"].append(json.loads(PACING_SECTION.read_text(encoding="utf-8-sig")))
    settings["sections"].sort(key=lambda section: section["order"])
    payload = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
    total = sum(len(section["settings"]) for section in settings["sections"])
    preset_total = len(settings["presets"]["items"])
    if args.check:
        current = OUT.read_text(encoding="utf-8-sig") if OUT.exists() else ""
        if current != payload:
            print(f"{OUT.relative_to(ROOT)} is out of date; run {Path(__file__).name}")
            return 1
        print(
            f"{OUT.relative_to(ROOT)} is up to date "
            f"({len(settings['sections'])} sections, {total} settings, {preset_total} presets)"
        )
        return 0
    OUT.write_text(payload, encoding="utf-8")
    print(
        f"Wrote {OUT.relative_to(ROOT)} with {len(settings['sections'])} sections, "
        f"{total} settings and {preset_total} presets"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
