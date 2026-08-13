#!/usr/bin/env python3
"""Check complete Town Hall presets, automatic form loading, and the explicit save boundary."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config/ui/run-planner.presets.json"
METADATA = ROOT / "config/ui/run-planner.settings.json"
CURRENT_CLIENT = ROOT / "config/game/current-client.json"
HEROES = ROOT / "config/game/heroes.json"
SCRIPTS = ROOT / "CSV/Attack"
HERO_DROP_NAMES = {
    "barbarian-king": "King",
    "archer-queen": "Queen",
    "grand-warden": "Warden",
    "royal-champion": "Champion",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def function_body(source: str, declaration: str, next_declaration: str) -> str:
    start = source.find(declaration)
    end = source.find(next_declaration, start + len(declaration))
    return "" if start < 0 or end < 0 else source[start:end]


def main() -> int:
    errors: list[str] = []
    source = load(SOURCE)
    metadata = load(METADATA)
    current = load(CURRENT_CLIENT)
    hero_unlocks = {item["id"]: item["unlock_town_hall"] for item in load(HEROES).get("heroes", [])}
    presets = metadata.get("presets", {}).get("items", [])
    source_presets = source.get("presets", [])
    max_town_hall = current.get("max_town_hall")

    expected = list(range(2, max_town_hall + 1))
    if [item.get("town_hall") for item in presets] != expected:
        errors.append(f"generated presets must cover TH2-TH{max_town_hall} once and in order")
    if [item.get("id") for item in presets] != [item.get("id") for item in source_presets]:
        errors.append("generated preset order or identity drifted from run-planner.presets.json")

    preserved = set(metadata.get("presets", {}).get("preserved_settings", []))
    safety_owned = {"runtime.emulator", "runtime.instance", "run.diagnostic_mode", "run.diagnostic_note"}
    if preserved != safety_owned:
        errors.append("presets must preserve emulator selection and diagnostic acknowledgement")

    sys.path.insert(0, str(ROOT / "tools"))
    import planner_ui  # noqa: E402

    defaults = planner_ui.default_plan()
    all_setting_ids = set(defaults)
    for preset in presets:
        prefix = preset.get("id", "unknown")
        values = preset.get("values", {})
        if set(values) & preserved:
            errors.append(f"{prefix} overwrites a preserved operator setting")
        candidate = dict(defaults)
        candidate.update(values)
        clean, adjustments, rejected = planner_ui.validate_plan(candidate)
        if adjustments or rejected or clean != candidate:
            errors.append(f"{prefix} is not normalized by the real planner validator")

        preset_owned = set(values)
        missing_owned = sorted(all_setting_ids - preserved - preset_owned)
        if missing_owned:
            errors.append(f"{prefix} is a partial preset and leaves fields unchanged: {', '.join(missing_owned)}")
        if "run.heroes" not in values:
            errors.append(f"{prefix} must explicitly select its complete Hero loadout")
        if values.get("run.town_hall") != preset.get("town_hall"):
            errors.append(f"{prefix} must own and persist its exact Town Hall identity")
        selected_heroes = values.get("run.heroes", [])
        if not isinstance(selected_heroes, list):
            errors.append(f"{prefix} run.heroes must be a list")
            selected_heroes = []
        if len(selected_heroes) != len(set(selected_heroes)) or len(selected_heroes) > 4:
            errors.append(f"{prefix} Hero loadout must be unique and fit the four active slots")

        compatibility = preset.get("compatibility")
        script = values.get("run.attack_script")
        strategy = values.get("run.strategy")
        script_text = ""
        if compatibility == "script-declared":
            if strategy != "legacy.csv" or not isinstance(script, str) or script == "profile-current":
                errors.append(f"{prefix} does not select an exact scripted deployment")
            else:
                script_path = SCRIPTS / f"{script}.csv"
                if not script_path.is_file():
                    errors.append(f"{prefix} selects a CSV file that is not bundled")
                else:
                    script_text = script_path.read_text(encoding="utf-8-sig", errors="replace")
                    if not re.search(
                        rf"(?<![A-Za-z0-9])TH0?{preset.get('town_hall')}(?!\d)",
                        script_text,
                        re.IGNORECASE,
                    ):
                        errors.append(f"{prefix} script does not declare its Town Hall")
                    if f"CSV/Attack/{script}.csv" not in str(preset.get("source_note", "")):
                        errors.append(f"{prefix} source note does not name the selected script")
        elif compatibility == "engine-fallback":
            if strategy != "legacy.standard" or script != "profile-current":
                errors.append(f"{prefix} fallback must use Standard without replacing the profile script")
            town_hall_token = re.compile(
                rf"(?<![A-Za-z0-9])TH0?{preset.get('town_hall')}(?!\d)", re.IGNORECASE
            )
            declaring_scripts = [
                path.name
                for path in SCRIPTS.glob("*.csv")
                if town_hall_token.search(path.read_text(encoding="utf-8-sig", errors="replace"))
            ]
            if declaring_scripts:
                errors.append(f"{prefix} fallback is stale because a bundled script now declares this Town Hall")
        elif compatibility == "research-guided":
            if strategy != "smart.local" or script != "profile-current":
                errors.append(f"{prefix} research-guided preset must use Smart Attack and the current profile army")
            if f"smart-attack-strategies.json TH{preset.get('town_hall')} policy" not in str(preset.get("source_note", "")):
                errors.append(f"{prefix} does not cite its exact Smart Attack policy")
        else:
            errors.append(f"{prefix} has no compatibility classification")
        unsupported_preset_heroes = set(selected_heroes) & {"dragon-duke"}
        if compatibility == "script-declared":
            unsupported_preset_heroes |= set(selected_heroes) & {"minion-prince"}
        if unsupported_preset_heroes:
            errors.append(
                f"{prefix} selects a Hero outside the source-proven CSV deployment set: "
                + ", ".join(sorted(unsupported_preset_heroes))
            )
        for hero_id in selected_heroes:
            unlock = hero_unlocks.get(hero_id)
            if not isinstance(unlock, int) or unlock > preset.get("town_hall", 0):
                errors.append(f"{prefix} selects {hero_id} before its catalog unlock")
            drop_name = HERO_DROP_NAMES.get(hero_id)
            if compatibility == "script-declared" and (
                not drop_name
                or not re.search(
                    rf"^DROP\s*\|[^\r\n]*\|\s*{re.escape(drop_name)}\s*\|",
                    script_text,
                    re.IGNORECASE | re.MULTILINE,
                )
            ):
                errors.append(f"{prefix} selects {hero_id} without a matching CSV DROP action")

    script_setting = next(
        (setting for section in metadata.get("sections", []) for setting in section.get("settings", [])
         if setting.get("id") == "run.attack_script"),
        None,
    )
    if not script_setting or script_setting.get("default") != "profile-current":
        errors.append("run.attack_script must default to preserving the profile selection")

    planner_js = (ROOT / "ui/planner.js").read_text(encoding="utf-8-sig")
    apply_body = function_body(planner_js, "function applySelectedPreset()", "function matches(setting)")
    if "let SELECTED_PRESET = 'custom';" not in planner_js:
        errors.append("the preset selector no longer boots in Custom")
    initialize_body = function_body(planner_js, "function initializePresets()", "function markPresetCustom(")
    if "applySelectedPreset();" not in initialize_body:
        errors.append("choosing a Town Hall must immediately load the complete preset into the visible plan")
    planner_html = (ROOT / "ui/planner.html").read_text(encoding="utf-8-sig")
    planner_css = (ROOT / "ui/planner.css").read_text(encoding="utf-8-sig")
    if 'id="applyPreset"' in planner_html:
        errors.append("the obsolete second Apply preset click must not remain in the interface")
    if 'class="preset-workbench" aria-label="Plan starting points"' not in planner_html:
        errors.append("the preset region and Town Hall select must not share the same accessible name")
    if "@media (max-width: 360px)" not in planner_css or "min-width: 280px" not in planner_css:
        errors.append("short desktop viewports must reserve a usable planner workspace")
    for required in (
        "if (option.runtime_verified)",
        "['planned', 'unsupported'].includes(item.availability)",
        "Planned and implemented",
        "Object.prototype.hasOwnProperty.call(setting, 'native_fixed_value')",
        "function selectedHeroLabels(plan = PLAN)",
        "function matchingPresetForPlan(plan = PLAN)",
        "Selected Heroes deploy only when their attack-bar slots are present.",
        "No Heroes are selected for deployment.",
    ):
        if required not in planner_js:
            errors.append(f"the planner lost an honest option-state invariant: {required}")
    if "{ available: 'verified'" in planner_js:
        errors.append("availability must not be mislabeled as runtime verification")
    update_dirty_body = function_body(planner_js, "function updateDirty()", "function readableState(state)")
    if "renderControl();" not in update_dirty_body:
        errors.append("unsaved preset or field changes must disable Start immediately, not on the next heartbeat")
    for required in ("function presetChanges(preset)", "function buildPresetDiff(changes)", "document.createElement('details')", "change.before", "change.after",
                     "function renderPresetPreview(loadedChanges = null)", "Review ${changes.length} loaded change"):
        if required not in planner_js:
            errors.append(f"preset preview is missing an inspectable old-to-new diff invariant: {required}")
    if not apply_body:
        errors.append("Apply preset implementation could not be inspected")
    else:
        for forbidden in ("fetch(", "savePlan(", "sendControl("):
            if forbidden in apply_body:
                errors.append(f"Apply preset must not call {forbidden[:-1]}")
        if "PLAN[id] = clone(value);" not in apply_body:
            errors.append("Apply preset no longer loads values into the visible plan")
        if "renderPresetPreview(changes);" not in apply_body or "addPresetFacts(preview, preset.values || PLAN);" not in planner_js:
            errors.append("preset loading no longer confirms the Hero loadout it selected")
        if "is visible but not applied" not in apply_body.lower():
            errors.append("preset loading no longer tells the operator the plan is still unsaved")

    send_body = function_body(planner_js, "async function sendControl(action)", "function eventDate(event)")
    if not send_body:
        errors.append("Start command implementation could not be inspected")
    else:
        if "savePlan()" in send_body:
            errors.append("Start must not silently save an unapplied preset or draft")
        for required in ("allSettings().some(isUnsaved)", "!PLAN_WRITTEN", "Apply the visible plan before Start"):
            if required not in send_body:
                errors.append(f"Start lost its explicit Apply-plan gate: {required}")

    run_plan_file = (ROOT / "COCBot/functions/Run/RunPlanFile.au3").read_text(encoding="utf-8-sig")
    if '"run.attack_script"' not in run_plan_file or "profile-current" not in run_plan_file:
        errors.append("the native plan reader does not carry or migrate the exact attack script")
    execution = (ROOT / "COCBot/functions/Run/RunExecution.au3").read_text(encoding="utf-8-sig")
    for required in ("FileExists($sAttackScriptPath)", "$g_sAttackScrScriptName[$iMode] = $sAttackScript", "_RunExecutionRestoreProfile"):
        if required not in execution:
            errors.append(f"one-run script override is missing engine invariant: {required}")
    for required in (
        'HeroLoadoutContains($oLoadout, "barbarian-king")',
        'HeroLoadoutContains($oLoadout, "archer-queen")',
        'HeroLoadoutContains($oLoadout, "minion-prince")',
        'HeroLoadoutContains($oLoadout, "grand-warden")',
        'HeroLoadoutContains($oLoadout, "royal-champion")',
        "$g_aiAttackUseHeroes[$iMode] = $iHeroMask",
    ):
        if required not in execution:
            errors.append(f"selected preset Heroes are not carried into the attack engine: {required}")
    save_config = (ROOT / "COCBot/functions/Config/saveConfig.au3").read_text(encoding="utf-8-sig")
    save_body = function_body(save_config, "Func saveConfig()", "Func SaveProfileConfig")
    guard_at = save_body.find("If RunProfileRegularConfigSerializationAllowed() Then")
    regular_write_at = save_body.find("SaveRegularConfig()")
    if guard_at < 0 or regular_write_at < guard_at:
        errors.append("SaveConfig must guard regular profile serialization during one-run overrides")

    if errors:
        print("Town Hall preset checks failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"Town Hall preset checks passed: {len(presets)} complete presets, TH2-TH{max_town_hall}, selection loads and Apply plan saves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
