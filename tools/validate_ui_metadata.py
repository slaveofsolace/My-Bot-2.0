#!/usr/bin/env python3
"""Validate engine-facing UI metadata, capability gates, defaults, and descriptive completeness."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = ROOT / "config/ui/run-planner.settings.json"
SETTINGS_SCHEMA_PATH = ROOT / "config/ui/settings.schema.json"
CAPABILITIES_PATH = ROOT / "config/current-client-capabilities.json"
SURFACES_PATH = ROOT / "config/game/battle-surfaces.json"
HEROES_PATH = ROOT / "config/game/heroes.json"
CURRENT_CLIENT_PATH = ROOT / "config/game/current-client.json"
ATTACK_SCRIPTS_PATH = ROOT / "CSV/Attack"
HIDDEN_SCRIPT_TOKENS = ("human-like",)
HERO_DROP_NAMES = {
    "barbarian-king": "King",
    "archer-queen": "Queen",
    "grand-warden": "Warden",
    "royal-champion": "Champion",
}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
BINDING_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
ALLOWED_TYPES = {"select", "multi-select", "instance-select", "text", "integer", "boolean", "profile-queue"}
ALLOWED_AVAILABILITY = {"available", "gated", "planned", "unsupported"}
# The planner describes timings in terms of what they are for - letting a screen finish drawing, not
# driving the emulator faster than it answers. Wording that reframes them as disguise gets caught here,
# because a control's description is what a user believes about it.
#
# These are patterns rather than fixed phrases: a literal list only catches the exact wording someone
# happened to try, and "looks human" would slip past an entry for "look human".
PROHIBITED_CLAIMS = {
    "undetectable": r"undetect\w*",
    "ban-proof": r"\bban[\s-]?proof\b|\banti[\s-]?ban\b|\bunbannable\b",
    "defeating detection": r"\b(bypass|evad\w+|avoid\w*|escap\w+|beat|defeat|dodg\w+|fool\w*|trick\w*|circumvent\w*)\b[^.]{0,30}?\b(detect\w+|anti[\s-]?cheat|ban|bans|flagg?\w*)\b",
    "human-like": r"human[\s-]?like",
    "passing as a person": r"\b(look|appear|seem|pass|behav\w+|act|read)\w*\b[^.]{0,20}?\b(human|like a (real )?(person|player))\b",
    "mimicking a person": r"\bmimic\w*\b[^.]{0,20}?\b(human|person|player)\b",
    "stealth": r"\bstealth\w*\b",
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_schema_alignment(settings: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Keep the generated metadata shape and its published JSON Schema in lockstep."""
    errors: list[str] = []
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        return ["settings schema is missing $defs"]

    def definition(name: str) -> dict[str, Any]:
        value = definitions.get(name)
        if not isinstance(value, dict):
            errors.append(f"settings schema is missing the {name!r} definition")
            return {}
        return value

    section_schema = definition("section")
    setting_schema = definition("setting")
    option_schema = definition("option")
    validation_schema = definition("validation")
    preset_collection_schema = definition("preset_collection")
    preset_schema = definition("preset")

    def declared_properties(label: str, contract: dict[str, Any]) -> set[str]:
        properties = contract.get("properties")
        if not isinstance(properties, dict):
            errors.append(f"settings schema {label} has no properties map")
            return set()
        if contract.get("additionalProperties") is not False:
            errors.append(f"settings schema {label} must reject undeclared properties")
        return set(properties)

    root_properties = declared_properties("root", schema)
    section_properties = declared_properties("section", section_schema)
    setting_properties = declared_properties("setting", setting_schema)
    option_properties = declared_properties("option", option_schema)
    validation_properties = declared_properties("validation", validation_schema)
    preset_collection_properties = declared_properties("preset_collection", preset_collection_schema)
    preset_properties = declared_properties("preset", preset_schema)

    def reject_undeclared(label: str, value: Any, declared: set[str]) -> None:
        if not isinstance(value, dict):
            return
        unknown = sorted(set(value) - declared)
        if unknown:
            errors.append(f"settings schema does not declare {label} fields: {', '.join(unknown)}")

    reject_undeclared("root", settings, root_properties)
    presets = settings.get("presets")
    reject_undeclared("presets", presets, preset_collection_properties)
    if isinstance(presets, dict):
        for preset_index, preset in enumerate(presets.get("items", [])):
            reject_undeclared(f"presets.items[{preset_index}]", preset, preset_properties)
    for section_index, section in enumerate(settings.get("sections", [])):
        reject_undeclared(f"section[{section_index}]", section, section_properties)
        if not isinstance(section, dict):
            continue
        for setting_index, setting in enumerate(section.get("settings", [])):
            reject_undeclared(
                f"section[{section_index}].settings[{setting_index}]", setting, setting_properties
            )
            if not isinstance(setting, dict):
                continue
            reject_undeclared(
                f"section[{section_index}].settings[{setting_index}].validation",
                setting.get("validation"),
                validation_properties,
            )
            for option_index, option in enumerate(setting.get("options", [])):
                reject_undeclared(
                    f"section[{section_index}].settings[{setting_index}].options[{option_index}]",
                    option,
                    option_properties,
                )

    setting_contracts = setting_schema.get("properties", {})
    type_contract = setting_contracts.get("type", {}) if isinstance(setting_contracts, dict) else {}
    schema_types = type_contract.get("enum") if isinstance(type_contract, dict) else None
    if not isinstance(schema_types, list) or set(schema_types) != ALLOWED_TYPES:
        errors.append("settings schema type enum does not match the metadata validator")

    id_contract = setting_contracts.get("id", {}) if isinstance(setting_contracts, dict) else {}
    if not isinstance(id_contract, dict) or id_contract.get("pattern") != ID_PATTERN.pattern:
        errors.append("settings schema id pattern does not match the metadata validator")
    binding_contract = setting_contracts.get("engine_binding", {}) if isinstance(setting_contracts, dict) else {}
    if not isinstance(binding_contract, dict) or binding_contract.get("pattern") != BINDING_PATTERN.pattern:
        errors.append("settings schema engine_binding pattern does not match the metadata validator")

    section_contracts = section_schema.get("properties", {})
    tab_contract = section_contracts.get("tab_label", {}) if isinstance(section_contracts, dict) else {}
    if (
        not isinstance(tab_contract, dict)
        or tab_contract.get("type") != "string"
        or tab_contract.get("minLength") != 2
        or tab_contract.get("maxLength") != 10
        or "tab_label" not in section_schema.get("required", [])
    ):
        errors.append("settings schema tab_label contract must require a 2-10 character string")

    max_selected = setting_contracts.get("max_selected", {}) if isinstance(setting_contracts, dict) else {}
    if (
        not isinstance(max_selected, dict)
        or max_selected.get("type") != "integer"
        or max_selected.get("minimum") != 1
    ):
        errors.append("settings schema max_selected contract must be a positive integer")

    multi_select_branches = []
    for branch in setting_schema.get("allOf", []):
        if not isinstance(branch, dict):
            continue
        branch_type = (
            branch.get("if", {})
            .get("properties", {})
            .get("type", {})
            .get("const")
        )
        if branch_type == "multi-select":
            multi_select_branches.append(branch)
    if len(multi_select_branches) != 1:
        errors.append("settings schema must define exactly one multi-select conditional contract")
    else:
        branch = multi_select_branches[0]
        required = set(branch.get("then", {}).get("required", []))
        forbidden_elsewhere = set(branch.get("else", {}).get("not", {}).get("required", []))
        default_options = (
            branch.get("then", {})
            .get("properties", {})
            .get("default", {})
            .get("oneOf", [])
        )
        default_types = {
            item.get("type") for item in default_options if isinstance(item, dict)
        }
        if not {"options", "max_selected"}.issubset(required):
            errors.append("settings schema multi-select contract must require options and max_selected")
        if "max_selected" not in forbidden_elsewhere:
            errors.append("settings schema must forbid max_selected on non-multi-select settings")
        if default_types != {"string", "array"}:
            errors.append("settings schema multi-select default must accept the generated scalar or a list")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    settings = load(SETTINGS_PATH)
    settings_schema = load(SETTINGS_SCHEMA_PATH)
    errors.extend(validate_schema_alignment(settings, settings_schema))
    capabilities = load(CAPABILITIES_PATH)
    capability_ids = {item["id"] for item in capabilities.get("capabilities", [])}

    serialized = json.dumps(settings, ensure_ascii=False).lower()
    for label, pattern in sorted(PROHIBITED_CLAIMS.items()):
        found = re.search(pattern, serialized)
        if found:
            errors.append(f"prohibited product claim appears in UI metadata ({label}): {found.group(0)!r}")

    if settings.get("schema_version") != 1:
        errors.append("settings schema_version must be 1")
    if settings.get("surface") != "run-planner":
        errors.append("surface must be run-planner")
    if len(str(settings.get("description", "")).strip()) < 20:
        errors.append("surface description is missing or too short")

    sections = settings.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections must be a non-empty list")
        sections = []

    seen_sections: set[str] = set()
    seen_orders: set[int] = set()
    seen_settings: set[str] = set()
    tab_labels: list[str] = []
    bindings: dict[str, str] = {}
    select_values: dict[str, set[str]] = {}
    settings_by_id: dict[str, dict[str, Any]] = {}

    for section_index, section in enumerate(sections):
        section_id = section.get("id", "")
        if not isinstance(section_id, str) or not re.fullmatch(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", section_id):
            errors.append(f"section[{section_index}] has invalid id")
        elif section_id in seen_sections:
            errors.append(f"duplicate section id: {section_id}")
        seen_sections.add(section_id)

        order = section.get("order")
        if not isinstance(order, int) or order < 0:
            errors.append(f"{section_id}: order must be a non-negative integer")
        elif order in seen_orders:
            errors.append(f"duplicate section order: {order}")
        seen_orders.add(order)

        if len(str(section.get("description", "")).strip()) < 20:
            errors.append(f"{section_id}: section description is missing or too short")

        # The tab strip is horizontal inside a 452px window, so captions have a hard budget.
        tab_label = section.get("tab_label", "")
        if not isinstance(tab_label, str) or not 2 <= len(tab_label.strip()) <= 10:
            errors.append(f"{section_id}: tab_label must be 2-10 characters")
        tab_labels.append(tab_label)

        section_settings = section.get("settings")
        if not isinstance(section_settings, list) or not section_settings:
            errors.append(f"{section_id}: settings must be a non-empty list")
            continue

        for setting_index, setting in enumerate(section_settings):
            setting_id = setting.get("id", "")
            prefix = f"{section_id}.settings[{setting_index}]"
            if not isinstance(setting_id, str) or not ID_PATTERN.fullmatch(setting_id):
                errors.append(f"{prefix}: invalid setting id {setting_id!r}")
                continue
            if setting_id in seen_settings:
                errors.append(f"duplicate setting id: {setting_id}")
            seen_settings.add(setting_id)
            settings_by_id[setting_id] = setting

            has_fixed_value = "native_fixed_value" in setting
            has_fixed_reason = bool(str(setting.get("native_fixed_reason", "")).strip())
            if has_fixed_value != has_fixed_reason:
                errors.append(f"{setting_id}: native_fixed_value and native_fixed_reason must be declared together")
            if has_fixed_value and setting.get("native_fixed_value") != setting.get("default"):
                errors.append(f"{setting_id}: native fixed value must equal the visible default")

            setting_type = setting.get("type")
            if setting_type not in ALLOWED_TYPES:
                errors.append(f"{setting_id}: unsupported type {setting_type!r}")
            for field, minimum in (("label", 2), ("summary", 10), ("description", 30)):
                if len(str(setting.get(field, "")).strip()) < minimum:
                    errors.append(f"{setting_id}: {field} is missing or too short")
            if not isinstance(setting.get("required"), bool):
                errors.append(f"{setting_id}: required must be boolean")

            binding = setting.get("engine_binding", "")
            if not isinstance(binding, str) or not BINDING_PATTERN.fullmatch(binding):
                errors.append(f"{setting_id}: invalid engine_binding")
            elif binding in bindings and bindings[binding] != setting_id:
                errors.append(f"engine binding {binding} is assigned to multiple settings")
            else:
                bindings[binding] = setting_id

            setting_availability = setting.get("availability")
            if setting_availability is not None:
                setting_prefix = f"{setting_id}.evidence"
                if setting_availability not in ALLOWED_AVAILABILITY:
                    errors.append(f"{setting_prefix}: unsupported availability {setting_availability!r}")
                disabled_reason = str(setting.get("disabled_reason", "")).strip()
                if setting_availability == "available" and disabled_reason:
                    errors.append(f"{setting_prefix}: available setting cannot have a disabled reason")
                if setting_availability != "available" and not disabled_reason:
                    errors.append(f"{setting_prefix}: unavailable setting requires a disabled reason")
                if not isinstance(setting.get("runtime_verified"), bool):
                    errors.append(f"{setting_prefix}: runtime_verified must be an explicit boolean")

                referenced = setting.get("capability_ids")
                if not isinstance(referenced, list):
                    errors.append(f"{setting_prefix}: capability_ids must be a list")
                    referenced = []
                for capability_id in referenced:
                    if capability_id not in capability_ids:
                        errors.append(f"{setting_prefix}: unknown capability id {capability_id}")

                prerequisites = setting.get("prerequisites")
                if not isinstance(prerequisites, list) or not all(
                    isinstance(item, str) and item.strip() for item in prerequisites
                ):
                    errors.append(f"{setting_prefix}: prerequisites must be a list of non-empty strings")
                if not isinstance(setting.get("warning"), str):
                    errors.append(f"{setting_prefix}: warning must be a string")

            if setting_type == "integer":
                validation = setting.get("validation")
                if not isinstance(validation, dict):
                    errors.append(f"{setting_id}: integer setting requires validation")
                else:
                    minimum = validation.get("minimum")
                    maximum = validation.get("maximum")
                    step = validation.get("step")
                    if not isinstance(minimum, int) or not isinstance(maximum, int) or minimum > maximum:
                        errors.append(f"{setting_id}: invalid minimum or maximum")
                    if not isinstance(step, int) or step < 1:
                        errors.append(f"{setting_id}: step must be a positive integer")
                    default = setting.get("default")
                    if not isinstance(default, int) or (isinstance(minimum, int) and default < minimum) or (isinstance(maximum, int) and default > maximum):
                        errors.append(f"{setting_id}: default is outside validation bounds")

            if setting_type == "boolean" and not isinstance(setting.get("default"), bool):
                errors.append(f"{setting_id}: boolean default must be boolean")

            if setting_type in {"instance-select", "text", "profile-queue"}:
                default = setting.get("default")
                if not isinstance(default, str):
                    errors.append(f"{setting_id}: text default must be a string")
                validation = setting.get("validation", {})
                if not isinstance(validation, dict):
                    errors.append(f"{setting_id}: validation must be an object")
                else:
                    maximum = validation.get("max_length")
                    if maximum is not None and (isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1):
                        errors.append(f"{setting_id}: max_length must be a positive integer")
                    elif isinstance(default, str) and isinstance(maximum, int) and len(default) > maximum:
                        errors.append(f"{setting_id}: default exceeds max_length")

            if setting_type in ("select", "multi-select"):
                options = setting.get("options")
                if not isinstance(options, list) or not options:
                    errors.append(f"{setting_id}: select setting requires options")
                    continue
                values: set[str] = set()
                recommended_count = 0
                for option_index, option in enumerate(options):
                    value = option.get("value", "")
                    option_prefix = f"{setting_id}.options[{option_index}]"
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f"{option_prefix}: value is missing")
                        continue
                    if value in values:
                        errors.append(f"{setting_id}: duplicate option value {value}")
                    values.add(value)
                    for field, minimum in (("label", 2), ("summary", 10), ("description", 30)):
                        if len(str(option.get(field, "")).strip()) < minimum:
                            errors.append(f"{option_prefix}: {field} is missing or too short")

                    availability = option.get("availability")
                    if availability not in ALLOWED_AVAILABILITY:
                        errors.append(f"{option_prefix}: unsupported availability {availability!r}")
                    disabled_reason = str(option.get("disabled_reason", "")).strip()
                    if availability == "available" and disabled_reason:
                        errors.append(f"{option_prefix}: available option cannot have a disabled reason")
                    if availability != "available" and not disabled_reason:
                        errors.append(f"{option_prefix}: unavailable option requires a disabled reason")
                    if not isinstance(option.get("runtime_verified"), bool):
                        errors.append(f"{option_prefix}: runtime_verified must be an explicit boolean")

                    referenced = option.get("capability_ids")
                    if not isinstance(referenced, list):
                        errors.append(f"{option_prefix}: capability_ids must be a list")
                        referenced = []
                    for capability_id in referenced:
                        if capability_id not in capability_ids:
                            errors.append(f"{option_prefix}: unknown capability id {capability_id}")

                    prerequisites = option.get("prerequisites")
                    if not isinstance(prerequisites, list) or not all(isinstance(item, str) and item.strip() for item in prerequisites):
                        errors.append(f"{option_prefix}: prerequisites must be a list of non-empty strings")
                    if option.get("recommended") is True:
                        recommended_count += 1
                    elif option.get("recommended") is not False:
                        errors.append(f"{option_prefix}: recommended must be boolean")
                    if not isinstance(option.get("warning"), str):
                        errors.append(f"{option_prefix}: warning must be a string")

                # A multi-select needs a ceiling, or the UI cannot tell the user when to stop picking
                # and the engine finds out for them by refusing the plan.
                if setting_type == "multi-select":
                    ceiling = setting.get("max_selected")
                    if not isinstance(ceiling, int) or isinstance(ceiling, bool) or not 1 <= ceiling <= len(values):
                        errors.append(
                            f"{setting_id}: max_selected must be an integer between 1 and {len(values)}"
                        )
                    raw_default = setting.get("default")
                    defaults = raw_default if isinstance(raw_default, list) else [raw_default]
                    if (
                        not defaults
                        or not set(defaults).issubset(values)
                        or (isinstance(ceiling, int) and not isinstance(ceiling, bool) and len(defaults) > ceiling)
                    ):
                        errors.append(f"{setting_id}: defaults do not match the selection contract")
                elif "max_selected" in setting:
                    errors.append(f"{setting_id}: max_selected only applies to a multi-select")

                select_values[setting_id] = values
                if setting_type != "multi-select" and setting.get("default") not in values:
                    errors.append(f"{setting_id}: default does not match an option")
                if recommended_count > 1:
                    errors.append(f"{setting_id}: no more than one option may be recommended")

    expected_settings = {
        "run.surface",
        "run.heroes",
        "run.diagnostic_mode",
        "run.strategy",
        "run.attack_script",
        "runtime.emulator",
        "runtime.instance",
        "run.duration_minutes",
        "run.max_battles",
        "run.stop_on_star_bonus",
        "run.max_failures",
        "target.gold",
        "target.elixir",
        "target.dark_elixir",
        "upgrade.policy",
        "account.queue",
        "army.recipe_name",
        "army.recipe_digest",
        "army.max_queue_units",
        "army.manage_training",
    }
    missing_settings = sorted(expected_settings - seen_settings)
    if missing_settings:
        errors.append("required planner settings missing: " + ", ".join(missing_settings))

    # The planner must offer exactly the surfaces and Heroes the catalogs define, so a catalog change cannot
    # silently leave the UI offering a surface the engine no longer knows about, or hiding one it does.
    catalog_surfaces = {item["id"] for item in load(SURFACES_PATH).get("surfaces", [])}
    if select_values.get("run.surface") != catalog_surfaces:
        errors.append(
            "run.surface must offer exactly the catalog battle surfaces: " + ", ".join(sorted(catalog_surfaces))
        )
    hero_catalog = load(HEROES_PATH).get("heroes", [])
    catalog_heroes = {item["id"] for item in hero_catalog}
    hero_unlocks = {item["id"]: item.get("unlock_town_hall") for item in hero_catalog}
    if select_values.get("run.heroes") != catalog_heroes:
        errors.append(
            "run.heroes must offer exactly the catalog Heroes: " + ", ".join(sorted(catalog_heroes))
        )
    required_emulators = {"auto", "bluestacks5", "memu", "nox", "ldplayer9", "mumu"}
    if not required_emulators.issubset(select_values.get("runtime.emulator", set())):
        errors.append("runtime.emulator is missing one or more supported adapter choices")
    if select_values.get("upgrade.policy") != {"disabled", "walls", "suggested", "all"}:
        errors.append("upgrade.policy options do not match the run-plan contract")

    expected_native_fixed = {
        "account.queue": "",
        "army.manage_training": False,
        "search.max_seconds": 0,
        "donate.keep_army": True,
        "donate.max_per_run": 0,
        "events.clan_games_point_cap": 0,
        "pacing.retry_attempts": 0,
    }
    actual_native_fixed = {
        setting_id: setting.get("native_fixed_value")
        for setting_id, setting in settings_by_id.items()
        if "native_fixed_value" in setting
    }
    if actual_native_fixed != expected_native_fixed:
        errors.append(f"native fixed-value controls drifted: {actual_native_fixed!r}")

    script_options = {"profile-current"} | {
        path.stem
        for path in ATTACK_SCRIPTS_PATH.glob("*.csv")
        if not any(token in path.stem.casefold() for token in HIDDEN_SCRIPT_TOKENS)
    }
    if select_values.get("run.attack_script") != script_options:
        errors.append("run.attack_script must offer profile-current and every bundled CSV attack script exactly")

    def option_map(setting_id: str) -> dict[str, dict]:
        return {item.get("value"): item for item in settings_by_id.get(setting_id, {}).get("options", [])}

    current_package = "current reviewed local package"
    surface_options = option_map("run.surface")
    regular_option = surface_options.get("regular", {})
    if regular_option.get("availability") != "gated" or regular_option.get("runtime_verified") is not False:
        errors.append("Regular Battles must remain diagnostic-only until the current binary and client are reviewed")
    regular_copy = " ".join(str(regular_option.get(field, "")).lower() for field in ("description", "disabled_reason"))
    if not all(term in regular_copy for term in (current_package, "exact-current no-input managed-engine", "bot-owned bluestacks", "managed start", "battle gameplay", "live human review")):
        errors.append("Regular Battles must distinguish current engine/self-launch proof from missing Start, battle, fixture, and human-review proof")
    for surface_id, surface_option in surface_options.items():
        if surface_id != "regular" and surface_option.get("availability") not in {"planned", "unsupported"}:
            errors.append(f"{surface_id}: a surface with no native adapter must not remain selectable")

    strategy_options = option_map("run.strategy")
    csv_option = strategy_options.get("legacy.csv", {})
    if csv_option.get("availability") != "gated" or csv_option.get("runtime_verified") is not False:
        errors.append("legacy.csv must remain supervised-only until exact-current battle evidence exists")
    standard_option = strategy_options.get("legacy.standard", {})
    if standard_option.get("availability") != "gated" or standard_option.get("runtime_verified") is not False:
        errors.append("legacy.standard must remain supervised-only until exact-current battle evidence exists")
    standard_copy = " ".join(str(standard_option.get(field, "")).lower() for field in ("description", "disabled_reason", "warning"))
    if not all(term in standard_copy for term in ("older-binary", "clean-room red-line detector", "supervised-only", "live battle evidence")):
        errors.append("legacy.standard must distinguish historical proof, clean-room red-line gating, and missing exact-current battle proof")
    smart_option = strategy_options.get("smart.local", {})
    if smart_option.get("availability") != "gated" or smart_option.get("runtime_verified") is not False:
        errors.append("smart.local must remain supervised-only until exact-current battle evidence exists")
    smart_copy = " ".join(
        str(smart_option.get(field, "")).lower()
        for field in ("description", "disabled_reason", "warning")
    )
    if not all(term in smart_copy for term in ("older-binary bounded supervised th17 run", "strategy quality", "clean-room red-line detector", "live battle evidence")):
        errors.append("smart.local must keep historical mechanics narrower than current exact-current battle or quality proof")
    for strategy_id in ("legacy.csv", "legacy.standard", "smart.local"):
        blocker_copy = str(strategy_options.get(strategy_id, {}).get("disabled_reason", "")).lower()
        description_copy = str(strategy_options.get(strategy_id, {}).get("description", "")).lower()
        if "supervised-only" not in blocker_copy or "exact-current live battle" not in blocker_copy:
            errors.append(f"{strategy_id}: battle blocker must name supervised-only exact-current live evidence")
        if not all(term in description_copy for term in ("clean-room red-line detector", "inherited imgloc exports remain disabled")):
            errors.append(f"{strategy_id}: battle description must keep the clean-room detector separate from inherited ImgLoc")
    for strategy_id in ("legacy.smart-farm", "builder.baby-dragon"):
        if strategy_options.get(strategy_id, {}).get("availability") not in {"planned", "unsupported"}:
            errors.append(f"{strategy_id}: strategy with no native adapter must not remain selectable")
    builder_collectors = strategy_options.get("builder.collectors", {})
    if builder_collectors.get("availability") != "gated":
        errors.append("builder.collectors must remain a gated supervised Builder Base collection route")
    if builder_collectors.get("runtime_verified") is not False:
        errors.append("builder.collectors must not claim live/runtime acceptance before an exact installed receipt")
    builder_copy = " ".join(
        str(builder_collectors.get(key, "")) for key in ("description", "details", "warning", "disabled_reason")
    ).lower()
    if not all(term in builder_copy for term in ("builder gold", "elixir", "gem mine", "excluded")):
        errors.append("builder.collectors copy must name ordinary Builder resources and the excluded Gem Mine")

    expected_option_capabilities = {
        ("run.surface", "builder"): {"builder-base.battles"},
        ("run.strategy", "army.exact-recipe"): {"army.training"},
        ("run.strategy", "builder.collectors"): {"builder-base.resources"},
        ("run.strategy", "builder.baby-dragon"): {"builder-base.battles"},
        ("run.strategy", "home.clan-request"): {"village.clan-request"},
        ("upgrade.policy", "walls"): {"village.upgrades-home", "village.town-hall-18"},
        ("upgrade.policy", "suggested"): {"village.upgrades-home"},
        ("upgrade.policy", "all"): {"village.upgrades-home", "village.laboratory", "village.town-hall-18", "heroes.six-slot-layout"},
        ("donate.mode", "matching"): {"village.donations", "chat.global-chat"},
        ("donate.mode", "anything"): {"village.donations", "chat.global-chat"},
        ("events.laboratory", "cheapest"): {"village.laboratory"},
        ("events.laboratory", "priority-list"): {"village.laboratory"},
    }
    for (setting_id, value), expected in expected_option_capabilities.items():
        actual = set(option_map(setting_id).get(value, {}).get("capability_ids", []))
        if actual != expected:
            errors.append(f"{setting_id}.{value}: capability mapping drifted: {sorted(actual)!r}")
    if set(settings_by_id.get("donate.request_when_short", {}).get("capability_ids", [])) != {"village.clan-request"}:
        errors.append("donate.request_when_short must use the request-only capability gate")

    for script_id, script_option in option_map("run.attack_script").items():
        if script_option.get("availability") != "gated" or script_option.get("runtime_verified") is not False:
            errors.append(f"{script_id}: attack script must not be labelled runtime verified without battle evidence")

    bluestacks_option = option_map("runtime.emulator").get("bluestacks5", {})
    if bluestacks_option.get("availability") != "gated" or bluestacks_option.get("runtime_verified") is not False:
        errors.append("BlueStacks 5 must remain diagnostic-only until the current binary attachment path is reviewed")
    bluestacks_copy = " ".join(
        str(bluestacks_option.get(field, "")).lower()
        for field in ("description", "disabled_reason", "warning")
    )
    if not all(term in bluestacks_copy for term in ("older binary", current_package, "repeated no-input managed-engine", "exact pie64", "adb", "returning-player interruption", "passive home", "managed start", "gameplay")):
        errors.append("BlueStacks 5 must distinguish exact current self-launch proof from missing managed Start and gameplay automation proof")

    presets = settings.get("presets")
    if not isinstance(presets, dict):
        errors.append("presets must be an object")
        presets = {}
    preserved = presets.get("preserved_settings")
    if not isinstance(preserved, list) or not all(isinstance(item, str) for item in preserved):
        errors.append("presets.preserved_settings must be a list of setting ids")
        preserved = []
    preserved_set = set(preserved)
    required_preserved = {"runtime.emulator", "runtime.instance", "run.diagnostic_mode", "run.diagnostic_note"}
    if preserved_set != required_preserved:
        errors.append("Town Hall presets must preserve emulator selection and diagnostic acknowledgement exactly")
    unknown_preserved = sorted(preserved_set - seen_settings)
    if unknown_preserved:
        errors.append("presets preserve unknown settings: " + ", ".join(unknown_preserved))

    preset_items = presets.get("items")
    if not isinstance(preset_items, list) or not preset_items:
        errors.append("presets.items must be a non-empty list")
        preset_items = []
    max_town_hall = load(CURRENT_CLIENT_PATH).get("max_town_hall")
    expected_town_halls = set(range(2, max_town_hall + 1)) if isinstance(max_town_hall, int) else set()
    seen_town_halls: set[int] = set()
    seen_preset_ids: set[str] = set()

    for preset_index, preset in enumerate(preset_items):
        prefix = f"presets.items[{preset_index}]"
        if not isinstance(preset, dict):
            errors.append(f"{prefix} must be an object")
            continue
        preset_id = preset.get("id")
        town_hall = preset.get("town_hall")
        if not isinstance(preset_id, str) or not re.fullmatch(r"th[0-9]+", preset_id):
            errors.append(f"{prefix}: invalid preset id")
        elif preset_id in seen_preset_ids:
            errors.append(f"duplicate preset id: {preset_id}")
        seen_preset_ids.add(preset_id)
        if not isinstance(town_hall, int) or isinstance(town_hall, bool):
            errors.append(f"{prefix}: town_hall must be an integer")
        elif town_hall in seen_town_halls:
            errors.append(f"duplicate Town Hall preset: {town_hall}")
        else:
            seen_town_halls.add(town_hall)
            if preset_id != f"th{town_hall}":
                errors.append(f"{prefix}: id does not match Town Hall {town_hall}")
        for field, minimum in (("label", 6), ("summary", 20), ("description", 40), ("source_note", 20)):
            if len(str(preset.get(field, "")).strip()) < minimum:
                errors.append(f"{prefix}: {field} is missing or too short")

        values = preset.get("values")
        if not isinstance(values, dict) or not values:
            errors.append(f"{prefix}: values must be a non-empty object")
            continue
        unknown_values = sorted(set(values) - seen_settings)
        if unknown_values:
            errors.append(f"{prefix}: unknown setting values: {', '.join(unknown_values)}")
        overwritten = sorted(set(values) & preserved_set)
        if overwritten:
            errors.append(f"{prefix}: preset must preserve: {', '.join(overwritten)}")
        missing_owned = sorted(seen_settings - preserved_set - set(values))
        if missing_owned:
            errors.append(f"{prefix}: preset silently preserves non-operator fields: {', '.join(missing_owned)}")
        if "run.heroes" not in values:
            errors.append(f"{prefix}: preset must explicitly select its complete Hero loadout")

        for setting_id, value in values.items():
            setting = settings_by_id.get(setting_id)
            if not setting:
                continue
            kind = setting.get("type")
            if kind == "boolean" and not isinstance(value, bool):
                errors.append(f"{prefix}: {setting_id} must be boolean")
            elif kind == "integer":
                rules = setting.get("validation", {})
                if (
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or value < rules.get("minimum", value)
                    or value > rules.get("maximum", value)
                ):
                    errors.append(f"{prefix}: {setting_id} is outside its integer contract")
            elif kind == "select" and value not in select_values.get(setting_id, set()):
                errors.append(f"{prefix}: {setting_id} does not name an option")
            elif kind == "multi-select":
                available = select_values.get(setting_id, set())
                ceiling = setting.get("max_selected", 0)
                if (
                    not isinstance(value, list)
                    or len(value) > ceiling
                    or len(value) != len(set(value))
                    or not set(value).issubset(available)
                ):
                    errors.append(f"{prefix}: {setting_id} violates its selection contract")
            elif kind in {"instance-select", "text", "profile-queue"} and not isinstance(value, str):
                errors.append(f"{prefix}: {setting_id} must be text")

        compatibility = preset.get("compatibility")
        strategy = values.get("run.strategy")
        attack_script = values.get("run.attack_script")
        script_text = ""
        if compatibility == "script-declared":
            if strategy != "legacy.csv" or attack_script == "profile-current":
                errors.append(f"{prefix}: script-declared preset must select an exact CSV strategy")
            else:
                script_path = ATTACK_SCRIPTS_PATH / f"{attack_script}.csv"
                if not script_path.is_file():
                    errors.append(f"{prefix}: selected attack script is not bundled")
                else:
                    script_text = script_path.read_text(encoding="utf-8-sig", errors="replace")
                    town_hall_token = re.compile(rf"(?<![A-Za-z0-9])TH0?{town_hall}(?!\d)", re.IGNORECASE)
                    if not town_hall_token.search(script_text):
                        errors.append(f"{prefix}: selected script does not declare Town Hall {town_hall}")
                    expected_source = f"CSV/Attack/{attack_script}.csv"
                    if expected_source not in str(preset.get("source_note", "")):
                        errors.append(f"{prefix}: source_note must name {expected_source}")
        elif compatibility == "engine-fallback":
            if strategy != "legacy.standard" or attack_script != "profile-current":
                errors.append(f"{prefix}: engine fallback must use Standard and preserve the profile script")
            town_hall_token = re.compile(rf"(?<![A-Za-z0-9])TH0?{town_hall}(?!\d)", re.IGNORECASE)
            declaring_scripts = [
                path.name
                for path in ATTACK_SCRIPTS_PATH.glob("*.csv")
                if town_hall_token.search(path.read_text(encoding="utf-8-sig", errors="replace"))
            ]
            if declaring_scripts:
                errors.append(
                    f"{prefix}: fallback source claim is stale; scripts now declare Town Hall {town_hall}: "
                    + ", ".join(sorted(declaring_scripts))
                )
        elif compatibility == "research-guided":
            if strategy != "smart.local" or attack_script != "profile-current":
                errors.append(f"{prefix}: research-guided preset must use Smart Attack with the current profile army")
            if f"smart-attack-strategies.json TH{town_hall} policy" not in str(preset.get("source_note", "")):
                errors.append(f"{prefix}: research-guided preset must cite its exact Town Hall policy")
        else:
            errors.append(f"{prefix}: unsupported compatibility classification {compatibility!r}")

        supported_values = {
            "run.surface": "regular",
            "army.source": "recipe",
            "army.recipe_name": "",
            "army.recipe_digest": "",
            "army.max_queue_units": 0,
            "search.max_seconds": 0,
            "search.town_hall_filter": "any",
            "pacing.retry_attempts": 0,
            "donate.keep_army": True,
            "donate.max_per_run": 0,
            "events.clan_games_point_cap": 0,
            "events.laboratory": "off",
            "account.queue": "",
            "notify.channel": "log-only",
        }
        for setting_id, expected in supported_values.items():
            if values.get(setting_id) != expected:
                errors.append(f"{prefix}: {setting_id} must stay at the wired value {expected!r}")
        if values.get("upgrade.policy") not in {"disabled", "walls"}:
            errors.append(f"{prefix}: upgrade.policy has no exact legacy adapter")
        preset_heroes = set(values.get("run.heroes", []))
        unsupported_preset_heroes = preset_heroes & {"dragon-duke"}
        if compatibility == "script-declared":
            unsupported_preset_heroes |= preset_heroes & {"minion-prince"}
        if unsupported_preset_heroes:
            errors.append(
                f"{prefix}: preset selects Heroes outside the source-proven CSV deployment set: "
                + ", ".join(sorted(unsupported_preset_heroes))
            )
        for hero_id in sorted(preset_heroes):
            unlock = hero_unlocks.get(hero_id)
            if not isinstance(unlock, int) or not isinstance(town_hall, int) or unlock > town_hall:
                errors.append(f"{prefix}: {hero_id} is not unlocked at Town Hall {town_hall}")
            drop_name = HERO_DROP_NAMES.get(hero_id)
            if compatibility == "script-declared" and (
                not drop_name
                or not re.search(
                    rf"^DROP\s*\|[^\r\n]*\|\s*{re.escape(drop_name)}\s*\|",
                    script_text,
                    re.IGNORECASE | re.MULTILINE,
                )
            ):
                errors.append(f"{prefix}: {hero_id} has no matching DROP action in the selected CSV")

    if seen_town_halls != expected_town_halls:
        missing = sorted(expected_town_halls - seen_town_halls)
        extra = sorted(seen_town_halls - expected_town_halls)
        errors.append(f"Town Hall presets do not cover TH2-TH{max_town_hall}: missing={missing}, extra={extra}")

    # Rough Win32 tab metrics: about 7px a character plus 12px of padding per tab. The strip is
    # multiline and the design reserves two caption rows, so the budget is two rows of 430px.
    # Anything beyond that would silently push the tab body down and clip the last row of controls.
    strip_width = sum(len(label) * 7 + 12 for label in tab_labels)
    if strip_width > 860:
        errors.append(
            f"tab captions need {strip_width}px but two caption rows hold 860px; shorten them or drop a section"
        )
    for label in tab_labels:
        if len(label) * 7 + 12 > 430:
            errors.append(f"tab caption too wide for one row: {label!r}")

    ordered = [section.get("order") for section in sections if isinstance(section.get("order"), int)]
    if ordered != sorted(ordered):
        warnings.append("sections are not stored in display order")

    report = {
        "schema_version": 1,
        "settings_file": str(SETTINGS_PATH.relative_to(ROOT)),
        "sections": len(sections),
        "settings": len(seen_settings),
        "engine_bindings": len(bindings),
        "presets": len(preset_items),
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
