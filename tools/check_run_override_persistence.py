#!/usr/bin/env python3
"""Static regression for one-run planner override apply/save/restore invariants."""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
EXECUTION = ROOT / "COCBot/functions/Run/RunExecution.au3"
WRITE_GUARD = ROOT / "COCBot/functions/Run/RunProfileWriteGuard.au3"
SAVE_CONFIG = ROOT / "COCBot/functions/Config/saveConfig.au3"
GUI_ACTION = ROOT / "COCBot/MBR GUI Action.au3"
GUI_CONTROL = ROOT / "COCBot/MBR GUI Control.au3"
AUTOIT_TEST = ROOT / "tests/autoit/RunEngineTest.au3"


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^Func\s+{re.escape(name)}\b.*?^EndFunc(?:\s*;[^\r\n]*)?",
        source,
    )
    return match.group(0) if match else ""


def main() -> int:
    execution = EXECUTION.read_text(encoding="utf-8-sig")
    guard = WRITE_GUARD.read_text(encoding="utf-8-sig")
    save = SAVE_CONFIG.read_text(encoding="utf-8-sig")
    action = GUI_ACTION.read_text(encoding="utf-8-sig")
    control = GUI_CONTROL.read_text(encoding="utf-8-sig")
    autoit_test = AUTOIT_TEST.read_text(encoding="utf-8-sig")
    errors: list[str] = []

    capture = function_body(execution, "_RunExecutionCaptureProfileSnapshot")
    restore = function_body(execution, "_RunExecutionRestoreProfile")
    apply_intent = function_body(execution, "_RunExecutionApplyIntent")
    apply_prepared = function_body(execution, "RunExecutionApplyPrepared")
    save_config = function_body(save, "saveConfig")
    save_building = function_body(save, "SaveBuildingConfig")
    save_clan_games = function_body(save, "SaveClanGamesConfig")
    save_switch_accounts = function_body(save, "SaveConfig_600_35_2")
    bot_stop = function_body(action, "BotStop")
    gui_mode_toggle = function_body(control, "BotGuiModeToggle")

    pairs = (
        ("$g_iAndroidConfig", "$g_iRunExecutionSnapshotAndroidConfig"),
        ("$g_sAndroidEmulator", "$g_sRunExecutionSnapshotAndroidEmulator"),
        ("$g_sAndroidInstance", "$g_sRunExecutionSnapshotAndroidInstance"),
        ("$g_sAttackScrScriptName[$iMode]", "$g_asRunExecutionSnapshotAttackScript[$iMode]"),
        ("$g_abAttackTypeEnable[$iMode]", "$g_abRunExecutionSnapshotAttackTypeEnable[$iMode]"),
        ("$g_aiAttackAlgorithm[$iMode]", "$g_aiRunExecutionSnapshotAttackAlgorithm[$iMode]"),
        ("$g_aiAttackUseHeroes[$iMode]", "$g_aiRunExecutionSnapshotAttackUseHeroes[$iMode]"),
        ("$g_abAttackDropCC[$iMode]", "$g_abRunExecutionSnapshotAttackDropCC[$iMode]"),
        ("$g_aiSearchHeroWaitEnable[$iMode]", "$g_aiRunExecutionSnapshotSearchHeroWaitEnable[$iMode]"),
        ("$g_abSearchSpellsWaitEnable[$iMode]", "$g_abRunExecutionSnapshotSearchSpellsWaitEnable[$iMode]"),
        ("$g_abSearchSiegeWaitEnable[$iMode]", "$g_abRunExecutionSnapshotSearchSiegeWaitEnable[$iMode]"),
        ("$g_aiFilterMeetGE[$iMode]", "$g_aiRunExecutionSnapshotFilterMeetGE[$iMode]"),
        ("$g_aiFilterMinGold[$iMode]", "$g_aiRunExecutionSnapshotFilterMinGold[$iMode]"),
        ("$g_aiFilterMinElixir[$iMode]", "$g_aiRunExecutionSnapshotFilterMinElixir[$iMode]"),
        ("$g_abFilterMeetDEEnable[$iMode]", "$g_abRunExecutionSnapshotFilterMeetDEEnable[$iMode]"),
        ("$g_aiFilterMeetDEMin[$iMode]", "$g_aiRunExecutionSnapshotFilterMeetDEMin[$iMode]"),
        ("$g_aiArmyCompSpells[$iSpell]", "$g_aiRunExecutionSnapshotArmyCompSpells[$iSpell]"),
        ("$g_aiArmyCompSiegeMachines[$iSiege]", "$g_aiRunExecutionSnapshotArmyCompSiegeMachines[$iSiege]"),
        ("$g_bChkDonate", "$g_bRunExecutionSnapshotChkDonate"),
        ("$g_bDonateLikeCrazy", "$g_bRunExecutionSnapshotDonateLikeCrazy"),
        ("$g_bRequestTroopsEnable", "$g_bRunExecutionSnapshotRequestTroopsEnable"),
        ("$g_bChkClanGamesEnabled", "$g_bRunExecutionSnapshotChkClanGamesEnabled"),
        ("$g_bChkCollect", "$g_bRunExecutionSnapshotChkCollect"),
        ("$g_bAutoLabUpgradeEnable", "$g_bRunExecutionSnapshotAutoLabUpgradeEnable"),
        ("$g_bAutoUpgradeWallsEnable", "$g_bRunExecutionSnapshotAutoUpgradeWallsEnable"),
        ("$g_bAutoUpgradeEnabled", "$g_bRunExecutionSnapshotAutoUpgradeEnabled"),
        ("$g_bChkSwitchAcc", "$g_bRunExecutionSnapshotChkSwitchAcc"),
    )
    for live, snapshot in pairs:
        if f"{snapshot} = {live}" not in capture:
            errors.append(f"capture is missing planner field {live}")
        if f"{live} = {snapshot}" not in restore:
            errors.append(f"restore is missing planner field {live}")

    if "$g_bChkSwitchAcc = False" not in apply_intent:
        errors.append("planned runs do not disable legacy profile account switching")

    if "readConfig(" in restore or "applyConfig(" in restore:
        errors.append("restore must not reload or apply the whole profile")
    if "UpdateAndroidConfig($g_sRunExecutionSnapshotAndroidInstance, $g_sRunExecutionSnapshotAndroidEmulator)" not in restore:
        errors.append("explicit emulator overrides do not reinitialize the captured emulator adapter")
    if not (
        apply_prepared.find("_RunExecutionCaptureProfileSnapshot()")
        < apply_prepared.find("_RunExecutionApplyIntent($sError)")
    ):
        errors.append("the profile snapshot must be captured before planner fields are applied")
    if "RunProfileOverrideBegin(" not in capture or "RunProfileOverrideEnd()" not in restore:
        errors.append("snapshot lifecycle is not connected to the profile write guard")

    regular_guard = save_config.find("If RunProfileRegularConfigSerializationAllowed() Then")
    regular_save = save_config.find("SaveRegularConfig()")
    if regular_guard < 0 or regular_save < regular_guard:
        errors.append("SaveRegularConfig is not behind the one-run override guard")
    for required in ("SaveProfileConfig()", "SaveWeakBaseStats()", "SaveBuildingConfig()", "SaveClanGamesConfig()"):
        if required not in save_config:
            errors.append(f"routine save no longer preserves unrelated serializer {required}")
    if "RunProfileAutoLabUpgradeEnabledForSerialization($g_bAutoLabUpgradeEnable)" not in save_building:
        errors.append("building.ini can persist the one-run laboratory override")
    if "RunProfileClanGamesEnabledForSerialization($g_bChkClanGamesEnabled)" not in save_clan_games:
        errors.append("clangames.ini can persist the one-run Clan Games override")
    if "RunProfileDonateLikeCrazyForSerialization($g_bDonateLikeCrazy)" not in save_switch_accounts:
        errors.append("SwitchAccount INI can persist the one-run donation override")

    if guard.count("Global $g_bRunExecutionOverridesApplied") != 1:
        errors.append("the shared override flag must have exactly one declaration")
    if "Global $g_bRunExecutionOverridesApplied" in execution:
        errors.append("RunExecution duplicates the shared override flag")
    for helper in (
        "RunProfileRegularConfigSerializationAllowed",
        "RunProfileClanGamesEnabledForSerialization",
        "RunProfileAutoLabUpgradeEnabledForSerialization",
        "RunProfileDonateLikeCrazyForSerialization",
    ):
        if helper not in guard or helper not in autoit_test:
            errors.append(f"{helper} is not implemented and covered by the AutoIt regression")
    for gui_mode in ("[1, 2]",):
        if gui_mode not in autoit_test:
            errors.append("the AutoIt guard regression does not cover Normal and Mini GUI modes")
    if "RunProfileOverridesActive()" not in gui_mode_toggle:
        errors.append("Normal/Mini mode switching can overwrite active planner globals from stale controls")

    stop_adapter = bot_stop.find('AndroidBotStopEvent()')
    stop_restore = bot_stop.find('RunExecutionComplete("stopped")')
    if stop_adapter < 0 or stop_restore < stop_adapter:
        errors.append("the active emulator must receive its stop callback before profile restoration")

    if errors:
        print("Run override persistence checks failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print(f"Run override persistence checks passed ({len(pairs)} planner-owned fields).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
