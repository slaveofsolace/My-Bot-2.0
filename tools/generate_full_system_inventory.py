#!/usr/bin/env python3
"""Generate the fail-closed, non-duplicated My Bot full-system inventory.

Capabilities remain the canonical user-facing workflow count. Planner settings,
fixtures, binaries, control actions, infrastructure routes, and actuator owners
are facets of that system, not extra capabilities. The report deliberately
separates source-contract coverage from exact-current runtime proof.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import posixpath
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from tools import build_release, evaluate_support_readiness, validate_actuator_registry
except ModuleNotFoundError:  # Direct execution from tools/.
    import build_release  # type: ignore[no-redef]
    import evaluate_support_readiness  # type: ignore[no-redef]
    import validate_actuator_registry  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES_PATH = ROOT / "config/current-client-capabilities.json"
SETTINGS_PATH = ROOT / "config/ui/run-planner.settings.json"
FIXTURES_PATH = ROOT / "tests/fixtures/current-client/manifest.json"
PLANNER_SERVER_PATH = ROOT / "tools/planner_ui.py"
UPSTREAMS_PATH = ROOT / "upstreams.lock.json"

OG_GUI_RE = re.compile(
    r"^(?:COCBot/GUI/.+\.au3|COCBot/MBR GUI (?:Design|Control)\.au3)$"
)
OG_CONFIG_PATHS = {
    "COCBot/functions/Config/readConfig.au3",
    "COCBot/functions/Config/saveConfig.au3",
    "COCBot/functions/Config/applyConfig.au3",
}
OG_ENTRYPOINTS = {"MyBot.run.au3"}

# Test ownership is explicit.  A previous implementation searched every test for
# short strings such as ``start``, ``stop``, or ``None`` (the string form of a
# missing implementation).  That made unrelated tests look like deterministic
# coverage.  Shared structural tests are listed deliberately where they really
# do cover a whole catalog rather than inferred from prose or incidental tokens.
CAPABILITY_TESTS: dict[str, tuple[str, ...]] = {
    "emulator.bluestacks5": (
        "tests/python/test_bluestacks5_instance_binding.py",
        "tests/python/test_game_launch_only_control.py",
    ),
    "emulator.memu": ("tests/python/test_gameplay_scope_catalog.py",),
    "emulator.ldplayer9": ("tests/python/test_additional_emulator_adapters.py",),
    "emulator.mumu": ("tests/python/test_additional_emulator_adapters.py",),
    "orchestration.run-plan": (
        "tests/python/test_run_planner_preview.py",
        "tests/python/test_native_profile_autolaunch.py",
    ),
    "orchestration.account-queue": ("tests/autoit/RunContractsTest.au3",),
    "orchestration.battle-route": ("tests/autoit/RunContractsTest.au3",),
    "orchestration.run-session": ("tests/autoit/RunEngineTest.au3",),
    "orchestration.run-event": ("tests/python/test_run_battle_telemetry.py",),
    "orchestration.engine-initialization": ("tests/python/test_engine_probe_lifecycle.py",),
    "safety.no-gem-guard": ("tests/python/test_no_gem_runtime_guard.py",),
    "model.current-game": ("tests/autoit/GameCatalogTest.au3",),
    "model.screen-state-registry": (
        "tests/autoit/GameCatalogTest.au3",
        "tests/python/test_current_client_fixture_replay.py",
    ),
    "village.collectors": ("tests/python/test_open_home_collectors.py",),
    "village.loot-cart": ("tests/python/test_loot_cart_route.py",),
    "village.treasury": ("tests/python/test_treasury_route.py",),
    "events.daily-reward": ("tests/python/test_open_home_collectors.py",),
    "village.donations": ("tests/python/test_clan_donation_one_route.py",),
    "village.clan-request": ("tests/python/test_clan_request_route.py",),
    "army.training": ("tests/python/test_exact_recipe_training_route.py",),
    "village.upgrades-home": ("tests/python/test_home_upgrade_one_route.py",),
    "builder-base.upgrades": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_maintenance_cancellation.py",
    ),
    "builder-base.battles": ("tests/python/test_gameplay_scope_catalog.py",),
    "village.laboratory": ("tests/python/test_maintenance_cancellation.py",),
    "events.clan-games": ("tests/python/test_run_village_readiness.py",),
    "orchestration.multi-account": ("tests/python/test_external_profile_routing.py",),
    "runtime.recovery": ("tests/python/test_recovery_cancellation.py",),
    "clan-capital.upgrades": ("tests/python/test_gameplay_scope_catalog.py",),
    "army.recipes": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "army.cookbook": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "defense.crafted": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "battle.regular-ranked-split": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "battle.revenge": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "village.town-hall-18": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "village.guardians": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "heroes.dragon-duke": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "heroes.six-slot-layout": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "battle.legend-tiers": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "builder-base.additional-builder": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "heroes.hero-journey": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "chat.global-chat": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "battle.fast-forward": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "shop.chain-offers": (
        "tests/python/test_gameplay_scope_catalog.py",
        "tests/python/test_current_client_fixture_coverage.py",
    ),
    "village.pets": ("tests/python/test_android_display_mapping.py",),
    "village.hero-equipment": ("tests/python/test_run_village_readiness.py",),
    "rewards.achievements": ("tests/python/test_managed_reward_safety.py",),
    "rewards.personal-challenges": ("tests/python/test_gameplay_scope_catalog.py",),
    "village.obstacles": ("tests/python/test_maintenance_cancellation.py",),
    "clan-capital.forge": ("tests/python/test_gameplay_scope_catalog.py",),
    "village.helper-hut": ("tests/python/test_run_village_readiness.py",),
    "builder-base.star-laboratory": ("tests/python/test_gameplay_scope_catalog.py",),
    "builder-base.resources": ("tests/python/test_maintenance_cancellation.py",),
    "rewards.magic-items": ("tests/python/test_managed_reward_safety.py",),
    "rewards.streak-star-bonus": ("tests/python/test_return_home_current_treasure.py",),
    "village.boosts": ("tests/python/test_no_gem_runtime_guard.py",),
    "heroes.upgrades": ("tests/python/test_gameplay_scope_catalog.py",),
    "builder-base.hero-upgrades": ("tests/python/test_gameplay_scope_catalog.py",),
    "battle.trophy-drop": ("tests/python/test_gameplay_scope_catalog.py",),
    "battle.smart-zap": ("tests/python/test_smart_attack_policy.py",),
    "village.replay-share": ("tests/python/test_gameplay_scope_catalog.py",),
    "village.profile-report": ("tests/python/test_run_village_readiness.py",),
}

PLANNER_SETTING_TESTS = (
    "tests/python/test_run_planner_preview.py",
    "tests/python/test_planner_workbench_contract.py",
    "tests/python/test_native_planner_contract_controls.py",
)

CONTROL_ACTION_TESTS: dict[str, tuple[str, ...]] = {
    "check-engine": (
        "tests/python/test_engine_init_only_control.py",
        "tests/python/test_capture_check_engine_evidence.py",
    ),
    "launch-game": ("tests/python/test_game_launch_only_control.py",),
    "pause": ("tests/python/test_native_profile_autolaunch.py",),
    "resume": ("tests/python/test_planner_resource_polling.py",),
    "start": (
        "tests/python/test_native_profile_autolaunch.py",
        "tests/python/test_launcher_recovery.py",
    ),
    "stop": (
        "tests/python/test_manual_start_supervisor_cancel.py",
        "tests/python/test_recovery_cancellation.py",
    ),
}

COMPILE_TARGET_TESTS: dict[str, tuple[str, ...]] = {
    "My Bot 2.0.exe": (
        "tests/python/test_launcher_recovery.py",
        "tests/python/test_local_runtime_install.py",
    ),
    "MyBot.run.EngineProbe.exe": ("tests/python/test_engine_probe_lifecycle.py",),
    "MyBot.run.exe": (
        "tests/python/test_engine_probe_lifecycle.py",
        "tests/python/test_python_release.py",
    ),
    "MyBot.run.MiniGui.exe": (
        "tests/python/test_mini_engine_supervisor_forwarding.py",
        "tests/python/test_native_window_visibility.py",
    ),
    "MyBot.run.Watchdog.exe": ("tests/python/test_python_release.py",),
    "MyBot.run.Wmi.exe": ("tests/python/test_python_release.py",),
}

INFRASTRUCTURE_TESTS: dict[str, tuple[str, ...]] = {
    "package.localruntime": ("tests/python/test_python_release.py",),
    "installer.localruntime": ("tests/python/test_python_local_runtime_install.py",),
    "launcher.controller": ("tests/python/test_launcher_recovery.py",),
    "launcher.watchdog": ("tests/python/test_launcher_recovery.py",),
    "control-center.web": ("tests/python/test_planner_workbench_contract.py",),
    "control-center.native": ("tests/python/test_native_planner_contract_controls.py",),
    "engine.adapter": ("tests/python/test_engine_probe_lifecycle.py",),
    "diagnostics.events": ("tests/python/test_run_battle_telemetry.py",),
}

STOP_RECOVERY_TESTS = {
    "tests/python/test_completed_battle_recovery.py",
    "tests/python/test_maintenance_cancellation.py",
    "tests/python/test_manual_start_supervisor_cancel.py",
    "tests/python/test_recovery_cancellation.py",
    "tests/python/test_run_village_readiness.py",
    "tests/autoit/RunEngineTest.au3",
}

CONFIGURATION_PERSISTENCE_TESTS: dict[str, tuple[str, ...]] = {
    "COCBot/functions/Config/saveConfig.au3": (
        "tools/check_run_override_persistence.py",
        "tests/autoit/RunEngineTest.au3",
    ),
}

# These source rows have deterministic tests that inspect the named OG surface
# itself.  Rows omitted from this table remain DEFERRED; merely mentioning a
# function name or file basename somewhere in the suite is not test ownership.
OG_SURFACE_TESTS: dict[str, tuple[str, ...]] = {
    "MyBot.run.au3": (
        "tests/python/test_engine_probe_lifecycle.py",
        "tests/python/test_native_window_visibility.py",
    ),
    "COCBot/MBR GUI Design.au3": ("tests/python/test_native_window_visibility.py",),
    "COCBot/functions/Config/saveConfig.au3": (
        "tools/check_run_override_persistence.py",
        "tests/autoit/RunEngineTest.au3",
    ),
    "COCBot/functions/GUI/WindowPlacement.au3": (
        "tests/python/test_native_window_visibility.py",
    ),
    "COCBot/functions/Other/MBRFunc.au3": (
        "tests/python/test_engine_probe_lifecycle.py",
        "tests/python/test_manual_start_supervisor_cancel.py",
    ),
    "COCBot/functions/Other/WindowsArrange.au3": (
        "tests/python/test_native_window_visibility.py",
    ),
}

INFRASTRUCTURE = (
    {
        "id": "package.localruntime",
        "source_owners": ["tools/build_release.py", "tools/Build-Release.ps1"],
        "runtime_check": "deterministic package set, hashes, provenance, and rights gate",
    },
    {
        "id": "installer.localruntime",
        "source_owners": ["tools/install_local_runtime.py", "tools/Install-LocalRuntime.ps1"],
        "runtime_check": "isolated install, rollback, registration, Profiles preservation, and uninstall",
    },
    {
        "id": "launcher.controller",
        "source_owners": ["My Bot 2.0.au3", "MyBot.run.MiniGui.au3"],
        "runtime_check": "exact process lineage, controller readiness, and clean exit",
    },
    {
        "id": "launcher.watchdog",
        "source_owners": ["MyBot.run.Watchdog.au3"],
        "runtime_check": "bounded owned-process hang detection and restart/recovery",
    },
    {
        "id": "control-center.web",
        "source_owners": ["tools/planner_ui.py", "ui/planner.html", "ui/planner.js", "ui/planner.css"],
        "runtime_check": "browser bridge, persistence, cancellation, responsive UI, and accessibility",
    },
    {
        "id": "control-center.native",
        "source_owners": [
            "COCBot/GUI/MBR GUI Control Run Planner.au3",
            "COCBot/functions/Run/RunControlBridge.au3",
        ],
        "runtime_check": "native planner, command ownership, truthful status, and cancellation",
    },
    {
        "id": "engine.adapter",
        "source_owners": ["COCBot/functions/Other/MBRFunc.au3", "MyBot.run.EngineProbe.au3"],
        "runtime_check": "supervised managed initialization and exact backend identity",
    },
    {
        "id": "diagnostics.events",
        "source_owners": [
            "COCBot/functions/Run/RunEvent.au3",
            "COCBot/functions/Run/RunEventLog.au3",
        ],
        "runtime_check": "correlated monotonic events, diagnostics, and failure receipts",
    },
)

TRUTH_STATUSES = {
    "LIVE_PROVEN",
    "INSTALLED_MECHANISM_PROVEN",
    "FIXTURE_PROVEN",
    "BLOCKED_EXTERNAL",
    "UNSUPPORTED",
    "NOT_APPLICABLE",
}


def _assert_truth_status(status: str) -> str:
    if status not in TRUTH_STATUSES:
        raise ValueError(f"unknown truth status: {status}")
    return status


def _blocker_class(blockers: list[str]) -> str:
    if any("rights" in item.casefold() or "imgloc" in item.casefold() for item in blockers):
        return "RIGHTS"
    if any("fixture" in item.casefold() for item in blockers):
        return "FIXTURE"
    if any("exact-current" in item.casefold() or "runtime" in item.casefold() for item in blockers):
        return "RUNTIME"
    return "EXTERNAL" if blockers else "NONE"


def _capability_truth_status(readiness_row: dict[str, Any]) -> dict[str, Any]:
    blockers = list(readiness_row.get("current_binary_blockers") or [])
    if readiness_row.get("current_binary_ready"):
        return {
            "truth_status": _assert_truth_status("INSTALLED_MECHANISM_PROVEN"),
            "truth_blocker_class": "NONE",
            "truth_reason": "exact-current binary evidence satisfies the capability policy",
        }
    if readiness_row.get("ready_for_support_review"):
        return {
            "truth_status": _assert_truth_status("FIXTURE_PROVEN"),
            "truth_blocker_class": _blocker_class(blockers),
            "truth_reason": "source, fixture, or historical runtime evidence exists, but exact-current installed proof is still missing",
        }
    return {
        "truth_status": _assert_truth_status("BLOCKED_EXTERNAL"),
        "truth_blocker_class": _blocker_class(blockers),
        "truth_reason": "required fixture, runtime, or exact-current evidence is missing; the route must remain fail-closed",
    }


def _fixture_truth_status(status: str | None) -> dict[str, Any]:
    if status in {"verified", "redacted"}:
        return {
            "truth_status": _assert_truth_status("FIXTURE_PROVEN"),
            "truth_blocker_class": "NONE",
            "truth_reason": "privacy-safe fixture bytes and metadata are present",
        }
    return {
        "truth_status": _assert_truth_status("BLOCKED_EXTERNAL"),
        "truth_blocker_class": "FIXTURE",
        "truth_reason": "required current-client fixture capture is not present",
    }


def _pending_runtime_truth(reason: str) -> dict[str, Any]:
    return {
        "truth_status": _assert_truth_status("BLOCKED_EXTERNAL"),
        "truth_blocker_class": "RUNTIME",
        "truth_reason": reason,
    }


def _actuator_truth_status(policy: str) -> dict[str, Any]:
    if policy == "blocked":
        return {
            "truth_status": _assert_truth_status("UNSUPPORTED"),
            "truth_blocker_class": "POLICY",
            "truth_reason": "actuator is intentionally blocked by registry policy",
        }
    if policy in {"infrastructure", "test-only"}:
        return {
            "truth_status": _assert_truth_status("NOT_APPLICABLE"),
            "truth_blocker_class": "NONE",
            "truth_reason": f"actuator is classified as {policy}, not a user-facing capability",
        }
    return {
        "truth_status": _assert_truth_status("BLOCKED_EXTERNAL"),
        "truth_blocker_class": "RUNTIME",
        "truth_reason": "capability-owned actuator still requires exact-current route evidence",
    }


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _git(*args: str) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise ValueError(proc.stderr.decode("utf-8", errors="replace").strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def _pinned_og_commit() -> str:
    upstreams = _load(UPSTREAMS_PATH)
    matches = [item for item in upstreams.get("sources", []) if item.get("id") == "mybotrun-v8"]
    if len(matches) != 1 or not re.fullmatch(r"[0-9a-f]{40}", str(matches[0].get("commit", ""))):
        raise ValueError("upstreams.lock.json must pin exactly one mybotrun-v8 commit")
    return str(matches[0]["commit"])


def _og_family(path: str) -> str:
    folded = path.casefold()
    if path in OG_ENTRYPOINTS:
        return "runtime.entrypoint"
    if path in OG_CONFIG_PATHS:
        return "profile.settings"
    if OG_GUI_RE.fullmatch(path):
        if "bot - android" in folded:
            return "emulator.configuration"
        if "bot - profiles" in folded:
            return "profile.management"
        if "bot - stats" in folded:
            return "diagnostics.reports"
        if "bot - options" in folded:
            return "runtime.configuration"
        if "army" in folded or "troops" in folded:
            return "army.configuration"
        if "attack" in folded:
            return "battle.configuration"
        if "donate" in folded:
            return "village.donate-request"
        if "achievement" in folded:
            return "village.rewards"
        if "upgrade" in folded:
            return "village.upgrades"
        if "notify" in folded:
            return "notifications"
        if "misc" in folded:
            return "village.maintenance"
        if "collector" in folded:
            return "village.maintenance"
        if "preset" in folded:
            return "profile.settings"
        if any(name in folded for name in ("about", "bottom", "log", "splash")):
            return "native.shell"
        return "native.configuration"
    if not path.startswith("COCBot/functions/"):
        return ""
    relative = path.removeprefix("COCBot/functions/")
    top = relative.split("/", 1)[0]
    if top == "Android":
        return "emulator.runtime"
    if top == "Attack":
        return "builder-base.battles" if relative.startswith("Attack/BuilderBase/") else "battle.runtime"
    if top == "Config":
        return "profile.settings"
    if top == "CreateArmy":
        return "army.runtime"
    if top == "GUI":
        return "native.infrastructure"
    if top in {"Image Search", "Pixels", "Read Text", "Search"}:
        return "recognition"
    if top == "Main Screen":
        return "runtime.recovery"
    if top == "Other":
        return "shared.infrastructure"
    if top == "Village":
        if relative.startswith("Village/BuilderBase/"):
            return "builder-base.runtime"
        if relative.startswith("Village/Clan Games/"):
            return "village.clan-games"
        return "village.runtime"
    return ""


def _og_parity_rows(actuator_report: dict[str, Any]) -> tuple[str, list[dict[str, Any]], list[str]]:
    commit = _pinned_og_commit()
    tree: dict[str, str] = {}
    raw_tree = _git("ls-tree", "-r", "-z", commit, "--", "COCBot", "MyBot.run.au3")
    for raw_entry in raw_tree.split(b"\0"):
        if not raw_entry:
            continue
        metadata, raw_path = raw_entry.split(b"\t", 1)
        fields = metadata.decode("ascii").split()
        if len(fields) != 3 or fields[1] != "blob":
            continue
        tree[raw_path.decode("utf-8", errors="strict")] = fields[2]
    selected = sorted(
        path
        for path in tree
        if OG_GUI_RE.fullmatch(path)
        or path in OG_CONFIG_PATHS
        or path in OG_ENTRYPOINTS
        or path.startswith("COCBot/functions/")
    )

    current_actuators: dict[str, list[dict[str, Any]]] = {}
    for owner, classification in actuator_report["classifications"].items():
        owner_path = owner.rsplit("::", 1)[0]
        current_actuators.setdefault(owner_path, []).append({"owner": owner, **classification})

    compiled_sources, compile_evidence, dispatched_sources, dispatch_evidence = _autoit_reachability()

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in selected:
        family = _og_family(path)
        if not family:
            errors.append(f"unclassified pinned OG source: {path}")
        current_path = ROOT / path
        current_exists = current_path.is_file()
        current_bytes = current_path.read_bytes() if current_exists else b""
        current_blob = (
            hashlib.sha1(f"blob {len(current_bytes)}\0".encode("ascii") + current_bytes).hexdigest()
            if current_exists
            else None
        )
        classifications = current_actuators.get(path, [])
        policies = sorted({str(item.get("policy")) for item in classifications})
        capability_ids = sorted(
            {
                str(capability_id)
                for item in classifications
                for capability_id in item.get("capability_ids", [])
            }
        )
        role = (
            "user-visible-configuration"
            if OG_GUI_RE.fullmatch(path)
            else "persisted-settings"
            if path in OG_CONFIG_PATHS
            else "runtime-entrypoint"
            if path in OG_ENTRYPOINTS
            else "automation-or-infrastructure"
        )
        deterministic_tests = _mapped_tests(
            OG_SURFACE_TESTS,
            path,
            context="pinned OG source",
            required=False,
        )
        persistence_tests = _mapped_tests(
            CONFIGURATION_PERSISTENCE_TESTS,
            path,
            context="configuration persistence source",
            required=False,
        )
        source_presence = {
            "status": "PASS" if current_exists else "FAIL",
            "evidence": [path] if current_exists else [f"missing:{path}"],
        }
        if role in {"user-visible-configuration", "persisted-settings"}:
            configuration_persistence = {
                "status": "PASS" if persistence_tests else "DEFERRED",
                "evidence": persistence_tests,
                "reason": (
                    "explicit persistence regression owns this source"
                    if persistence_tests
                    else "no explicit persistence regression is mapped to this source"
                ),
            }
        else:
            configuration_persistence = {
                "status": "NOT_APPLICABLE",
                "evidence": [],
                "reason": "source does not own user-visible or persisted configuration",
            }
        compile_inclusion = {
            "status": (
                "FAIL"
                if not current_exists
                else "PASS"
                if path in compiled_sources
                else "DEFERRED"
            ),
            "evidence": compile_evidence.get(path, []),
            "reason": (
                "present in the MyBot.run.au3 include closure"
                if path in compiled_sources
                else "source exists but is not proven present in the entrypoint include closure"
            ),
        }
        dispatch_reachability = {
            "status": (
                "FAIL"
                if not current_exists
                else "PASS"
                if path in dispatched_sources
                else "DEFERRED"
            ),
            "evidence": dispatch_evidence.get(path, []),
            "reason": (
                "a function is reachable from MyBot.run.au3 top-level executable calls"
                if path in dispatched_sources
                else "compile inclusion alone is not dispatch; no invoked function path was established"
            ),
        }
        actuator_ownership = {
            "status": "FAIL" if not current_exists else "PASS" if classifications else "NOT_APPLICABLE",
            "owners": sorted(str(item["owner"]) for item in classifications),
            "policies": policies,
            "capability_ids": capability_ids,
            "reason": (
                "every detected actuator owner has an explicit registry policy"
                if classifications
                else "no direct actuator site was detected in this source"
            ),
        }
        recovery_tests = sorted(set(deterministic_tests) & STOP_RECOVERY_TESTS)
        if role in {"user-visible-configuration", "persisted-settings"}:
            stop_recovery = {
                "status": "NOT_APPLICABLE",
                "evidence": [],
                "reason": "configuration-only source does not own a running operation",
            }
        else:
            stop_recovery = {
                "status": "FAIL" if not current_exists else "PASS" if recovery_tests else "DEFERRED",
                "evidence": recovery_tests,
                "reason": (
                    "explicit stop/recovery regression owns this source"
                    if recovery_tests
                    else "no explicit stop/recovery regression is mapped to this source"
                ),
            }
        deterministic_test = {
            "status": "PASS" if deterministic_tests else "DEFERRED",
            "tests": deterministic_tests,
            "reason": (
                "explicit deterministic test mapping"
                if deterministic_tests
                else "no deterministic test is explicitly mapped to this source"
            ),
        }
        dimension_statuses = (
            source_presence["status"],
            configuration_persistence["status"],
            compile_inclusion["status"],
            dispatch_reachability["status"],
            actuator_ownership["status"],
            stop_recovery["status"],
            deterministic_test["status"],
        )
        composite_status = (
            "FAIL"
            if "FAIL" in dimension_statuses
            else "PASS"
            if all(status in {"PASS", "NOT_APPLICABLE"} for status in dimension_statuses)
            else "DEFERRED"
        )
        rows.append(
            {
                "path": path,
                "family": family,
                "role": role,
                "og_git_blob": tree[path],
                "current_sha256": hashlib.sha256(current_bytes).hexdigest() if current_exists else None,
                "current_git_blob": current_blob,
                "current_source_state": (
                    "missing" if not current_exists else "unchanged" if current_blob == tree[path] else "adapted"
                ),
                "current_actuator_policies": policies,
                "current_capability_ids": capability_ids,
                "source_presence": source_presence,
                "configuration_persistence": configuration_persistence,
                "compile_inclusion": compile_inclusion,
                "dispatch_reachability": dispatch_reachability,
                "actuator_ownership": actuator_ownership,
                "stop_recovery": stop_recovery,
                "deterministic_test": deterministic_test,
                "source_contract": composite_status,
                "composite_status": composite_status,
                "exact_current_runtime_status": "BLOCKED_EXTERNAL",
                "truth_status": "BLOCKED_EXTERNAL",
                "truth_blocker_class": "RUNTIME",
                "truth_reason": "pinned OG source parity is source-level only until exact-current installed runtime evidence proves the route",
            }
        )
        if not current_exists:
            errors.append(f"pinned OG source is missing from current master: {path}")
    if len(selected) != len(set(selected)):
        errors.append("pinned OG source inventory contains duplicates")
    return commit, rows, errors


def _mapped_tests(
    mapping: dict[str, tuple[str, ...]],
    key: str,
    *,
    context: str,
    required: bool = True,
) -> list[str]:
    if key not in mapping:
        if required:
            raise ValueError(f"{context} has no explicit test mapping: {key}")
        return []
    tests = list(mapping[key])
    if not tests or len(tests) != len(set(tests)):
        raise ValueError(f"{context} has an empty or duplicate test mapping: {key}")
    missing = [path for path in tests if not (ROOT / path).is_file()]
    if missing:
        raise ValueError(f"{context} maps {key} to missing tests: {missing}")
    return tests


def _shared_tests(paths: tuple[str, ...], *, context: str) -> list[str]:
    tests = list(paths)
    if not tests or len(tests) != len(set(tests)):
        raise ValueError(f"{context} has an empty or duplicate shared test mapping")
    missing = [path for path in tests if not (ROOT / path).is_file()]
    if missing:
        raise ValueError(f"{context} maps to missing tests: {missing}")
    return tests


def _validate_mapping_domain(label: str, mapping: dict[str, tuple[str, ...]], expected: set[str]) -> None:
    actual = set(mapping)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{label} test mapping domain mismatch; missing={missing}, extra={extra}")


def _read_autoit(path: Path) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"unable to decode AutoIt source: {path.relative_to(ROOT).as_posix()}")


def _autoit_code_without_comments(text: str) -> str:
    output: list[str] = []
    block_comment = False
    for line in text.splitlines():
        folded = line.lstrip().casefold()
        if folded.startswith(("#comments-start", "#cs")):
            block_comment = True
            continue
        if block_comment:
            if folded.startswith(("#comments-end", "#ce")):
                block_comment = False
            continue
        if folded.startswith(";"):
            continue
        quote = ""
        code: list[str] = []
        index = 0
        while index < len(line):
            char = line[index]
            if char in {'"', "'"}:
                if quote == char and index + 1 < len(line) and line[index + 1] == char:
                    code.extend((char, char))
                    index += 2
                    continue
                if not quote:
                    quote = char
                elif quote == char:
                    quote = ""
            if char == ";" and not quote:
                break
            code.append(char)
            index += 1
        output.append("".join(code))
    return "\n".join(output)


def _mask_autoit_strings(text: str) -> str:
    output: list[str] = []
    quote = ""
    index = 0
    while index < len(text):
        char = text[index]
        if char in {'"', "'"}:
            if quote == char and index + 1 < len(text) and text[index + 1] == char:
                output.extend((" ", " "))
                index += 2
                continue
            if not quote:
                quote = char
            elif quote == char:
                quote = ""
            output.append(" ")
        elif quote:
            output.append("\n" if char == "\n" else " ")
        else:
            output.append(char)
        index += 1
    return "".join(output)


def _literal_autoit_string(text: str, start: int) -> tuple[str, int] | None:
    if start >= len(text) or text[start] not in {'"', "'"}:
        return None
    quote = text[start]
    value: list[str] = []
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == quote:
            if index + 1 < len(text) and text[index + 1] == quote:
                value.append(quote)
                index += 2
                continue
            return "".join(value), index + 1
        value.append(char)
        index += 1
    return None


def _autoit_invocations(code: str) -> list[tuple[str, str]]:
    masked = _mask_autoit_strings(code)
    invocations = {
        (match.group(1), "direct")
        for match in re.finditer(r"(?<![.$@])\b([A-Za-z_]\w*)\s*\(", masked)
    }
    for match in re.finditer(r"(?<![.$@])\bCall\s*\(", masked, flags=re.IGNORECASE):
        index = match.end()
        while index < len(code) and code[index].isspace():
            index += 1
        parts: list[str] = []
        while True:
            literal = _literal_autoit_string(code, index)
            if literal is None:
                parts = []
                break
            value, index = literal
            parts.append(value)
            while index < len(code) and code[index].isspace():
                index += 1
            if index >= len(code) or code[index] != "&":
                break
            index += 1
            while index < len(code) and code[index].isspace():
                index += 1
        target = "".join(parts)
        if (
            parts
            and index < len(code)
            and code[index] in {",", ")"}
            and re.fullmatch(r"[A-Za-z_]\w*", target)
        ):
            invocations.add((target, "literal-call"))
    return sorted(invocations, key=lambda item: (item[0].casefold(), item[1]))


def _autoit_source_parts(text: str) -> tuple[str, list[tuple[str, str]]]:
    code = _autoit_code_without_comments(text)
    top_level: list[str] = []
    functions: list[tuple[str, str]] = []
    current_name = ""
    current_body: list[str] = []
    for line in code.splitlines():
        if not current_name:
            start = re.match(r"^\s*Func\s+([A-Za-z_]\w*)\s*\(", line, flags=re.IGNORECASE)
            if start:
                current_name = start.group(1)
                current_body = []
            else:
                top_level.append(line)
            continue
        if re.match(r"^\s*EndFunc\b", line, flags=re.IGNORECASE):
            functions.append((current_name, "\n".join(current_body)))
            current_name = ""
            current_body = []
        else:
            current_body.append(line)
    return "\n".join(top_level), functions


def _autoit_reachability_from_sources(
    sources: dict[str, str],
    entrypoint: str = "MyBot.run.au3",
) -> tuple[set[str], dict[str, list[str]], set[str], dict[str, list[str]]]:
    canonical = {path.casefold(): path for path in sources}
    if entrypoint.casefold() not in canonical:
        raise ValueError(f"AutoIt entrypoint is missing: {entrypoint}")
    entrypoint = canonical[entrypoint.casefold()]
    cleaned_sources = {path: _autoit_code_without_comments(text) for path, text in sources.items()}
    parts = {path: _autoit_source_parts(text) for path, text in sources.items()}

    include_edges: dict[str, set[str]] = defaultdict(set)
    for path, code in cleaned_sources.items():
        for include in re.findall(r'(?im)^\s*#include\s+["<]([^">]+)[">]', code):
            normalized = include.replace("\\", "/")
            candidates = (
                posixpath.normpath(posixpath.join(posixpath.dirname(path), normalized)),
                posixpath.normpath(normalized),
            )
            for candidate in candidates:
                target = canonical.get(candidate.casefold())
                if target is not None:
                    include_edges[path].add(target)
                    break

    compiled = {entrypoint}
    compile_evidence: dict[str, list[str]] = {entrypoint: ["entrypoint"]}
    pending_sources = [entrypoint]
    while pending_sources:
        source = pending_sources.pop(0)
        for target in sorted(include_edges.get(source, set())):
            if target in compiled:
                continue
            compiled.add(target)
            compile_evidence[target] = [f"include:{source}"]
            pending_sources.append(target)

    definitions: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for path in sorted(compiled):
        for name, body in parts[path][1]:
            definitions[name.casefold()].append((path, name, body))

    dispatched = {entrypoint}
    dispatch_evidence: dict[str, set[str]] = defaultdict(set)
    dispatch_evidence[entrypoint].add("entrypoint:top-level")
    pending_functions = [
        (name, kind, f"{entrypoint}::<top-level>")
        for name, kind in _autoit_invocations(parts[entrypoint][0])
    ]
    visited: set[tuple[str, str]] = set()
    while pending_functions:
        target_name, kind, caller = pending_functions.pop(0)
        matches = definitions.get(target_name.casefold(), [])
        if len(matches) != 1:
            continue
        path, declared_name, body = matches[0]
        function_id = (path, declared_name.casefold())
        dispatch_evidence[path].add(f"{kind}:{declared_name}:{caller}")
        dispatched.add(path)
        if function_id in visited:
            continue
        visited.add(function_id)
        pending_functions.extend(
            (name, child_kind, f"{path}::{declared_name}")
            for name, child_kind in _autoit_invocations(body)
        )

    return (
        compiled,
        {path: sorted(values) for path, values in compile_evidence.items()},
        dispatched,
        {path: sorted(values) for path, values in dispatch_evidence.items()},
    )


def _autoit_reachability() -> tuple[set[str], dict[str, list[str]], set[str], dict[str, list[str]]]:
    source_paths = sorted(
        {
            *ROOT.glob("*.au3"),
            *(ROOT / "COCBot").glob("**/*.au3"),
        }
    )
    sources = {path.relative_to(ROOT).as_posix(): _read_autoit(path) for path in source_paths}
    return _autoit_reachability_from_sources(sources)


def _control_actions() -> list[str]:
    tree = ast.parse(PLANNER_SERVER_PATH.read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "CONTROL_ACTIONS" for target in node.targets):
            continue
        value = ast.literal_eval(node.value)
        if not isinstance(value, set) or not all(isinstance(item, str) for item in value):
            raise ValueError("CONTROL_ACTIONS must be a literal set of strings")
        return sorted(value)
    raise ValueError("CONTROL_ACTIONS was not found")


def _planner_settings(document: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    automated_tests = _shared_tests(PLANNER_SETTING_TESTS, context="planner settings")
    for section in document.get("sections", []):
        if not isinstance(section, dict):
            continue
        for setting in section.get("settings", []):
            if not isinstance(setting, dict):
                continue
            setting_id = setting.get("id")
            if not isinstance(setting_id, str) or not setting_id:
                raise ValueError("planner setting id must be non-empty")
            if setting_id in seen:
                raise ValueError(f"duplicate planner setting: {setting_id}")
            seen.add(setting_id)
            result.append(
                {
                    "id": setting_id,
                    "section": section.get("id"),
                    "type": setting.get("type"),
                    "source_owner": "config/ui/run-planner.settings.json",
                    "automated_tests": list(automated_tests),
                    "source_contract": "PASS",
                    "runtime_status": "BLOCKED_EXTERNAL",
                    **_pending_runtime_truth(
                        "planner setting persistence is source-tested; exact installed execution depends on the selected route and live/state evidence"
                    ),
                }
            )
    return result


def build_report(root: Path = ROOT) -> dict[str, Any]:
    if root.resolve() != ROOT.resolve():
        raise ValueError("the inventory generator must run against its own repository root")
    capabilities_document = _load(CAPABILITIES_PATH)
    settings_document = _load(SETTINGS_PATH)
    fixtures_document = _load(FIXTURES_PATH)
    capabilities = capabilities_document.get("capabilities", [])
    fixtures = fixtures_document.get("required_fixtures", [])
    if not isinstance(capabilities, list) or not isinstance(fixtures, list):
        raise ValueError("capability and fixture inventories must be lists")

    capability_ids = [item.get("id") for item in capabilities if isinstance(item, dict)]
    if len(capability_ids) != len(capabilities) or any(not isinstance(item, str) or not item for item in capability_ids):
        raise ValueError("every capability requires a non-empty id")
    duplicates = sorted(item for item, count in Counter(capability_ids).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate capabilities: {duplicates}")
    _validate_mapping_domain("capability", CAPABILITY_TESTS, set(capability_ids))

    readiness = evaluate_support_readiness.evaluate_readiness(root=ROOT)
    readiness_by_id = {row["id"]: row for row in readiness["results"]}
    fixture_by_capability: dict[str, list[dict[str, Any]]] = {item: [] for item in capability_ids}
    fixture_rows: list[dict[str, Any]] = []
    fixture_ids: set[str] = set()
    for fixture in fixtures:
        if not isinstance(fixture, dict) or not isinstance(fixture.get("id"), str):
            raise ValueError("every fixture requires an id")
        fixture_id = fixture["id"]
        if fixture_id in fixture_ids:
            raise ValueError(f"duplicate fixture: {fixture_id}")
        fixture_ids.add(fixture_id)
        mapped = fixture.get("capability_ids", [])
        if not isinstance(mapped, list) or any(item not in fixture_by_capability for item in mapped):
            raise ValueError(f"fixture {fixture_id} references an unknown capability")
        row = {
            "id": fixture_id,
            "status": fixture.get("status"),
            "capability_ids": mapped,
            "image_path": fixture.get("image_path"),
            "metadata_path": fixture.get("metadata_path"),
            "final_status": _fixture_truth_status(fixture.get("status")).get("truth_status"),
            **_fixture_truth_status(fixture.get("status")),
        }
        fixture_rows.append(row)
        for capability_id in mapped:
            fixture_by_capability[capability_id].append(row)

    policies = capabilities_document.get("runtime_evidence_policy", {}).get("capabilities", {})
    capability_rows: list[dict[str, Any]] = []
    for capability in capabilities:
        capability_id = capability["id"]
        readiness_row = readiness_by_id.get(capability_id)
        if readiness_row is None:
            raise ValueError(f"readiness evaluator omitted capability: {capability_id}")
        policy = policies.get(capability_id, {})
        required_tests = policy.get("required_tests", []) if isinstance(policy, dict) else []
        implementation = capability.get("implementation")
        automatic = _mapped_tests(CAPABILITY_TESTS, capability_id, context="capability")
        truth = _capability_truth_status(readiness_row)
        capability_rows.append(
            {
                "id": capability_id,
                "declared_status": capability.get("status"),
                "source_owner": implementation,
                "verification_contract": capability.get("verification", []),
                "automated_tests": automatic,
                "fixtures": [item["id"] for item in fixture_by_capability[capability_id]],
                "runtime_checks": required_tests,
                "historical_ready": readiness_row["ready_for_support_review"],
                "exact_current_ready": readiness_row["current_binary_ready"],
                "blockers": readiness_row["current_binary_blockers"],
                "final_status": truth["truth_status"],
                **truth,
            }
        )

    planner_settings = _planner_settings(settings_document)
    control_actions = _control_actions()
    _validate_mapping_domain("control action", CONTROL_ACTION_TESTS, set(control_actions))
    control_rows = [
        {
            "id": action,
            "source_owner": "tools/planner_ui.py",
            "automated_tests": _mapped_tests(CONTROL_ACTION_TESTS, action, context="control action"),
            "source_contract": "PASS",
            "runtime_status": "BLOCKED_EXTERNAL",
            **_pending_runtime_truth(
                "control action has source-level tests, but exact installed UI/runtime evidence is tracked outside the source inventory"
            ),
        }
        for action in control_actions
    ]
    compile_targets = build_release.DEFAULT_CONTRACT.compile_targets
    _validate_mapping_domain(
        "compile target",
        COMPILE_TARGET_TESTS,
        {target.output for target in compile_targets},
    )
    compile_rows = [
        {
            "source": target.source,
            "output": target.output,
            "subsystem": target.subsystem,
            "pragma_output": target.pragma_output,
            "automated_tests": _mapped_tests(
                COMPILE_TARGET_TESTS,
                target.output,
                context="compile target",
            ),
            "source_contract": "PASS",
            "installed_runtime_status": "BLOCKED_EXTERNAL",
            **_pending_runtime_truth(
                "compile target is source-tested; installed binary provenance and launch evidence are package-specific"
            ),
        }
        for target in compile_targets
    ]
    _validate_mapping_domain(
        "infrastructure route",
        INFRASTRUCTURE_TESTS,
        {str(item["id"]) for item in INFRASTRUCTURE},
    )
    infrastructure_rows = [
        {
            **item,
            "automated_tests": _mapped_tests(
                INFRASTRUCTURE_TESTS,
                str(item["id"]),
                context="infrastructure route",
            ),
            "source_contract": "PASS",
            "runtime_status": "BLOCKED_EXTERNAL",
            **_pending_runtime_truth(
                "infrastructure route is source-tested; exact installed runtime evidence is package-specific"
            ),
        }
        for item in INFRASTRUCTURE
    ]

    actuators = validate_actuator_registry.build_report()
    actuator_rows = [
        {
            "owner": owner,
            **classification,
            "final_status": _actuator_truth_status(str(classification["policy"]))["truth_status"],
            **_actuator_truth_status(str(classification["policy"])),
        }
        for owner, classification in sorted(actuators["classifications"].items())
    ]
    errors = list(readiness["errors"]) + list(actuators["errors"])
    og_commit, og_parity, og_errors = _og_parity_rows(actuators)
    errors.extend(og_errors)
    if len(capability_rows) != len(readiness_by_id):
        errors.append("capability/readiness cardinality mismatch")
    if len(actuator_rows) != actuators["owners"]:
        errors.append("actuator owner cardinality mismatch")

    return {
        "schema_version": 2,
        "scope_rule": "Capabilities are canonical; every other collection is a non-additive system facet.",
        "counts": {
            "capabilities": len(capability_rows),
            "planner_settings": len(planner_settings),
            "fixtures": len(fixture_rows),
            "compile_targets": len(compile_rows),
            "control_actions": len(control_rows),
            "infrastructure_routes": len(infrastructure_rows),
            "actuator_owners": len(actuator_rows),
            "actuator_sites": actuators["sites"],
            "exact_current_capabilities_ready": sum(item["exact_current_ready"] for item in capability_rows),
            "capability_truth_statuses": dict(Counter(item["truth_status"] for item in capability_rows)),
            "fixture_truth_statuses": dict(Counter(item["truth_status"] for item in fixture_rows)),
            "actuator_truth_statuses": dict(Counter(item["truth_status"] for item in actuator_rows)),
            "og_parity_sources": len(og_parity),
            "og_gui_sources": sum(item["role"] == "user-visible-configuration" for item in og_parity),
            "og_function_sources": sum(item["path"].startswith("COCBot/functions/") for item in og_parity),
            "og_unclassified_sources": sum(not item["family"] for item in og_parity),
        },
        "pinned_og_commit": og_commit,
        "og_parity": og_parity,
        "capabilities": capability_rows,
        "planner_settings": planner_settings,
        "fixtures": fixture_rows,
        "compile_targets": compile_rows,
        "control_actions": control_rows,
        "infrastructure_routes": infrastructure_rows,
        "actuator_owners": actuator_rows,
        "errors": errors,
        "warnings": list(readiness["evidence_validation"]["warnings"]) + list(actuators["warnings"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()
    try:
        report = build_report()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"full-system inventory failed: {exc}")
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_path:
        args.json_path.write_text(rendered, encoding="utf-8")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
