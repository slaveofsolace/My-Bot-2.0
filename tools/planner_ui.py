#!/usr/bin/env python3
"""Serve the local Run Planner control center.

The server is deliberately small: standard library only, loopback only, no credentials, and no
remote assets. It validates and atomically writes the flat planner document consumed by AutoIt.

Merge note (cloud base + Windows hardening):
    The save contract is strict in one direction only. A POST naming a setting this planner does not
    have is refused with 400 and nothing is written, because the caller and the server disagree about
    what exists and guessing would silently drop the caller's intent. Values that are merely out of
    range, or a boolean spelled as a word, or a Hero list over the ceiling, are adjusted, saved, and
    reported -- those are recoverable. The AutoIt reader stays deliberately lenient; different
    direction, different concern.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
import re
import stat
import tempfile
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SERVICE_NAME = "my-bot-control-center"
BRIDGE_PROTOCOL = "autoit-control-file-v1"
HEALTH_PROTOCOL = "my-bot-control-center-health-v2"
SERVICE_REPO_ROOT = str(ROOT.resolve())
# Capture the loaded service build once. If this file is replaced while an older process is still
# listening, its health response keeps the old digest and the native client refuses to reuse it.
SERVICE_BUILD_SHA256 = hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()
SERVICE_OWNER_TOKEN = ""
METADATA = ROOT / "config/ui/run-planner.settings.json"
CAPABILITIES = ROOT / "config/current-client-capabilities.json"
UI_HTML = ROOT / "ui/planner.html"
UI_CSS = ROOT / "ui/planner.css"
UI_JS = ROOT / "ui/planner.js"
UI_FAVICON = ROOT / "ui/favicon.svg"

PLAN_PATH = ROOT / "config/run-plan.local.json"
EVENTS_PATH = ROOT / "logs/run-events.jsonl"
PROFILES_ROOT = ROOT / "Profiles"
CONTROL_COMMAND_PATH = ROOT / "config/control-command.local.json"
CONTROL_STATUS_PATH = ROOT / "config/control-status.local.json"
ENGINE_INIT_RECEIPT_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "My Bot 2.0" / "engine-init-owner-v1.json"
ENGINE_INIT_CANCEL_PATH = ROOT / "config/engine-init-cancel.local.json"
ENGINE_INIT_RECEIPT_MAX_BYTES = 4096
ENGINE_INIT_ACTIVE_PHASES = {
    "prepared": 1,
    "pool-entered": 2,
    "pool-returned": 3,
    "max-entered": 4,
    "max-returned": 5,
    "android-entered": 6,
    "android-returned": 7,
    "gui-entered": 8,
}

MAX_REQUEST_BYTES = 256 * 1024
MAX_TAIL_BYTES = 512 * 1024
MAX_NATIVE_LOG_LINES = 600
CONTROL_STATUS_MAX_AGE_SECONDS = 4.0
CONTROL_STATUS_BUSY_MAX_AGE_SECONDS = 45.0
CONTROL_STATUS_READ_RETRY_SECONDS = 0.02
CONTROL_STATUS_READ_ATTEMPTS = 5
CONTROL_BUSY_STATES = {"starting", "stopping", "closing"}
ENGINE_INIT_CANCEL_CONTEXT_WAIT_SECONDS = 3.0
ENGINE_INIT_CANCEL_CONTEXT_POLL_SECONDS = 0.025
CONTROL_ACTIONS = {"start", "stop", "pause", "resume", "check-engine"}
CONTROL_LOCK = threading.Lock()
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
DIAGNOSTIC_ARTIFACTS = {
    "native_app": ROOT / "MyBot.run.exe",
    "engine_probe": ROOT / "MyBot.run.EngineProbe.exe",
    "managed_engine": ROOT / "lib/MyBot.run.dll",
}
DIAGNOSTIC_ENGINE_FIELDS = {
    "connected", "state", "authorization_ready", "engine_available", "engine_probe_state", "product_name",
    "product_version", "engine_version", "plan_active", "plan_message", "session_id",
    "emulator", "emulator_attached", "window_attached", "adb_ready", "game_ready", "bot_pid", "last_command", "last_outcome", "last_command_message",
    "message", "last_seen_at", "age_seconds",
}
DIAGNOSTIC_EVENT_FIELDS = {"timestamp_ms", "type", "severity", "message", "surface_id", "verification_state"}


def validated_external_profiles_root(value: str, *, local_app_data: str | os.PathLike[str] | None = None) -> Path:
    """Resolve an existing profile directory confined below the current user's LOCALAPPDATA."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("profiles root must be a non-empty absolute directory")
    candidate = Path(value)
    if not candidate.is_absolute():
        raise ValueError("profiles root must be absolute")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError("profiles root does not exist") from exc
    if not resolved.is_dir():
        raise ValueError("profiles root is not a directory")

    local_value = local_app_data if local_app_data is not None else os.environ.get("LOCALAPPDATA", "")
    if not local_value:
        raise ValueError("LOCALAPPDATA is unavailable")
    local_candidate = Path(local_value)
    if not local_candidate.is_absolute():
        raise ValueError("LOCALAPPDATA is not absolute")
    try:
        local_root = local_candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError("LOCALAPPDATA does not exist") from exc
    if not local_root.is_dir():
        raise ValueError("LOCALAPPDATA is not a directory")
    try:
        relative = resolved.relative_to(local_root)
    except ValueError as exc:
        raise ValueError("profiles root must remain below LOCALAPPDATA") from exc
    if not relative.parts:
        raise ValueError("profiles root cannot be LOCALAPPDATA itself")
    return resolved


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def _path_is_reparse(path: Path) -> bool:
    """Fail closed on a symlink, junction, or other Windows reparse point."""
    try:
        metadata = path.lstat()
    except OSError:
        return True
    is_junction = getattr(os.path, "isjunction", None)
    return bool(
        path.is_symlink()
        or (callable(is_junction) and is_junction(path))
        or (
            getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
    )


def engine_init_cancel_context() -> dict | None:
    """Read only the bounded ownership fields needed to mirror Stop to the launcher."""
    path = ENGINE_INIT_RECEIPT_PATH
    try:
        parent_metadata = path.parent.lstat()
        metadata = path.lstat()
    except OSError:
        return None
    if (
        not stat.S_ISDIR(parent_metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or _path_is_reparse(path.parent)
        or _path_is_reparse(path)
        or metadata.st_size <= 0
        or metadata.st_size > ENGINE_INIT_RECEIPT_MAX_BYTES
    ):
        return None
    try:
        with path.open("rb") as stream:
            raw = stream.read(ENGINE_INIT_RECEIPT_MAX_BYTES + 1)
        if len(raw) > ENGINE_INIT_RECEIPT_MAX_BYTES:
            return None
        receipt = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(receipt, dict) or receipt.get("schema") != "engine-init-supervisor-v1":
        return None
    token = receipt.get("token")
    start_request_id = receipt.get("start_request_id")
    phase = receipt.get("phase")
    sequence = receipt.get("sequence")
    if (
        not isinstance(token, str)
        or re.fullmatch(r"[0-9a-f]{64}", token) is None
        or not isinstance(start_request_id, str)
        or re.fullmatch(r"[A-Za-z0-9._-]{1,80}", start_request_id) is None
        or phase not in ENGINE_INIT_ACTIVE_PHASES
        or isinstance(sequence, bool)
        or sequence != ENGINE_INIT_ACTIVE_PHASES[phase]
    ):
        return None
    return {"token": token, "start_request_id": start_request_id}


def wait_for_engine_init_cancel_context(expected_start_request_id: str) -> dict | None:
    """Bridge the accepted-command to prepared-receipt race without trusting a foreign receipt."""
    if re.fullmatch(r"[A-Za-z0-9._-]{1,80}", expected_start_request_id) is None:
        return None
    deadline = time.monotonic() + ENGINE_INIT_CANCEL_CONTEXT_WAIT_SECONDS
    while True:
        context = engine_init_cancel_context()
        if context is not None:
            return context if context["start_request_id"] == expected_start_request_id else None
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        time.sleep(min(ENGINE_INIT_CANCEL_CONTEXT_POLL_SECONDS, remaining))


def metadata_document() -> dict:
    return read_json(METADATA, {"sections": []})


def settings_index() -> dict[str, dict]:
    return {
        setting["id"]: setting
        for section in metadata_document().get("sections", [])
        for setting in section.get("settings", [])
    }


def normalized_default(setting: dict):
    value = setting.get("default", "")
    if setting.get("type") == "multi-select":
        if isinstance(value, list):
            return list(value)
        return [] if value in (None, "") else [value]
    return value


def default_plan() -> dict:
    return {setting_id: normalized_default(setting) for setting_id, setting in settings_index().items()}


def validate_plan(submitted: dict) -> tuple[dict, list[str], list[str]]:
    """Normalize the complete planner document without guessing ambiguous values.

    Returns (clean, adjustments, rejected). `adjustments` records values that were coerced or
    clamped and then saved. `rejected` records settings this planner does not have; a caller that
    names one gets a 400 and nothing is written.
    """
    known = settings_index()
    clean: dict = {}
    adjustments: list[str] = []
    rejected: list[str] = []

    for key, value in submitted.items():
        setting = known.get(key)
        if setting is None:
            rejected.append(f"{key} is not a setting this planner has")
            continue

        kind = setting.get("type")
        default = normalized_default(setting)

        if kind == "boolean":
            if isinstance(value, bool):
                clean[key] = value
            elif isinstance(value, str):
                token = value.strip().lower()
                if token in {"true", "1", "yes", "on"}:
                    clean[key] = True
                elif token in {"false", "0", "no", "off", ""}:
                    clean[key] = False
                else:
                    adjustments.append(f"{key}: {value!r} is not a yes/no value, kept the default")
                    clean[key] = default
            else:
                adjustments.append(f"{key}: {type(value).__name__} is not a yes/no value, kept the default")
                clean[key] = default

        elif kind == "integer":
            if isinstance(value, bool):
                adjustments.append(f"{key}: boolean is not a whole number, kept the default")
                clean[key] = default
                continue
            try:
                number = int(value)
            except (TypeError, ValueError, OverflowError):
                adjustments.append(f"{key}: not a whole number, kept the default")
                clean[key] = default
                continue
            rules = setting.get("validation", {})
            low, high = rules.get("minimum"), rules.get("maximum")
            if isinstance(low, int) and number < low:
                adjustments.append(f"{key}: {number} is below {low}, clamped")
                number = low
            if isinstance(high, int) and number > high:
                adjustments.append(f"{key}: {number} is above {high}, clamped")
                number = high
            clean[key] = number

        elif kind in {"select", "multi-select"}:
            choices = {option["value"] for option in setting.get("options", [])}
            if kind == "multi-select":
                incoming = value if isinstance(value, list) else [value]
                picked: list[str] = []
                for item in incoming:
                    if not isinstance(item, str) or item not in choices:
                        adjustments.append(f"{key}: {item!r} is not an option")
                    elif item not in picked:
                        picked.append(item)
                # A MISSING ceiling is treated as a fault, not as "no ceiling". Silently falling
                # through on None is exactly how the Hero four-slot cap would disappear from the
                # server while still looking enforced in the browser and the metadata validator.
                # Every multi-select is required to declare a ceiling, so absence is a real defect.
                limit = setting.get("max_selected")
                if isinstance(limit, bool) or not isinstance(limit, int):
                    adjustments.append(f"{key}: no selection ceiling is declared for this setting")
                elif len(picked) > limit:
                    adjustments.append(f"{key}: only {limit} selections are allowed")
                    picked = picked[:limit]
                clean[key] = picked
            elif isinstance(value, str) and value in choices:
                clean[key] = value
            else:
                adjustments.append(f"{key}: {value!r} is not an option, kept the default")
                clean[key] = default

        else:
            if isinstance(value, str):
                clean[key] = value.strip()
            else:
                adjustments.append(f"{key}: expected text, kept the default")
                clean[key] = default

    for key, setting in known.items():
        clean.setdefault(key, normalized_default(setting))
    return clean, adjustments, rejected


def engine_preflight(plan: dict) -> list[str]:
    """Mirror the native RunExecutionContract rules that can be decided before Start.

    The browser is allowed to save only plans the native adapter can represent exactly. Gated
    selections require the same explicit diagnostic acknowledgement that native Start rechecks;
    known no-op or unsupported values fail here instead of being advertised as an applied plan.
    """
    problems: list[str] = []
    settings = settings_index()

    for setting_id, setting in settings.items():
        if setting.get("type") != "select":
            continue
        selected = plan.get(setting_id)
        option = next((item for item in setting.get("options", []) if item.get("value") == selected), None)
        if option and option.get("availability") in {"planned", "unsupported"}:
            problems.append(f"{setting_id}: {option.get('label', selected)} is not implemented by the native engine")
        elif option and option.get("availability") == "gated" and not bool(plan.get("run.diagnostic_mode")):
            problems.append(
                f"{setting_id}: {option.get('label', selected)} needs Allow unverified and a supervised "
                "diagnostic acknowledgement"
            )

    surface = str(plan.get("run.surface", "")).strip().lower()
    strategy = str(plan.get("run.strategy", "")).strip().lower()
    script = str(plan.get("run.attack_script", "")).strip()
    planned_town_hall = int(plan.get("run.town_hall", 0))
    home_maintenance = strategy == "home.collectors"
    clan_request_only = strategy == "home.clan-request"
    if surface != "regular":
        problems.append("run.surface: the native engine is currently wired only to Regular Battles")
    if strategy not in {"legacy.csv", "legacy.standard", "smart.local", "home.collectors", "home.clan-request"}:
        problems.append(f"run.strategy: {strategy or 'blank'} has no native execution adapter")
    if strategy != "legacy.csv" and script.lower() != "profile-current":
        problems.append("run.attack_script: a named CSV requires the Scripted strategy")

    if str(plan.get("army.source", "")).strip().lower() != "recipe" or str(plan.get("army.recipe_name", "")).strip():
        problems.append("army: named recipes and non-profile army sources are not wired; use the active profile army")

    manages_training = bool(plan.get("army.manage_training"))
    if home_maintenance:
        if not bool(plan.get("run.diagnostic_mode")):
            problems.append("run.diagnostic_mode: Home maintenance requires supervised diagnostic acknowledgement")
        collectors = bool(plan.get("events.collect_resources"))
        daily_reward = bool(plan.get("events.collect_daily_reward"))
        loot_cart = bool(plan.get("events.collect_loot_cart"))
        treasury = bool(plan.get("events.collect_treasury"))
        selected_home_tasks = sum(bool(value) for value in (collectors, daily_reward, loot_cart, treasury))
        if treasury or selected_home_tasks != 1:
            problems.append(
                "events: choose exactly one available template-free task: collectors, Loot Cart, or startup Daily Reward; "
                "Treasury remains unavailable"
            )
        if manages_training or bool(plan.get("army.wait_for_full")) or bool(plan.get("army.train_spells")) or bool(plan.get("army.train_sieges")):
            problems.append("army: Home maintenance requires training, army wait, spells, and sieges off")
        if plan.get("run.heroes"):
            problems.append("run.heroes: Home maintenance requires no selected Heroes")
        if int(plan.get("run.duration_minutes", 0)) != 0 or int(plan.get("run.max_battles", 0)) != 0 or bool(plan.get("run.stop_on_star_bonus")) or int(plan.get("run.max_failures", 0)) != 0:
            problems.append("run: Home maintenance is one pass; duration, battles, star bonus, and failure limits must be 0/off")
        if any(int(plan.get(key, 0)) != 0 for key in ("target.gold", "target.elixir", "target.dark_elixir", "search.min_gold", "search.min_elixir", "search.min_dark", "search.max_seconds")):
            problems.append("search/targets: Home maintenance cannot configure matchmaking or battle-loot targets")
        if str(plan.get("donate.mode", "")).strip().lower() != "off" or bool(plan.get("donate.request_when_short")) or int(plan.get("donate.max_per_run", 0)) != 0:
            problems.append("donate: Home maintenance requires donations and requests off")
        if bool(plan.get("events.clan_games")) or int(plan.get("events.clan_games_point_cap", 0)) != 0:
            problems.append("events.clan_games: Home maintenance cannot enter Clan Games")
        if str(plan.get("events.laboratory", "")).strip().lower() != "off":
            problems.append("events.laboratory: Home maintenance requires Laboratory off")
        if str(plan.get("upgrade.policy", "")).strip().lower() != "disabled":
            problems.append("upgrade.policy: Home maintenance requires upgrades disabled")
        if str(plan.get("account.queue", "")).strip():
            problems.append("account.queue: Home maintenance cannot rotate accounts")
    elif clan_request_only:
        if not bool(plan.get("run.diagnostic_mode")):
            problems.append("run.diagnostic_mode: Clan request requires supervised diagnostic acknowledgement")
        if manages_training or bool(plan.get("army.wait_for_full")) or bool(plan.get("army.train_spells")) or bool(plan.get("army.train_sieges")):
            problems.append("army: Clan request requires training, army wait, spells, and sieges off")
        if plan.get("run.heroes"):
            problems.append("run.heroes: Clan request requires no selected Heroes")
        if int(plan.get("run.duration_minutes", 0)) != 0 or int(plan.get("run.max_battles", 0)) != 0 or bool(plan.get("run.stop_on_star_bonus")) or int(plan.get("run.max_failures", 0)) != 0:
            problems.append("run: Clan request is one pass; duration, battles, star bonus, and failure limits must be 0/off")
        if any(int(plan.get(key, 0)) != 0 for key in ("target.gold", "target.elixir", "target.dark_elixir", "search.min_gold", "search.min_elixir", "search.min_dark", "search.max_seconds")):
            problems.append("search/targets: Clan request cannot configure matchmaking or battle-loot targets")
        if str(plan.get("donate.mode", "")).strip().lower() != "off" or not bool(plan.get("donate.request_when_short")) or not bool(plan.get("donate.keep_army")) or int(plan.get("donate.max_per_run", 0)) != 0:
            problems.append("donate: Clan request requires Off, Request when available on, army preservation on, and donation limit 0")
        if bool(plan.get("events.collect_resources")) or bool(plan.get("events.collect_daily_reward")) or bool(plan.get("events.collect_loot_cart")) or bool(plan.get("events.collect_treasury")) or bool(plan.get("events.clan_games")) or int(plan.get("events.clan_games_point_cap", 0)) != 0:
            problems.append("events: Clan request cannot collect resources, claim rewards, or enter Clan Games")
        if str(plan.get("events.laboratory", "")).strip().lower() != "off":
            problems.append("events.laboratory: Clan request requires Laboratory off")
        if str(plan.get("upgrade.policy", "")).strip().lower() != "disabled":
            problems.append("upgrade.policy: Clan request requires upgrades disabled")
        if str(plan.get("account.queue", "")).strip():
            problems.append("account.queue: Clan request cannot rotate accounts")
        if int(plan.get("pacing.break_every_minutes", 0)) != 0:
            problems.append("pacing.break_every_minutes: Clan request requires scheduled breaks off")
    elif bool(plan.get("events.collect_resources")) or bool(plan.get("events.collect_daily_reward")) or bool(plan.get("events.collect_loot_cart")) or bool(plan.get("events.collect_treasury")):
        problems.append("events: Home collection work requires the Home maintenance strategy")
    elif manages_training:
        problems.append(
            "army.manage_training: managed training is disabled because the inherited profile training path is not "
            "closed-world; turn it off and use the current trained army for one battle"
        )
    else:
        if int(plan.get("run.max_battles", 0)) != 1:
            problems.append("run.max_battles: current trained army mode requires exactly one battle")
        if not bool(plan.get("army.wait_for_full")):
            problems.append("army.wait_for_full: current trained army mode requires a fresh full-army check")
        if str(plan.get("donate.mode", "")).strip().lower() != "off":
            problems.append("donate.mode: donations must be off for the one-shot current army")
        if bool(plan.get("donate.request_when_short")):
            problems.append("donate.request_when_short: current-army mode cannot request troops")
        if bool(plan.get("events.clan_games")) or bool(plan.get("events.collect_resources")) or bool(plan.get("events.collect_daily_reward")) or bool(plan.get("events.collect_loot_cart")) or bool(plan.get("events.collect_treasury")):
            problems.append("events: current-army mode cannot run Clan Games or Home collection work before battle")
        if str(plan.get("events.laboratory", "")).strip().lower() != "off":
            problems.append("events.laboratory: current-army mode requires Laboratory off")
        if str(plan.get("upgrade.policy", "")).strip().lower() != "disabled":
            problems.append("upgrade.policy: current-army mode requires upgrades disabled")

    if int(plan.get("pacing.retry_attempts", 0)) != 0:
        problems.append("pacing.retry_attempts: visual-change retries are not wired; use 0")
    if int(plan.get("search.max_seconds", 0)) != 0:
        problems.append("search.max_seconds: bounded search exit is not wired; use 0")
    if str(plan.get("search.town_hall_filter", "")).strip().lower() != "any":
        problems.append("search.town_hall_filter: only Any Town Hall is wired")
    hero_setting = settings.get("run.heroes", {})
    hero_options = {item.get("value"): item for item in hero_setting.get("options", [])}
    selected_heroes = plan.get("run.heroes", [])
    if len(selected_heroes) > int(hero_setting.get("max_selected", 0)):
        problems.append("run.heroes: the native deployment actuator has only four active Hero slots")
    for hero_id in selected_heroes:
        option = hero_options.get(hero_id, {})
        if not option.get("active_slot_eligible", False) or hero_id == "dragon-duke":
            problems.append(f"run.heroes: {option.get('label', hero_id)} is not present in the inherited deployment actuator")
            continue
        unlock = int(option.get("unlock_town_hall", 0))
        if planned_town_hall > 0 and unlock > planned_town_hall:
            problems.append(
                f"run.heroes: {option.get('label', hero_id)} unlocks at Town Hall {unlock}, "
                f"after planned Town Hall {planned_town_hall}"
            )

    emulator = str(plan.get("runtime.emulator", "")).strip().lower()
    instance = str(plan.get("runtime.instance", "")).strip()
    if emulator == "auto" and instance:
        problems.append("runtime.instance: choose a specific emulator before selecting an instance")
    if emulator == "bluestacks5" and not instance:
        problems.append("runtime.instance: choose the exact BlueStacks 5 instance")
    if (home_maintenance or clan_request_only) and (emulator == "auto" or not instance):
        route_label = "Home maintenance" if home_maintenance else "Clan request"
        problems.append(f"runtime.instance: {route_label} requires the exact non-Auto emulator and instance")
    if (home_maintenance or clan_request_only) and instance and not re.fullmatch(r"[A-Za-z0-9_. -]{1,64}", instance):
        problems.append("runtime.instance: the Home route instance name contains unsupported characters")

    if not bool(plan.get("donate.keep_army")):
        problems.append("donate.keep_army: the native planner requires attack-army protection")
    if int(plan.get("donate.max_per_run", 0)) != 0:
        problems.append("donate.max_per_run: per-run donation limits are not wired; use 0")
    if int(plan.get("events.clan_games_point_cap", 0)) != 0:
        problems.append("events.clan_games_point_cap: the point cap is not wired; use 0")
    if str(plan.get("events.laboratory", "")).strip().lower() != "off":
        problems.append("events.laboratory: planner-driven research is not wired; use Off")
    if str(plan.get("upgrade.policy", "")).strip().lower() not in {"disabled", "walls"}:
        problems.append("upgrade.policy: only Disabled or Walls has a native adapter")
    if str(plan.get("account.queue", "")).strip():
        problems.append("account.queue: planner account rotation is not wired")
    if str(plan.get("notify.channel", "")).strip().lower() != "log-only":
        problems.append("notify.channel: only Bot log notifications are wired")

    return list(dict.fromkeys(problems))


def read_plan() -> dict:
    raw = read_json(PLAN_PATH, default_plan())
    if not isinstance(raw, dict):
        return default_plan()
    return validate_plan(raw)[0]


def write_plan_atomic(plan: dict, path: Path | None = None) -> None:
    """Write through a unique same-directory file, flush it, then replace the destination."""
    destination = path or PLAN_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(plan, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def write_json_atomic(document: dict, destination: Path) -> None:
    """Use the same crash-safe write contract for commands and planner documents."""
    write_plan_atomic(document, destination)


def plan_status() -> dict:
    """Report what is on disk.

    A file that exists but cannot be parsed is reported as "unreadable", not "saved". The AutoIt
    loader is strict and would refuse such a file, and a status that disagrees with the reader is
    worse than no status at all.
    """
    if not PLAN_PATH.exists():
        return {"exists": False, "state": "defaults", "written_at": None}
    try:
        written = datetime.fromtimestamp(PLAN_PATH.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        written = None
    parsed = read_json(PLAN_PATH, None)
    if not isinstance(parsed, dict):
        return {"exists": True, "state": "unreadable", "written_at": written}
    return {"exists": True, "state": "saved", "written_at": written}


def displayed_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def tail_events(limit: int = 200) -> list[dict]:
    """Read a bounded tail and ignore malformed lines without losing the complete feed."""
    if not EVENTS_PATH.exists():
        return []
    try:
        with EVENTS_PATH.open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - MAX_TAIL_BYTES))
            blob = stream.read()
        if size > MAX_TAIL_BYTES:
            blob = blob.split(b"\n", 1)[-1]
        lines = blob.decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []

    events: list[dict] = []
    for line in lines[-limit:]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def control_status() -> dict:
    """Return native state plus an explicit freshness verdict.

    The native process owns the status file and refreshes it once per second. A syntactically valid
    but old file must never make the browser claim that a dead engine is online.
    """
    engine_init_cancellable = engine_init_cancel_context() is not None
    offline = {
        "connected": False,
        "authorization_ready": False,
        "engine_available": False,
        "emulator_attached": False,
        "window_attached": False,
        "adb_ready": False,
        "game_ready": False,
        "state": "offline",
        "message": "Native engine is not connected",
        "last_seen_at": None,
        "age_seconds": None,
        "engine_init_cancellable": engine_init_cancellable,
    }
    modified = None
    document = None
    for attempt in range(CONTROL_STATUS_READ_ATTEMPTS):
        try:
            modified = CONTROL_STATUS_PATH.stat().st_mtime
            document = read_json(CONTROL_STATUS_PATH, None)
            if isinstance(document, dict):
                break
        except OSError:
            modified = None
            document = None
        # FileMove on Windows can expose a short remove/replace window. Retry the complete
        # existence/stat/read sequence so that gap never masquerades as a dead native engine.
        if attempt + 1 < CONTROL_STATUS_READ_ATTEMPTS:
            time.sleep(CONTROL_STATUS_READ_RETRY_SECONDS)
    if modified is None:
        return offline
    if not isinstance(document, dict):
        return {**offline, "state": "error", "message": "Native status file is unreadable"}

    age = max(0.0, datetime.now(timezone.utc).timestamp() - modified)
    document = dict(document)
    document["last_seen_at"] = datetime.fromtimestamp(modified, timezone.utc).isoformat()
    document["age_seconds"] = round(age, 2)
    max_age = CONTROL_STATUS_BUSY_MAX_AGE_SECONDS if document.get("state") in CONTROL_BUSY_STATES else CONTROL_STATUS_MAX_AGE_SECONDS
    document["connected"] = age <= max_age
    if not document["connected"]:
        document["state"] = "offline"
        document["message"] = "Native engine heartbeat is stale"
    native_attached = (
        document.get("window_attached") is True
        if "window_attached" in document
        else document.get("emulator_attached") is True
    )
    window_attached = bool(document["connected"] and native_attached)
    document["window_attached"] = window_attached
    document["emulator_attached"] = window_attached
    document["adb_ready"] = bool(window_attached and document.get("adb_ready") is True)
    document["game_ready"] = bool(document["adb_ready"] and document.get("game_ready") is True)
    document["engine_init_cancellable"] = engine_init_cancellable
    return document


def queue_control_command(action: str, expected_start_request_id: str = "") -> tuple[dict, int]:
    if action not in CONTROL_ACTIONS:
        return {"ok": False, "problems": ["unsupported control action"]}, 400
    if expected_start_request_id:
        if action != "stop" or re.fullmatch(r"[A-Za-z0-9._-]{1,80}", expected_start_request_id) is None:
            return {"ok": False, "problems": ["expected_start_request_id is invalid for this action"]}, 400
    status = control_status()
    init_context = engine_init_cancel_context() if action == "stop" else None
    expected_init_request_id = expected_start_request_id
    if (
        action == "stop"
        and init_context is None
        and not expected_init_request_id
        and status.get("last_command") in {"start", "check-engine"}
        and status.get("last_outcome") == "accepted"
        and isinstance(status.get("last_command_id"), str)
        and re.fullmatch(r"[A-Za-z0-9._-]{1,80}", status["last_command_id"])
    ):
        expected_init_request_id = status["last_command_id"]
    if not status.get("connected") and init_context is None and not expected_init_request_id:
        return {"ok": False, "problems": ["native engine is offline"], "status": status}, 409
    if action in {"start", "check-engine"} and not status.get("engine_available", True):
        return {"ok": False, "problems": [status.get("message") or "native engine is unavailable"], "status": status}, 409

    with CONTROL_LOCK:
        command_pending = CONTROL_COMMAND_PATH.exists()
        # Stop has priority over an unconsumed Start or engine check. Replacing that pending file is
        # safe even before the backend publishes an initialization receipt; no managed call has
        # started yet. Once a receipt exists, the separate launcher cancel remains authoritative.
        if command_pending and action != "stop":
            return {"ok": False, "problems": ["another control command is awaiting the native engine"]}, 409
        request_id = uuid.uuid4().hex
        command = {
            "schema_version": 1,
            "request_id": request_id,
            "action": action,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }
        native_command_queued = False
        # A supervised Stop must replace any command that could otherwise be replayed by the
        # controller's replacement backend after the launcher closes the blocked generation.
        # The launcher cancel remains a separate exact-owner path when this native write fails.
        if not command_pending or action == "stop":
            try:
                write_json_atomic(command, CONTROL_COMMAND_PATH)
                native_command_queued = True
            except OSError:
                if action != "stop" or init_context is None:
                    return {"ok": False, "problems": ["the control command could not be queued atomically"]}, 500

        # The synchronous first managed-engine call blocks the AutoIt message loop. Mirror Stop
        # through the launcher's separately owned channel. A failure here must not turn an already
        # durable native Stop into a false HTTP 500; report the two delivery paths independently.
        if action == "stop" and init_context is None and expected_init_request_id:
            init_context = wait_for_engine_init_cancel_context(expected_init_request_id)

        supervisor_cancel_status = "not-active"
        if action == "stop" and init_context is not None:
            try:
                write_json_atomic(
                    {
                        "schema": "engine-init-cancel-v1",
                        "token": init_context["token"],
                        "expected_start_request_id": init_context["start_request_id"],
                        "stop_request_id": request_id,
                        "requested_at": command["requested_at"],
                    },
                    ENGINE_INIT_CANCEL_PATH,
                )
                supervisor_cancel_status = "queued"
            except OSError:
                supervisor_cancel_status = "unavailable"
                if not native_command_queued:
                    return {"ok": False, "problems": ["the supervisor Stop could not be queued atomically"]}, 500
    return {
        "ok": True,
        "accepted": True,
        "request_id": request_id,
        "action": action,
        "native_command_queued": native_command_queued,
        "supervisor_cancel_status": supervisor_cancel_status,
        "written": displayed_path(CONTROL_COMMAND_PATH) if native_command_queued else None,
    }, 202


def health_payload() -> dict:
    metadata = metadata_document()
    settings = [setting for section in metadata.get("sections", []) for setting in section.get("settings", [])]
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "bridge": BRIDGE_PROTOCOL,
        "protocol": HEALTH_PROTOCOL,
        "repo_root": SERVICE_REPO_ROOT,
        "profiles_root": str(PROFILES_ROOT.resolve()),
        "profiles_root_token": base64.urlsafe_b64encode(
            str(PROFILES_ROOT.resolve()).encode("utf-8")
        ).decode("ascii").rstrip("="),
        "build_sha256": SERVICE_BUILD_SHA256,
        "service_pid": os.getpid(),
        # Never publish the launch capability itself. Native ownership recovery reads the raw,
        # unguessable token from its atomic local receipt and compares this digest. Loopback health
        # is deliberately treated as public and spoofable.
        "owner_token": hashlib.sha256(SERVICE_OWNER_TOKEN.encode("ascii")).hexdigest(),
        "owner_token_kind": "sha256",
        "sections": len(metadata.get("sections", [])),
        "settings": len(settings),
        "plan": plan_status(),
        "engine": control_status(),
    }


def native_log_path(profile: str) -> Path | None:
    """Return only the latest normal bot log for the active, path-safe profile."""
    if not isinstance(profile, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}", profile):
        return None
    if profile in {".", ".."}:
        return None
    root = PROFILES_ROOT.resolve()
    log_dir = (PROFILES_ROOT / profile / "Logs").resolve()
    try:
        log_dir.relative_to(root)
    except ValueError:
        return None
    try:
        candidates = []
        for path in log_dir.iterdir():
            if not path.is_file() or not re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{2}\.\d{2}\.\d{2}\.log", path.name):
                continue
            try:
                candidates.append((path.stat().st_mtime_ns, path))
            except OSError:
                continue
    except OSError:
        return None
    return max(candidates, default=(0, None))[1]


def read_native_log_tail(path: Path) -> tuple[str, bool]:
    """Read a bounded text tail without returning a partial first line or control characters."""
    try:
        size = path.stat().st_size
        with path.open("rb") as stream:
            start = max(0, size - MAX_TAIL_BYTES)
            stream.seek(start)
            raw = stream.read(MAX_TAIL_BYTES)
    except OSError:
        return "", False
    text = raw.decode("utf-8-sig", errors="replace")
    if start:
        split = text.split("\n", 1)
        text = split[1] if len(split) == 2 else ""
    all_lines = text.splitlines()
    lines = all_lines[-MAX_NATIVE_LOG_LINES:]
    clean = "\n".join("".join(char for char in line if char == "\t" or ord(char) >= 32) for line in lines)
    return clean, start > 0 or len(all_lines) > MAX_NATIVE_LOG_LINES


def native_log_payload() -> dict:
    status = control_status()
    profile = status.get("profile", "")
    path = native_log_path(profile)
    if path is None:
        return {
            "available": False,
            "profile": profile if isinstance(profile, str) else "",
            "path": None,
            "modified_at": None,
            "size_bytes": 0,
            "truncated": False,
            "text": "",
            "message": "No native log is available for the active profile yet.",
        }
    text, truncated = read_native_log_tail(path)
    try:
        stat = path.stat()
    except OSError:
        return {
            "available": False, "profile": profile, "path": None, "modified_at": None,
            "size_bytes": 0, "truncated": False, "text": "", "message": "The native log could not be read.",
        }
    return {
        "available": True,
        "profile": profile,
        "path": displayed_path(path),
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "size_bytes": stat.st_size,
        "truncated": truncated,
        "text": text,
        "message": "Showing the newest bounded log tail from this local profile.",
    }


def redact_diagnostic_text(value, limit: int = 800):
    """Keep useful operator text while removing common credential and user-path shapes."""
    if not isinstance(value, str):
        return value
    text = value[:limit]
    text = re.sub(r"(?i)\b(bearer)\s+\S+", r"\1 [redacted]", text)
    text = re.sub(
        r"(?i)\b(password|passwd|token|secret|api[_-]?key|authorization)\b\s*[:=]\s*[^\s,;]+",
        r"\1=[redacted]",
        text,
    )
    text = re.sub(r"(?i)\bC:\\Users\\[^\\\s]+", lambda _: r"C:\Users\[user]", text)
    return text


def diagnostic_artifact(path: Path) -> dict:
    result = {"path": displayed_path(path), "exists": False, "size_bytes": None, "sha256": None}
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        result.update(exists=True, size_bytes=path.stat().st_size, sha256=digest.hexdigest())
    except OSError:
        pass
    return result


def diagnostics_payload() -> dict:
    """Build a bounded, allowlisted support bundle without collecting secrets or game data."""
    metadata = metadata_document()
    known_settings = set(settings_index())
    raw_plan = read_json(PLAN_PATH, None) if PLAN_PATH.exists() else None
    plan_validation = {
        "readable": isinstance(raw_plan, dict),
        "exact_setting_set": False,
        "adjustment_count": 0,
        "rejected_setting_count": 0,
        "engine_preflight_count": 0,
        "valid": False,
    }
    if isinstance(raw_plan, dict):
        normalized, adjustments, rejected = validate_plan(raw_plan)
        preflight = engine_preflight(normalized)
        exact = set(raw_plan) == known_settings
        plan_validation.update(
            exact_setting_set=exact,
            adjustment_count=len(adjustments),
            rejected_setting_count=len(rejected),
            engine_preflight_count=len(preflight),
            valid=exact and not adjustments and not rejected and not preflight,
        )

    engine = {
        key: redact_diagnostic_text(value)
        for key, value in control_status().items()
        if key in DIAGNOSTIC_ENGINE_FIELDS
    }
    events = []
    for event in tail_events(50):
        events.append({
            key: redact_diagnostic_text(value)
            for key, value in event.items()
            if key in DIAGNOSTIC_EVENT_FIELDS
        })

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "privacy": "Allowlisted operational state only; no credentials, plan values, screenshots, or game data.",
        "service": SERVICE_NAME,
        "bridge": BRIDGE_PROTOCOL,
        "planner": {
            "title": metadata.get("title", "Run Planner"),
            "section_count": len(metadata.get("sections", [])),
            "setting_count": len(known_settings),
            "plan": plan_status(),
            "saved_plan_validation": plan_validation,
        },
        "engine": engine,
        "recent_events": events,
        "artifacts": {name: diagnostic_artifact(path) for name, path in DIAGNOSTIC_ARTIFACTS.items()},
        "host_diagnostics": {
            "collected": False,
            "note": "Windows Security and system event logs are not queried by the Control Center.",
        },
    }


def local_request_allowed(handler: BaseHTTPRequestHandler) -> bool:
    try:
        host = urlsplit("//" + handler.headers.get("Host", "")).hostname
        port = urlsplit("//" + handler.headers.get("Host", "")).port
    except ValueError:
        return False
    expected_port = handler.server.server_address[1]
    if host not in LOCAL_HOSTS or port not in (None, expected_port):
        return False

    origin = handler.headers.get("Origin")
    if not origin:
        return True
    try:
        parsed = urlsplit(origin)
        return parsed.scheme == "http" and parsed.hostname in LOCAL_HOSTS and parsed.port == expected_port
    except ValueError:
        return False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code: int, body: bytes, content_type: str, extra_headers: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, code: int = 200):
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def _allow_local(self) -> bool:
        if local_request_allowed(self):
            return True
        self._json({"ok": False, "problems": ["request origin is not this local planner"]}, 403)
        return False

    def do_GET(self):
        if not self._allow_local():
            return
        assets = {
            "/": (UI_HTML, "text/html; charset=utf-8"),
            "/index.html": (UI_HTML, "text/html; charset=utf-8"),
            "/planner.css": (UI_CSS, "text/css; charset=utf-8"),
            "/planner.js": (UI_JS, "text/javascript; charset=utf-8"),
            "/favicon.svg": (UI_FAVICON, "image/svg+xml"),
        }
        if self.path in assets:
            path, content_type = assets[self.path]
            if not path.exists():
                self._send(500, f"{path.relative_to(ROOT)} is missing".encode(), "text/plain; charset=utf-8")
                return
            self._send(200, path.read_bytes(), content_type)
        elif self.path == "/api/health":
            self._json(health_payload())
        elif self.path == "/api/metadata":
            self._json({"metadata": metadata_document(), "capabilities": read_json(CAPABILITIES, {})})
        elif self.path == "/api/plan":
            self._json(read_plan())
        elif self.path == "/api/events":
            self._json({"events": tail_events()})
        elif self.path == "/api/log":
            self._json(native_log_payload())
        elif self.path == "/api/log/download":
            payload = native_log_payload()
            if not payload["available"]:
                self._send(404, payload["message"].encode("utf-8"), "text/plain; charset=utf-8")
                return
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            body = (payload["text"] + "\n").encode("utf-8")
            self._send(200, body, "text/plain; charset=utf-8", {
                "Content-Disposition": f'attachment; filename="my-bot-native-log-{stamp}.txt"'
            })
        elif self.path == "/api/control/status":
            self._json(control_status())
        elif self.path == "/api/diagnostics":
            body = json.dumps(diagnostics_payload(), indent=2).encode("utf-8")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            self._send(200, body, "application/json; charset=utf-8", {
                "Content-Disposition": f'attachment; filename="my-bot-diagnostics-{stamp}.json"'
            })
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if not self._allow_local():
            return
        if self.path not in {"/api/plan", "/api/control/command"}:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        if self.headers.get_content_type() != "application/json":
            self._json({"ok": False, "problems": ["Content-Type must be application/json"]}, 415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json({"ok": False, "problems": ["Content-Length was not a number"]}, 400)
            return
        if length < 0 or length > MAX_REQUEST_BYTES:
            self._json({"ok": False, "problems": [f"request body exceeds {MAX_REQUEST_BYTES} bytes"]}, 413)
            return
        try:
            submitted = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self._json({"ok": False, "problems": ["request was not valid JSON"]}, 400)
            return
        if not isinstance(submitted, dict):
            self._json({"ok": False, "problems": ["expected a JSON object"]}, 400)
            return

        if self.path == "/api/control/command":
            action = submitted.get("action")
            if not isinstance(action, str):
                self._json({"ok": False, "problems": ["action must be a string"]}, 400)
                return
            expected_start_request_id = submitted.get("expected_start_request_id", "")
            if not isinstance(expected_start_request_id, str):
                self._json({"ok": False, "problems": ["expected_start_request_id must be a string"]}, 400)
                return
            payload, code = queue_control_command(action.strip().lower(), expected_start_request_id)
            self._json(payload, code)
            return

        clean, adjustments, rejected = validate_plan(submitted)

        # An unknown setting means the caller and this server disagree about what exists. Saving the
        # rest would silently drop the caller's intent, so refuse the whole document and write nothing.
        if rejected:
            self._json({"ok": False, "problems": rejected, "written": None}, 400)
            return

        preflight = engine_preflight(clean)
        if preflight:
            self._json({"ok": False, "problems": preflight, "written": None, "plan": clean}, 422)
            return

        try:
            write_plan_atomic(clean)
        except OSError:
            self._json({"ok": False, "problems": ["the plan could not be written atomically"]}, 500)
            return
        self._json({
            "ok": True,
            "problems": adjustments,
            "written": displayed_path(PLAN_PATH),
            "plan": clean,
            "status": plan_status(),
        })


class PlannerServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def selftest() -> int:
    failures: list[str] = []

    def check(condition, message):
        print(f"  {'ok  ' if condition else 'FAIL'}  {message}")
        if not condition:
            failures.append(message)

    plan = default_plan()
    setting_ids = set(settings_index())
    check(set(plan) == setting_ids, "default plan covers every setting exactly")
    check(isinstance(plan["run.heroes"], list), "multi-select defaults use a stable list shape")
    check(plan.get("run.attack_script") == "profile-current", "the default preserves the active profile script")
    check(bool(engine_preflight(plan)), "the unacknowledged default plan is refused before diagnostic execution")
    diagnostic_plan = dict(plan)
    diagnostic_plan["run.diagnostic_mode"] = True
    diagnostic_plan["run.diagnostic_note"] = "selftest operator acknowledgement"
    check(not engine_preflight(diagnostic_plan), "the acknowledged default plan reaches the native execution contract")

    preset_contract = metadata_document().get("presets", {})
    presets = preset_contract.get("items", [])
    check([preset.get("town_hall") for preset in presets] == list(range(2, 19)), "Town Hall presets cover TH2 through TH18 in order")
    preserved = set(preset_contract.get("preserved_settings", []))
    check(
        preserved == {"runtime.emulator", "runtime.instance", "run.diagnostic_mode", "run.diagnostic_note"},
        "presets preserve machine selection and diagnostic acknowledgement",
    )
    for preset in presets:
        values = preset.get("values", {})
        preset_id = preset.get("id", "unknown")
        owned = setting_ids - preserved
        check(set(values) == owned, f"{preset_id} owns every non-preserved setting exactly")
        check("run.heroes" in values and isinstance(values["run.heroes"], list), f"{preset_id} carries an explicit Hero loadout")
        operator_values = {
            "runtime.emulator": "bluestacks5",
            "runtime.instance": "Pie64",
            "run.diagnostic_mode": True,
            "run.diagnostic_note": "operator acknowledgement",
        }
        loaded = dict(plan)
        loaded.update(operator_values)
        loaded.update(values)
        check(
            all(loaded[key] == values[key] for key in owned)
            and all(loaded[key] == value for key, value in operator_values.items()),
            f"{preset_id} replaces all preset fields while preserving operator-owned fields",
        )
        candidate = dict(plan)
        candidate["run.diagnostic_mode"] = True
        candidate["run.diagnostic_note"] = "selftest operator acknowledgement"
        candidate.update(values)
        clean_preset, adjusted_preset, rejected_preset = validate_plan(candidate)
        check(
            not adjusted_preset and not rejected_preset and clean_preset == candidate,
            f"{preset_id} is already normalized",
        )
        check(not engine_preflight(candidate), f"{preset_id} passes the native execution preflight")
        check(not (set(values) & preserved), f"{preset_id} does not overwrite preserved settings")

    clean, adjustments, rejected = validate_plan({"run.max_failures": 9999})
    check(clean["run.max_failures"] == 100 and any("clamped" in item for item in adjustments), "integer maximum is enforced")
    clean, adjustments, rejected = validate_plan({"run.diagnostic_mode": "false"})
    check(clean["run.diagnostic_mode"] is False and not adjustments, "the string 'false' reads as off")
    clean, adjustments, rejected = validate_plan({"run.diagnostic_mode": "0"})
    check(clean["run.diagnostic_mode"] is False and not adjustments, "the string '0' reads as off")
    for ambiguous in (0, None, [], {}):
        clean, adjustments, rejected = validate_plan({"run.diagnostic_mode": ambiguous})
        check(clean["run.diagnostic_mode"] is False and bool(adjustments), f"ambiguous boolean {ambiguous!r} is rejected")
    clean, adjustments, rejected = validate_plan({"run.heroes": ["barbarian-king", "archer-queen", "minion-prince", "grand-warden", "royal-champion"]})
    check(len(clean["run.heroes"]) == 4 and any("only 4" in item for item in adjustments), "Hero selection is capped at four")
    for setting_id, value in (
        ("run.surface", "builder"),
        ("run.strategy", "legacy.smart-farm"),
        ("search.max_seconds", 15),
        ("pacing.retry_attempts", 1),
        ("notify.channel", "telegram"),
    ):
        impossible = dict(plan)
        impossible[setting_id] = value
        check(bool(engine_preflight(impossible)), f"native preflight refuses unwired {setting_id}={value}")

    # Strict rejection: unknown settings are never silently dropped.
    clean, adjustments, rejected = validate_plan({"run.not_a_real_setting": 1})
    check(len(rejected) == 1 and "not a setting" in rejected[0], "an unknown setting is rejected, not ignored")
    clean, adjustments, rejected = validate_plan({"run.max_failures": 9999, "run.not_a_real_setting": 1})
    check(bool(rejected) and bool(adjustments), "rejections and adjustments are reported separately")

    # The pacing section arrives with the cloud metadata; prove its bounds are live.
    check("pacing.settle_ms" in setting_ids, "the pacing section is present in the metadata")
    clean, adjustments, rejected = validate_plan({"pacing.settle_ms": 999999})
    check(clean["pacing.settle_ms"] == 10000 and any("clamped" in item for item in adjustments), "pacing settle bound is enforced")

    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "plan.json"
        write_plan_atomic(plan, target)
        check(read_json(target, {}) == plan, "atomic writer produces the complete plan")
        target.write_text('{"sentinel": true}\n', encoding="utf-8")
        with mock.patch("os.replace", side_effect=OSError("interrupted")):
            try:
                write_plan_atomic(plan, target)
            except OSError:
                pass
        check(read_json(target, {}) == {"sentinel": True}, "interrupted replacement preserves the previous plan")
        check(not list(target.parent.glob(".*.tmp")), "failed writes leave no temporary plan behind")

    global PLAN_PATH, EVENTS_PATH, CONTROL_COMMAND_PATH, CONTROL_STATUS_PATH
    global ENGINE_INIT_RECEIPT_PATH, ENGINE_INIT_CANCEL_PATH, SERVICE_OWNER_TOKEN
    original_plan, original_events = PLAN_PATH, EVENTS_PATH
    original_control_command, original_control_status = CONTROL_COMMAND_PATH, CONTROL_STATUS_PATH
    original_engine_receipt, original_engine_cancel = ENGINE_INIT_RECEIPT_PATH, ENGINE_INIT_CANCEL_PATH
    original_service_owner_token = SERVICE_OWNER_TOKEN
    with tempfile.TemporaryDirectory() as folder:
        PLAN_PATH = Path(folder) / "plan.json"
        EVENTS_PATH = Path(folder) / "events.jsonl"
        CONTROL_COMMAND_PATH = Path(folder) / "control-command.json"
        CONTROL_STATUS_PATH = Path(folder) / "control-status.json"
        ENGINE_INIT_RECEIPT_PATH = Path(folder) / "engine-init-owner.json"
        ENGINE_INIT_CANCEL_PATH = Path(folder) / "engine-init-cancel.json"
        SERVICE_OWNER_TOKEN = "selftest-owner"
        EVENTS_PATH.write_text(
            json.dumps({
                "timestamp_ms": 1234,
                "type": "session.preparing",
                "severity": "info",
                "message": "ready",
                "surface_id": "regular",
                "verification_state": "verified",
                "account_profile_id": "must-not-export",
            }) + "\n",
            encoding="utf-8",
        )

        # A corrupt plan file must not be reported as saved, because AutoIt would refuse it.
        PLAN_PATH.write_text("{ this is not json", encoding="utf-8")
        check(plan_status()["state"] == "unreadable", "a corrupt plan file is reported as unreadable")
        PLAN_PATH.unlink()

        server = PlannerServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("GET", "/api/health")
            response = connection.getresponse()
            health = json.loads(response.read())
            check(response.status == 200 and health["bridge"] == BRIDGE_PROTOCOL, "health endpoint reports the native control bridge")
            check(health["protocol"] == HEALTH_PROTOCOL, "health endpoint reports the exact health protocol")
            check(health["repo_root"] == str(ROOT.resolve()), "health endpoint identifies this repository root")
            check(
                health["build_sha256"] == hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest(),
                "health endpoint identifies the loaded service build",
            )
            check(health["service_pid"] == os.getpid(), "health endpoint reports the serving process id")
            check(
                health["owner_token"] == hashlib.sha256(b"selftest-owner").hexdigest()
                and health["owner_token_kind"] == "sha256",
                "health endpoint carries only a digest of the launch ownership token",
            )

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("GET", "/api/health")
            headers = connection.getresponse().headers
            check(
                headers.get("Content-Security-Policy") is not None
                and headers.get("X-Content-Type-Options") == "nosniff"
                and headers.get("Cache-Control") == "no-store",
                "security and no-cache headers are present",
            )

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("GET", "/api/diagnostics")
            response = connection.getresponse()
            diagnostic = json.loads(response.read())
            check(response.status == 200 and diagnostic["schema_version"] == 1, "diagnostic bundle is available")
            check("attachment" in response.headers.get("Content-Disposition", ""), "diagnostic bundle downloads as a file")
            check("run.diagnostic_mode" not in json.dumps(diagnostic), "diagnostic bundle excludes plan values and setting ids")
            check(set(diagnostic["engine"]) <= DIAGNOSTIC_ENGINE_FIELDS, "diagnostic engine state is allowlisted")
            check(
                diagnostic["recent_events"] == [{
                    "timestamp_ms": 1234,
                    "type": "session.preparing",
                    "severity": "info",
                    "message": "ready",
                    "surface_id": "regular",
                    "verification_state": "verified",
                }],
                "diagnostic events preserve the native allowlisted field names only",
            )

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.putrequest("GET", "/api/health", skip_host=True)
            connection.putheader("Host", "example.invalid")
            connection.endheaders()
            check(connection.getresponse().status == 403, "non-local Host is refused")

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("POST", "/api/plan", body=b"{}", headers={
                "Content-Type": "application/json", "Origin": "https://example.invalid"
            })
            check(connection.getresponse().status == 403, "foreign Origin is refused")

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("POST", "/api/plan", body=b"{}", headers={"Content-Type": "text/plain"})
            check(connection.getresponse().status == 415, "a non-JSON Content-Type is refused")

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.putrequest("POST", "/api/plan")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(MAX_REQUEST_BYTES + 1))
            connection.endheaders()
            check(connection.getresponse().status == 413, "oversized plan is refused before reading")

            # Strict rejection over the wire: 400, and the file on disk is untouched.
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            body = json.dumps({"run.not_a_real_setting": 1}).encode()
            connection.request("POST", "/api/plan", body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            check(response.status == 400 and payload["ok"] is False, "an unknown setting is refused with 400")
            check(not PLAN_PATH.exists(), "a refused save writes nothing")

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            body = json.dumps({
                "run.diagnostic_mode": True,
                "run.diagnostic_note": "selftest operator acknowledgement",
            }).encode()
            connection.request("POST", "/api/plan", body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            check(response.status == 200 and payload["ok"] and set(payload["plan"]) == setting_ids, "valid partial plan is normalized and written")

            saved_before_refusal = PLAN_PATH.read_bytes()
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            body = json.dumps({"search.max_seconds": 15}).encode()
            connection.request("POST", "/api/plan", body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            check(response.status == 422 and payload["ok"] is False, "engine-incompatible plan is refused before save")
            check(PLAN_PATH.read_bytes() == saved_before_refusal, "engine preflight refusal preserves the previous plan")

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            body = json.dumps({"action": "start"}).encode()
            connection.request("POST", "/api/control/command", body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            check(response.status == 409 and payload["ok"] is False, "control command is refused while native engine is offline")

            write_json_atomic({"state": "idle", "message": "Managed engine probe timed out", "bot_pid": 123, "engine_available": False}, CONTROL_STATUS_PATH)
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("POST", "/api/control/command", body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            check(response.status == 409 and "timed out" in payload["problems"][0], "Start is refused when the native engine reports unavailable")

            write_json_atomic({"state": "idle", "message": "Native engine is ready", "bot_pid": 123, "engine_available": True, "authorization_ready": False}, CONTROL_STATUS_PATH)
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("POST", "/api/control/command", body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            check(response.status == 202 and payload["ok"], "retired authorization field does not gate Start")
            check(CONTROL_COMMAND_PATH.exists(), "compatibility-status Start is queued for the native engine")
            CONTROL_COMMAND_PATH.unlink(missing_ok=True)

            write_json_atomic({"state": "idle", "message": "Native engine is ready", "bot_pid": 123, "engine_available": True, "authorization_ready": True}, CONTROL_STATUS_PATH)
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("GET", "/api/control/status")
            response = connection.getresponse()
            payload = json.loads(response.read())
            check(response.status == 200 and payload["connected"] and payload["state"] == "idle", "fresh native heartbeat is reported online")

            write_json_atomic({"state": "starting", "message": "Preparing the run", "bot_pid": 123}, CONTROL_STATUS_PATH)
            stale_busy_time = datetime.now(timezone.utc).timestamp() - (CONTROL_STATUS_MAX_AGE_SECONDS + 2)
            os.utime(CONTROL_STATUS_PATH, (stale_busy_time, stale_busy_time))
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("GET", "/api/control/status")
            response = connection.getresponse()
            payload = json.loads(response.read())
            check(response.status == 200 and payload["connected"] and payload["state"] == "starting", "busy startup keeps a bounded heartbeat grace")

            write_json_atomic({"state": "idle", "message": "Native engine is ready", "bot_pid": 123}, CONTROL_STATUS_PATH)
            os.utime(CONTROL_STATUS_PATH, (stale_busy_time, stale_busy_time))
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("GET", "/api/control/status")
            response = connection.getresponse()
            payload = json.loads(response.read())
            check(response.status == 200 and not payload["connected"] and payload["state"] == "offline", "idle heartbeat still fails closed at the normal threshold")

            write_json_atomic({"state": "starting", "message": "Preparing the run", "bot_pid": 123}, CONTROL_STATUS_PATH)
            with mock.patch(f"{__name__}.read_json", side_effect=[None, {"state": "starting", "message": "Preparing the run", "bot_pid": 123}]) as status_read:
                payload = control_status()
            check(payload["connected"] and payload["state"] == "starting" and status_read.call_count == 2, "status replacement race is retried once")

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            body = json.dumps({"action": "start"}).encode()
            connection.request("POST", "/api/control/command", body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            check(response.status == 202 and payload["accepted"] and CONTROL_COMMAND_PATH.exists(), "valid control command is queued atomically")

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("POST", "/api/control/command", body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            check(response.status == 409, "a pending control command is never overwritten")

            queued = read_json(CONTROL_COMMAND_PATH, {})
            check(queued.get("action") == "start" and bool(queued.get("request_id")), "queued command carries action and request id")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
    PLAN_PATH, EVENTS_PATH = original_plan, original_events
    CONTROL_COMMAND_PATH, CONTROL_STATUS_PATH = original_control_command, original_control_status
    ENGINE_INIT_RECEIPT_PATH, ENGINE_INIT_CANCEL_PATH = original_engine_receipt, original_engine_cancel
    SERVICE_OWNER_TOKEN = original_service_owner_token

    print(f"\n{'selftest passed' if not failures else str(len(failures)) + ' check(s) failed'}")
    return 1 if failures else 0


def main() -> int:
    global PROFILES_ROOT, SERVICE_OWNER_TOKEN
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--owner-token", default="", help=argparse.SUPPRESS)
    parser.add_argument("--profiles-root", default="", help=argparse.SUPPRESS)
    parser.add_argument("--selftest", action="store_true", help="check the complete local server contract")
    args = parser.parse_args()

    if args.profiles_root:
        try:
            PROFILES_ROOT = validated_external_profiles_root(args.profiles_root)
        except ValueError as exc:
            print(f"invalid profiles root: {exc}")
            return 2

    if args.selftest:
        return selftest()
    owner_token = args.owner_token.strip()
    if len(owner_token) > 128 or not re.fullmatch(r"[A-Za-z0-9._-]*", owner_token):
        print("invalid owner token")
        return 2
    SERVICE_OWNER_TOKEN = owner_token
    if not METADATA.exists():
        print(f"missing {METADATA.relative_to(ROOT)}; run tools/generate_run_planner_settings.py first")
        return 2
    if not all(path.exists() for path in (UI_HTML, UI_CSS, UI_JS)):
        print("missing one or more planner UI files")
        return 2

    server = PlannerServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"My Bot 2.0 Control Center on {url}")
    print(f"  plan file   {PLAN_PATH.relative_to(ROOT)}")
    print(f"  event feed  {EVENTS_PATH.relative_to(ROOT)}")
    print(f"  profile root {PROFILES_ROOT}")
    print(f"  engine link {CONTROL_STATUS_PATH.relative_to(ROOT)}")
    print(f"  service pid {os.getpid()}")
    print(f"  build       {SERVICE_BUILD_SHA256[:16]}")
    print("  ctrl-c to stop")
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
