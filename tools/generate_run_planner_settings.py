#!/usr/bin/env python3
"""Build the Run Planner metadata from the game catalogs.

The prose lives here; the identifiers, labels, and availability come from config/game/*.json so the planner cannot
drift from the catalog it is meant to describe. Run this after changing a catalog, then validate_ui_metadata.py.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "config/ui/run-planner.settings.json"


def load(name: str) -> dict:
    return json.loads((ROOT / "config/game" / name).read_text(encoding="utf-8-sig"))


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
           recommended=False, warning="", disabled_reason=""):
    if availability != "available" and not disabled_reason:
        raise ValueError(f"{value}: an unavailable option needs a disabled reason")
    return {
        "value": value,
        "label": label,
        "summary": summary,
        "description": description,
        "availability": availability,
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

        options.append(option(
            value=sid,
            label=surface["label"],
            summary=summary,
            description=prose,
            availability="gated",
            disabled_reason=(
                "No current-client capture has been recorded for this surface yet. You can still run it as a "
                "diagnostic to see how it behaves."
            ),
            capability_ids=["battle.legend-tiers"] if sid.startswith("legend") else (
                ["builder-base.additional-builder"] if sid == "builder" else (
                    ["battle.revenge"] if sid == "revenge" else ["battle.regular-ranked-split"])),
            prerequisites=prerequisites,
            recommended=(sid == "regular"),
        ))
    return options


def build_hero_options(heroes: dict) -> list[dict]:
    options = []
    for hero in heroes["heroes"]:
        hid = hero["id"]
        unlock = hero["unlock_town_hall"]
        options.append(option(
            value=hid,
            label=hero["label"],
            summary=f"Unlocks at Town Hall {unlock}. Movement: {hero['movement']}.",
            description=(
                f"{HERO_PROSE[hid]} Available from Town Hall {unlock}. The Hero Hall holds six Heroes but only "
                f"{heroes['max_active_slots']} can be active at once, so selecting this Hero may require freeing a slot."
            ),
            availability="gated",
            disabled_reason=(
                "Hero Hall recognition has not been captured on the current client, so the bot cannot confirm which "
                "Heroes are actually in your active slots."
            ),
            capability_ids=["heroes.dragon-duke"] if hid == "dragon-duke" else ["heroes.six-slot-layout"],
            prerequisites=[f"Town Hall {unlock} or above"],
            recommended=(hid == "barbarian-king"),
        ))
    return options


def main() -> int:
    surfaces = load("battle-surfaces.json")
    heroes = load("heroes.json")

    settings = {
        "schema_version": 1,
        "surface": "run-planner",
        "title": "Run Planner",
        "description": (
            "Describes one run: where it attacks, when it stops, and what it does in between. Every control says "
            "whether the bot has actually been shown working."
        ),
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
                                   "available", [], ["At least one CSV strategy present"], recommended=True),
                            option("legacy.standard", "Standard deployment",
                                   "The built-in side and line deployment routine.",
                                   "The inherited standard attack, which spreads troops along the chosen sides. It "
                                   "depends on troop-bar recognition that has not been re-confirmed on the current "
                                   "client.",
                                   "gated", [], ["Troop bar recognition"],
                                   disabled_reason="Troop bar recognition has not been captured on the current client."),
                            option("legacy.smart-farm", "Smart farm",
                                   "Targets collectors and storages based on the base layout.",
                                   "Reads the base to choose where to drop, which needs current building recognition "
                                   "including the Town Hall 18 additions.",
                                   "gated", ["village.town-hall-18"], ["Current building recognition"],
                                   disabled_reason="Building recognition has not been re-confirmed for Town Hall 18."),
                            option("builder.baby-dragon", "Builder Base routine",
                                   "Deployment routine for Builder Base battles.",
                                   "A Builder Base specific deployment. It is not implemented against the current "
                                   "Builder Base layout yet.",
                                   "planned", ["builder-base.additional-builder"], ["Builder Base recognition"],
                                   disabled_reason="Not implemented for the current Builder Base layout."),
                        ],
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
                        "id": "run.heroes",
                        "type": "multi-select",
                        "label": "Active Heroes",
                        "summary": "Up to four Heroes from the six in the Hero Hall.",
                        "description": (
                            "Heroes below your Town Hall level are released automatically rather than left selected, "
                            "so the run never plans around a Hero you cannot field."
                        ),
                        "default": "barbarian-king",
                        "required": False,
                        "engine_binding": "HeroLoadout.hero_ids",
                        "options": build_hero_options(heroes),
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
                            "Leave this on automatic unless you run more than one emulator. The LDPlayer 9 and MuMu "
                            "adapters are new: their discovery and ADB addressing are implemented, but they have not "
                            "been through a controlled test on real hardware yet."
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
                                   "Carried over from the upstream bot. It works against the versions the upstream "
                                   "project supported, which are older than the current release.",
                                   "gated", [], ["BlueStacks 5 installed"],
                                   disabled_reason="Not re-tested against current BlueStacks 5 builds."),
                            option("memu", "MEmu",
                                   "The inherited MEmu backend.",
                                   "Carried over from the upstream bot and not re-tested against current MEmu builds.",
                                   "gated", [], ["MEmu installed"],
                                   disabled_reason="Not re-tested against current MEmu builds."),
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
                            "Populated by asking the selected emulator what it has configured. Instance zero and the "
                            "later instances are addressed differently, which is a common source of the bot attaching "
                            "to the wrong window."
                        ),
                        "default": "",
                        "required": False,
                        "engine_binding": "RunPlan.emulator_instance",
                        "empty_state": "No instances found. Start the emulator once.",
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
                        "default": 0,
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
                                   "gated", ["village.town-hall-18"], ["Current wall recognition"],
                                   disabled_reason="Wall levels have not been re-confirmed for the current client."),
                            option("suggested", "Suggested upgrades",
                                   "Follow the in-game suggested upgrade list.",
                                   "Uses the game's own suggestions, which requires reading the upgrade menu as it "
                                   "currently appears.",
                                   "gated", ["builder-base.additional-builder"], ["Upgrade menu recognition"],
                                   disabled_reason="Upgrade menu recognition has not been captured."),
                            option("all", "Everything",
                                   "Walls, buildings, laboratory, and Heroes.",
                                   "The full upgrade routine across every category. It depends on the six-Hero "
                                   "layout and the Town Hall 18 building set.",
                                   "planned", ["village.town-hall-18", "heroes.six-slot-layout"],
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
                                   "gated", ["army.cookbook"], ["Cookbook tab available"],
                                   disabled_reason="Cookbook tab recognition has not been captured."),
                            option("legacy-list", "Fixed troop list",
                                   "The inherited per-troop composition.",
                                   "Trains a fixed list of troops the way the older bot did. Kept because it does not "
                                   "depend on recipe recognition, but it ignores anything the game has changed since.",
                                   "gated", [], ["Troop training screen recognition"],
                                   disabled_reason="Training screen recognition has not been re-confirmed."),
                        ],
                    },
                    {
                        "id": "army.recipe_name",
                        "type": "instance-select",
                        "label": "Recipe name",
                        "summary": "Which saved recipe to train.",
                        "description": (
                            "The exact recipe name as it appears in game. Left blank, the run uses whichever recipe "
                            "is already selected rather than switching."
                        ),
                        "default": "",
                        "required": False,
                        "engine_binding": "RunPlan.army_recipe_name",
                        "validation": {"max_length": 64},
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
                        "default": True,
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
                                   "gated", ["village.town-hall-18"], ["Search screen Town Hall recognition"],
                                   disabled_reason="Town Hall recognition on the search screen has not been captured."),
                            option("same-or-lower", "Same or lower",
                                   "Bases at or below your Town Hall level.",
                                   "A looser version of the above, trading some safety for a shorter search.",
                                   "gated", ["village.town-hall-18"], ["Search screen Town Hall recognition"],
                                   disabled_reason="Town Hall recognition on the search screen has not been captured."),
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
                                   "gated", ["chat.global-chat"], ["Clan chat recognition"],
                                   disabled_reason="Clan chat recognition has not been captured since Global Chat."),
                            option("anything", "Donate anything",
                                   "Fill any request with whatever is available.",
                                   "Donates without matching the request. Fast, and reliably annoys clan mates who "
                                   "asked for something specific.",
                                   "gated", ["chat.global-chat"], ["Clan chat recognition"],
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
                        "unit": "donations",
                        "validation": {"minimum": 0, "maximum": 500, "step": 5},
                    },
                    {
                        "id": "donate.request_when_short",
                        "type": "boolean",
                        "label": "Request when empty",
                        "summary": "Ask the clan for Clan Castle troops.",
                        "description": "Posts a request when the Clan Castle is empty, so a defending or attacking castle troop is available.",
                        "default": False,
                        "required": False,
                        "engine_binding": "RunPlan.donate_request_when_short",
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
                                   "gated", ["village.town-hall-18"], ["Laboratory screen recognition"],
                                   disabled_reason="Laboratory recognition has not been captured for the current client."),
                            option("priority-list", "Follow a priority list",
                                   "Work down a configured order.",
                                   "Researches in the order you specify, skipping anything unaffordable. Needs both "
                                   "lab recognition and a stored priority list.",
                                   "planned", ["village.town-hall-18"], ["Laboratory screen recognition"],
                                   disabled_reason="Priority lists are not implemented yet."),
                        ],
                    },
                    {
                        "id": "events.collect_resources",
                        "type": "boolean",
                        "label": "Collect collectors",
                        "summary": "Empty mines and collectors each pass.",
                        "description": (
                            "Tapping collectors is low risk and adds up. It is skipped automatically when storages "
                            "are already full, so it costs nothing to leave on."
                        ),
                        "default": True,
                        "required": False,
                        "engine_binding": "RunPlan.events_collect_resources",
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
                                   "gated", [], ["Telegram token configured in bot settings"],
                                   disabled_reason="Inherited integration, not re-tested."),
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
                        "type": "instance-select",
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

    OUT.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    total = sum(len(section["settings"]) for section in settings["sections"])
    print(f"Wrote {OUT.relative_to(ROOT)} with {len(settings['sections'])} sections and {total} settings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
