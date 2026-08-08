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
CAPABILITIES_PATH = ROOT / "config/current-client-capabilities.json"
SURFACES_PATH = ROOT / "config/game/battle-surfaces.json"
HEROES_PATH = ROOT / "config/game/heroes.json"
ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[.\-_][a-z0-9]+)*$")
BINDING_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
ALLOWED_TYPES = {"select", "multi-select", "instance-select", "integer", "boolean", "profile-queue"}
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    settings = load(SETTINGS_PATH)
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
    catalog_heroes = {item["id"] for item in load(HEROES_PATH).get("heroes", [])}
    if select_values.get("run.heroes") != catalog_heroes:
        errors.append(
            "run.heroes must offer exactly the catalog Heroes: " + ", ".join(sorted(catalog_heroes))
        )
    required_emulators = {"auto", "bluestacks5", "memu", "nox", "ldplayer9", "mumu"}
    if not required_emulators.issubset(select_values.get("runtime.emulator", set())):
        errors.append("runtime.emulator is missing one or more supported adapter choices")
    if select_values.get("upgrade.policy") != {"disabled", "walls", "suggested", "all"}:
        errors.append("upgrade.policy options do not match the run-plan contract")

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
