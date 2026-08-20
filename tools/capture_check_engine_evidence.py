#!/usr/bin/env python3
"""Capture one redacted, no-emulator managed-engine initialization receipt.

The command is deliberately inert unless ``--execute`` is supplied.  Its
preflight proves that the loopback service belongs to the exact installed
launcher/controller/backend chain, the reviewed package manifest matches every
installed immutable file, no emulator or ADB process is present, and native
state is fresh idle/not-run.  The live path queues exactly one ``check-engine``
command, never retries it, and writes only redacted evidence drafts.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import http.client
import json
import os
import platform
import re
import stat
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable


PHASES = [
    "prepared",
    "pool-entered",
    "pool-returned",
    "max-entered",
    "max-returned",
    "android-entered",
    "android-returned",
    "gui-entered",
    "initialized",
]
HEX64 = re.compile(r"[0-9a-f]{64}")
HEX16 = re.compile(r"[0-9a-f]{16}")
REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,80}")
BROWSER_IMAGES = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"}
EMULATOR_IMAGES = {"hd-player.exe"}
ADB_IMAGES = {"hd-adb.exe", "adb.exe"}
MAX_RECEIPT_BYTES = 4096
EXPECTED_INITIAL = {
    "connected": True,
    "state": "idle",
    "run_state": False,
    "plan_active": False,
    "engine_available": True,
    "engine_probe_state": "not-run",
    "emulator_attached": False,
    "window_attached": False,
    "adb_ready": False,
    "game_ready": False,
}
EXPECTED_FINAL = {
    "connected": True,
    "state": "idle",
    "run_state": False,
    "plan_active": False,
    "engine_available": True,
    "engine_probe_state": "passed",
    "last_command": "check-engine",
    "last_outcome": "passed",
    "emulator_attached": False,
    "window_attached": False,
    "adb_ready": False,
    "game_ready": False,
}


class CaptureError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    parent_pid: int
    created: str
    image: str


@dataclass
class CaptureConfig:
    install_root: Path
    profiles_root: Path
    package_zip: Path
    output_directory: Path | None
    host: str
    port: int
    emulator_version: str
    game_version: str
    instance_name: str
    instance_index: int
    reviewer_name: str
    execute: bool
    timeout_seconds: float


@dataclass
class Preflight:
    manifest: dict[str, Any]
    manifest_bytes: bytes
    manifest_sha256: str
    package_sha256: str
    package_bytes: int
    binary: dict[str, Any]
    autoit_version: str
    health: dict[str, Any]
    status: dict[str, Any]
    processes: dict[int, ProcessIdentity]
    launcher: ProcessIdentity
    controller: ProcessIdentity
    backend: ProcessIdentity
    service: ProcessIdentity
    profile_sha256: str
    english_sha256: str
    plan_sha256: str | None
    event_offset: int
    launcher_log_offset: int
    manifest_integrity: dict[str, int]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(path: Path, *, directory: bool = False) -> Path:
    resolved = path.resolve(strict=True)
    if directory and not resolved.is_dir():
        raise CaptureError(f"expected directory: {path}")
    if not directory and not resolved.is_file():
        raise CaptureError(f"expected file: {path}")
    return resolved


def same_path(left: str | Path, right: str | Path) -> bool:
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(os.path.abspath(str(right)))


def assert_no_reparse_path(root: Path, path: Path) -> None:
    """Reject a manifest path whose root or any descendant component is redirected."""
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    current = root
    try:
        if getattr(current.lstat(), "st_file_attributes", 0) & reparse:
            raise CaptureError(f"immutable install root is a reparse point: {root}")
        relative = path.relative_to(root)
        for part in relative.parts:
            current = current / part
            metadata = current.lstat()
            if current.is_symlink() or getattr(metadata, "st_file_attributes", 0) & reparse:
                raise CaptureError(f"immutable manifest path crosses a reparse point: {relative.as_posix()}")
    except OSError as exc:
        raise CaptureError(f"immutable manifest path could not be inspected: {path}") from exc


def json_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CaptureError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CaptureError(f"JSON root is not an object: {path}")
    return value


def api_json(config: CaptureConfig, method: str, path: str, body: dict | None = None) -> tuple[int, dict[str, Any]]:
    payload = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    connection = http.client.HTTPConnection(config.host, config.port, timeout=2.0)
    try:
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        raw = response.read(256 * 1024 + 1)
    except OSError as exc:
        raise CaptureError(f"loopback request failed: {method} {path}: {exc}") from exc
    finally:
        connection.close()
    if len(raw) > 256 * 1024:
        raise CaptureError(f"loopback response was oversized: {path}")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CaptureError(f"loopback response was not JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CaptureError(f"loopback response was not an object: {path}")
    return response.status, value


def _windows_process_snapshot() -> dict[int, ProcessIdentity]:
    if os.name != "nt":
        raise CaptureError("process identity capture requires Windows")

    from ctypes import wintypes

    TH32CS_SNAPPROCESS = 0x00000002
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME)]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise CaptureError("CreateToolhelp32Snapshot failed")
    raw: list[tuple[int, int, str]] = []
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            raw.append((int(entry.th32ProcessID), int(entry.th32ParentProcessID), str(entry.szExeFile)))
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)

    result: dict[int, ProcessIdentity] = {}
    for pid, parent_pid, fallback_name in raw:
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            continue
        try:
            capacity = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(capacity.value)
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(capacity)):
                continue
            created = wintypes.FILETIME()
            exited = wintypes.FILETIME()
            kernel = wintypes.FILETIME()
            user = wintypes.FILETIME()
            if not kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
                continue
            creation_value = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
            result[pid] = ProcessIdentity(pid, parent_pid, f"{creation_value:016x}", buffer.value or fallback_name)
        finally:
            kernel32.CloseHandle(handle)
    return result


def process_snapshot() -> dict[int, ProcessIdentity]:
    return _windows_process_snapshot()


def descendants(processes: dict[int, ProcessIdentity], roots: set[int]) -> set[int]:
    found = set(roots)
    changed = True
    while changed:
        changed = False
        for pid, item in processes.items():
            if pid not in found and item.parent_pid in found:
                found.add(pid)
                changed = True
    return found - roots


def image_set(processes: dict[int, ProcessIdentity], names: set[str]) -> set[tuple[str, str]]:
    return {
        (item.image.casefold(), item.created)
        for item in processes.values()
        if Path(item.image).name.casefold() in names
    }


def backend_has_outbound_tcp(pid: int) -> bool:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    executable = system_root / "System32" / "netstat.exe"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [str(executable), "-ano", "-p", "tcp"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=2, creationflags=flags, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise CaptureError("bounded netstat observation failed")
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) < 5 or fields[0].upper() != "TCP" or fields[-1] != str(pid):
            continue
        remote = fields[2].rsplit(":", 1)[0].strip("[]").casefold()
        state_name = fields[3].upper()
        if state_name in {"ESTABLISHED", "SYN_SENT"} and remote not in {"127.0.0.1", "0.0.0.0", "::1", "::", "*"}:
            return True
    return False


def manifest_integrity(install_root: Path, manifest: dict[str, Any]) -> dict[str, int]:
    records = manifest.get("files")
    if manifest.get("mode") != "LocalRuntime" or manifest.get("source_tree_clean") is not True:
        raise CaptureError("installed manifest is not a clean LocalRuntime release")
    if not isinstance(records, list) or not records:
        raise CaptureError("installed manifest has no file records")
    seen: set[str] = set()
    result = {"records": len(records), "missing": 0, "size_mismatches": 0, "hash_mismatches": 0}
    for record in records:
        if not isinstance(record, dict):
            raise CaptureError("installed manifest contains a non-object record")
        raw = record.get("path")
        if not isinstance(raw, str):
            raise CaptureError("installed manifest contains a non-string path")
        normalized = raw.replace("\\", "/")
        pure = PurePosixPath(normalized)
        if (
            raw.startswith(("/", "\\"))
            or re.match(r"^[A-Za-z]:", normalized)
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise CaptureError(f"installed manifest contains an unsafe path: {raw}")
        key = pure.as_posix().casefold()
        if key in seen:
            raise CaptureError(f"installed manifest contains a duplicate path: {raw}")
        seen.add(key)
        path = install_root.joinpath(*pure.parts)
        if not path.is_file():
            result["missing"] += 1
            continue
        assert_no_reparse_path(install_root, path)
        expected_bytes = record.get("bytes")
        expected_hash = record.get("sha256")
        if isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int) or expected_bytes < 0:
            raise CaptureError(f"installed manifest has an invalid byte count: {raw}")
        if not isinstance(expected_hash, str) or HEX64.fullmatch(expected_hash.lower()) is None:
            raise CaptureError(f"installed manifest has an invalid hash: {raw}")
        if path.stat().st_size != expected_bytes:
            result["size_mismatches"] += 1
        elif sha256_file(path) != expected_hash.lower():
            result["hash_mismatches"] += 1
    return result


def package_manifest(package_zip: Path) -> bytes:
    try:
        with zipfile.ZipFile(package_zip) as archive:
            matches = [name for name in archive.namelist() if name.casefold().endswith("/release-manifest.json")]
            if len(matches) != 1:
                raise CaptureError("reviewed ZIP must contain exactly one release-manifest.json")
            return archive.read(matches[0])
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise CaptureError(f"reviewed ZIP is unreadable: {exc}") from exc


def exact_lineage(config: CaptureConfig, health: dict[str, Any], status: dict[str, Any], processes: dict[int, ProcessIdentity]) -> tuple[ProcessIdentity, ProcessIdentity, ProcessIdentity, ProcessIdentity]:
    backend_pid = status.get("bot_pid")
    service_pid = health.get("service_pid")
    if isinstance(backend_pid, bool) or not isinstance(backend_pid, int) or backend_pid <= 0:
        raise CaptureError("native status has no exact backend PID")
    if isinstance(service_pid, bool) or not isinstance(service_pid, int) or service_pid <= 0:
        raise CaptureError("health has no exact service PID")
    backend = processes.get(backend_pid)
    service = processes.get(service_pid)
    if backend is None or service is None:
        raise CaptureError("backend or service process identity is unavailable")
    controller = processes.get(backend.parent_pid)
    launcher = processes.get(controller.parent_pid) if controller is not None else None
    expected = {
        "backend": config.install_root / "MyBot.run.exe",
        "controller": config.install_root / "MyBot.run.MiniGui.exe",
        "launcher": config.install_root / "My Bot 2.0.exe",
    }
    if controller is None or launcher is None:
        raise CaptureError("launcher/controller/backend ancestry is incomplete")
    if not same_path(backend.image, expected["backend"]):
        raise CaptureError("backend image is not the reviewed installed binary")
    if not same_path(controller.image, expected["controller"]):
        raise CaptureError("controller image is not the reviewed installed binary")
    if not same_path(launcher.image, expected["launcher"]):
        raise CaptureError("launcher image is not the reviewed installed binary")
    if service.parent_pid != backend.pid:
        raise CaptureError("Control Center service is not a child of the exact backend")
    return launcher, controller, backend, service


def require_state(document: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    mismatches = [key for key, value in expected.items() if document.get(key) != value]
    if mismatches:
        raise CaptureError(f"{label} state mismatch: {', '.join(mismatches)}")


def safe_offset(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def preflight(config: CaptureConfig, snapshot: Callable[[], dict[int, ProcessIdentity]] = process_snapshot) -> Preflight:
    config.install_root = canonical(config.install_root, directory=True)
    config.profiles_root = canonical(config.profiles_root, directory=True)
    config.package_zip = canonical(config.package_zip)
    installed_manifest_path = canonical(config.install_root / "release-manifest.json")
    manifest_bytes = installed_manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    if not isinstance(manifest, dict):
        raise CaptureError("installed release manifest is not an object")
    if package_manifest(config.package_zip) != manifest_bytes:
        raise CaptureError("reviewed ZIP manifest does not match the installed manifest exactly")
    integrity = manifest_integrity(config.install_root, manifest)
    if any(integrity[key] for key in ("missing", "size_mismatches", "hash_mismatches")):
        raise CaptureError(f"installed immutable payload drifted: {integrity}")

    status_code, health = api_json(config, "GET", "/api/health")
    if status_code != 200 or health.get("ok") is not True:
        raise CaptureError("Control Center health is unavailable")
    if not same_path(health.get("repo_root", ""), config.install_root):
        raise CaptureError("Control Center repo_root is not the reviewed install root")
    if not same_path(health.get("profiles_root", ""), config.profiles_root):
        raise CaptureError("Control Center profiles_root is not the expected external tree")
    status = health.get("engine")
    if not isinstance(status, dict):
        raise CaptureError("Control Center health has no native engine state")
    require_state(status, EXPECTED_INITIAL, "initial")

    user_root = config.profiles_root.parent
    receipt = user_root / "engine-init-owner-v1.json"
    command = config.install_root / "config" / "control-command.local.json"
    cancel = config.install_root / "config" / "engine-init-cancel.local.json"
    if any(path.exists() for path in (receipt, command, cancel)):
        raise CaptureError("an engine receipt, command, or cancel file already exists")
    if list((config.install_root / "lib").glob("*.html")):
        raise CaptureError("warning HTML already exists in the installed lib directory")

    processes = snapshot()
    launcher, controller, backend, service = exact_lineage(config, health, status, processes)
    if image_set(processes, EMULATOR_IMAGES):
        raise CaptureError("BlueStacks must be absent for the no-emulator check")
    if image_set(processes, ADB_IMAGES):
        raise CaptureError("ADB must be absent for the no-emulator check")

    provenance = json_file(config.install_root / "config" / "binary-provenance.json")
    binaries = [item for item in provenance.get("artifacts", []) if isinstance(item, dict) and str(item.get("path", "")).replace("\\", "/").casefold() == "mybot.run.exe"]
    if len(binaries) != 1:
        raise CaptureError("binary provenance has no unique MyBot.run.exe record")
    binary = {"path": "MyBot.run.exe", "sha256": sha256_file(config.install_root / "MyBot.run.exe"), "bytes": (config.install_root / "MyBot.run.exe").stat().st_size}
    if binaries[0].get("sha256") != binary["sha256"] or binaries[0].get("bytes") != binary["bytes"]:
        raise CaptureError("installed backend does not match binary provenance")
    autoit_version = str(binaries[0].get("provenance", {}).get("tool_version", ""))
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", autoit_version) is None:
        raise CaptureError("binary provenance has no valid AutoIt version")

    profile_ini = canonical(config.profiles_root / "profile.ini")
    english = canonical(config.install_root / "Languages" / "English.ini")
    plan = config.install_root / "config" / "run-plan.local.json"
    events = config.install_root / "logs" / "run-events.jsonl"
    launcher_log = user_root / "launcher-recovery.log"
    return Preflight(
        manifest=manifest, manifest_bytes=manifest_bytes, manifest_sha256=sha256_bytes(manifest_bytes),
        package_sha256=sha256_file(config.package_zip), package_bytes=config.package_zip.stat().st_size,
        binary=binary, autoit_version=autoit_version, health=health, status=status, processes=processes,
        launcher=launcher, controller=controller, backend=backend, service=service,
        profile_sha256=sha256_file(profile_ini), english_sha256=sha256_file(english),
        plan_sha256=sha256_file(plan) if plan.is_file() else None,
        event_offset=safe_offset(events), launcher_log_offset=safe_offset(launcher_log),
        manifest_integrity=integrity,
    )


def read_receipt(path: Path) -> dict[str, Any] | None:
    try:
        parent = path.parent.lstat()
        metadata = path.lstat()
    except OSError:
        return None
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if not stat.S_ISDIR(parent.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise CaptureError("engine receipt path is not a regular file under a regular directory")
    if getattr(parent, "st_file_attributes", 0) & reparse or getattr(metadata, "st_file_attributes", 0) & reparse:
        raise CaptureError("engine receipt path contains a reparse point")
    if metadata.st_size <= 0 or metadata.st_size > MAX_RECEIPT_BYTES:
        raise CaptureError("engine receipt size is invalid")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CaptureError("engine receipt is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise CaptureError("engine receipt is not an object")
    return value


def validate_receipt(receipt: dict[str, Any], request_id: str, pre: Preflight, processes: dict[int, ProcessIdentity]) -> list[dict[str, Any]]:
    if receipt.get("schema") != "engine-init-supervisor-v1":
        raise CaptureError("engine receipt schema is invalid")
    if not isinstance(receipt.get("token"), str) or HEX64.fullmatch(receipt["token"]) is None:
        raise CaptureError("engine receipt token is invalid")
    if receipt.get("start_request_id") != request_id:
        raise CaptureError("engine receipt request does not match the accepted command")
    sequence = receipt.get("sequence")
    phase = receipt.get("phase")
    history = receipt.get("phase_history")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1 or sequence > len(PHASES):
        raise CaptureError("engine receipt sequence is invalid")
    if phase != PHASES[sequence - 1] or history != PHASES[:sequence]:
        raise CaptureError("engine receipt does not retain the exact monotonic phase history")
    for field, expected in (
        ("launcher_pid", pre.launcher.pid), ("launcher_created", pre.launcher.created),
        ("controller_pid", pre.controller.pid), ("controller_created", pre.controller.created),
        ("backend_pid", pre.backend.pid), ("backend_created", pre.backend.created),
        ("parent_pid", pre.controller.pid),
    ):
        if receipt.get(field) != expected:
            raise CaptureError(f"engine receipt identity mismatch: {field}")
    for original in (pre.launcher, pre.controller, pre.backend):
        current = processes.get(original.pid)
        if current is None or current.created != original.created or not same_path(current.image, original.image):
            raise CaptureError("owned launcher/controller/backend generation changed during initialization")
    return [{"sequence": index + 1, "phase": name} for index, name in enumerate(history)]


def read_new_lines(path: Path, offset: int) -> list[str]:
    try:
        with path.open("rb") as stream:
            stream.seek(offset)
            raw = stream.read()
    except OSError:
        return []
    return raw.decode("utf-8-sig", errors="replace").splitlines()


def new_event_delta(path: Path, offset: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in read_new_lines(path, offset):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            raise CaptureError("new run-event line is malformed")
        if isinstance(value, dict):
            events.append(value)
    return events


def safe_state(document: dict[str, Any], *, final: bool) -> dict[str, Any]:
    fields = list(EXPECTED_FINAL if final else EXPECTED_INITIAL)
    result = {key: document.get(key) for key in fields if key != "connected"}
    if final:
        result["session_cleared"] = not bool(document.get("session_id"))
    return result


def write_new_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise CaptureError(f"refusing to overwrite evidence draft: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, indent=2, sort_keys=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def capture(config: CaptureConfig, *, snapshot: Callable[[], dict[int, ProcessIdentity]] = process_snapshot, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> tuple[dict[str, Any], dict[str, Any]]:
    if not config.execute:
        raise CaptureError("capture requires the explicit --execute switch")
    if config.output_directory is None:
        raise CaptureError("capture requires --output-directory")
    pre = preflight(config, snapshot)
    user_root = config.profiles_root.parent
    receipt_path = user_root / "engine-init-owner-v1.json"
    cancel_path = config.install_root / "config" / "engine-init-cancel.local.json"
    command_path = config.install_root / "config" / "control-command.local.json"
    events_path = config.install_root / "logs" / "run-events.jsonl"
    launcher_log_path = user_root / "launcher-recovery.log"
    plan_path = config.install_root / "config" / "run-plan.local.json"
    profile_path = config.profiles_root / "profile.ini"
    english_path = config.install_root / "Languages" / "English.ini"
    manifest_path = config.install_root / "release-manifest.json"
    initial_emulators = image_set(pre.processes, EMULATOR_IMAGES)
    initial_adb = image_set(pre.processes, ADB_IMAGES)
    accepted = False
    completed = False
    request_id = ""
    sampled: list[dict[str, Any]] = []
    browser_child_seen = False
    outbound_seen = False
    terminal_receipt: dict[str, Any] | None = None
    deadline = clock() + config.timeout_seconds
    last_process_poll = 0.0
    last_tcp_poll = 0.0
    latest_processes = pre.processes
    try:
        code, response = api_json(config, "POST", "/api/control/command", {"action": "check-engine"})
        request_id = response.get("request_id", "")
        if code != 202 or response.get("ok") is not True or response.get("accepted") is not True or response.get("native_command_queued") is not True or not isinstance(request_id, str) or REQUEST_ID.fullmatch(request_id) is None:
            raise CaptureError("check-engine was not accepted exactly once")
        accepted = True
        while clock() < deadline:
            receipt = read_receipt(receipt_path)
            if receipt is not None:
                # Bind every observed receipt to a fresh OS identity snapshot before trusting it.
                latest_processes = snapshot()
                sampled = validate_receipt(receipt, request_id, pre, latest_processes)
                if receipt.get("phase") == "initialized":
                    terminal_receipt = receipt
            now = clock()
            if now - last_process_poll >= 0.04:
                latest_processes = snapshot()
                lineage = {pre.launcher.pid, pre.controller.pid, pre.backend.pid}
                for pid in descendants(latest_processes, lineage):
                    item = latest_processes.get(pid)
                    if item and Path(item.image).name.casefold() in BROWSER_IMAGES:
                        browser_child_seen = True
                last_process_poll = now
            if now - last_tcp_poll >= 0.08:
                outbound_seen = outbound_seen or backend_has_outbound_tcp(pre.backend.pid)
                last_tcp_poll = now
            _, status = api_json(config, "GET", "/api/control/status")
            if status.get("engine_probe_state") == "failed" or status.get("last_outcome") == "failed":
                raise CaptureError("managed-engine initialization failed")
            final_ready = all(status.get(key) == value for key, value in EXPECTED_FINAL.items())
            finalized_log = any("engine init supervision finalized; outcome=initialized" in line for line in read_new_lines(launcher_log_path, pre.launcher_log_offset))
            artifacts_absent = not receipt_path.exists() and not cancel_path.exists() and not command_path.exists()
            if terminal_receipt is not None and final_ready and finalized_log and artifacts_absent:
                completed = True
                final_status = status
                break
            sleep(0.01)
        if not completed:
            raise CaptureError("check-engine did not reach finalized idle/passed before the bounded deadline")
    except BaseException:
        if accepted and not completed:
            try:
                api_json(config, "POST", "/api/control/command", {"action": "stop", "expected_start_request_id": request_id})
            except Exception:
                pass
        raise

    after_processes = snapshot()
    current_launcher = after_processes.get(pre.launcher.pid)
    current_controller = after_processes.get(pre.controller.pid)
    current_backend = after_processes.get(pre.backend.pid)
    if any(current is None or current.created != original.created or not same_path(current.image, original.image) for current, original in ((current_launcher, pre.launcher), (current_controller, pre.controller), (current_backend, pre.backend))):
        raise CaptureError("owned process generation changed after check-engine")
    require_state(final_status, EXPECTED_FINAL, "final")
    events = new_event_delta(events_path, pre.event_offset)
    event_types = [event.get("type") for event in events]
    if event_types != ["engine.check.started", "engine.check.passed"]:
        raise CaptureError(f"diagnostic event delta was not exact: {event_types}")
    if browser_child_seen:
        raise CaptureError("a browser process descended from the owned runtime during check-engine")
    if outbound_seen:
        raise CaptureError("the backend opened an outbound TCP connection during check-engine")
    if list((config.install_root / "lib").glob("*.html")):
        raise CaptureError("warning HTML appeared during check-engine")
    after_emulators = image_set(after_processes, EMULATOR_IMAGES)
    after_adb = image_set(after_processes, ADB_IMAGES)
    if after_emulators != initial_emulators or after_adb != initial_adb:
        raise CaptureError("emulator or ADB process identity changed during check-engine")

    profile_after = sha256_file(profile_path)
    english_after = sha256_file(english_path)
    manifest_after = sha256_file(manifest_path)
    plan_after = sha256_file(plan_path) if plan_path.is_file() else None
    if profile_after != pre.profile_sha256 or english_after != pre.english_sha256 or manifest_after != pre.manifest_sha256 or plan_after != pre.plan_sha256:
        raise CaptureError("profile, language, manifest, or saved-plan state changed during check-engine")
    after_integrity = manifest_integrity(config.install_root, pre.manifest)
    if any(after_integrity[key] for key in ("missing", "size_mismatches", "hash_mismatches")):
        raise CaptureError("installed immutable payload drifted during check-engine")

    captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    artifact_id = f"check-engine.pie64.{stamp}"
    evidence_id = f"orchestration.engine-initialization.pie64.{stamp}"
    build = sys.getwindowsversion().build if os.name == "nt" else platform.version()
    environment = {
        "os": "Windows 11 Home", "os_version": f"10.0.{build}", "autoit_version": pre.autoit_version,
        "emulator": "BlueStacks5", "emulator_version": config.emulator_version,
        "instance_index": config.instance_index, "instance_name": config.instance_name,
        "game_version": config.game_version,
    }
    source_commit = str(pre.manifest.get("source_commit", ""))
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise CaptureError("installed manifest source_commit is invalid")
    preservation = {
        "external_profile_before_sha256": pre.profile_sha256,
        "external_profile_after_sha256": profile_after,
        "installed_english_before_sha256": pre.english_sha256,
        "installed_english_after_sha256": english_after,
        "release_manifest_before_sha256": pre.manifest_sha256,
        "release_manifest_after_sha256": manifest_after,
        "emulator_process_identity_preserved": True,
        "adb_daemon_identity_preserved": True,
    }
    if pre.plan_sha256 is None:
        preservation["plan_absent_before_and_after"] = True
    else:
        preservation["saved_plan_before_sha256"] = pre.plan_sha256
        preservation["saved_plan_after_sha256"] = plan_after
    artifact = {
        "schema_version": 2, "artifact_id": artifact_id, "captured_at": captured_at,
        "commit_sha": source_commit, "redacted": True,
        "scope": "Managed-engine initialization in the reviewed installed backend, returning to idle before plan preparation, authentication, emulator discovery, ADB, recognition, or game input.",
        "environment": environment,
        "reviewed_install": {
            "version": pre.manifest.get("version"), "architecture": pre.manifest.get("architecture"),
            "source_commit": source_commit, "release_manifest_sha256": pre.manifest_sha256,
            "package_sha256": pre.package_sha256, "package_bytes": pre.package_bytes,
            "manifest_records": after_integrity["records"], "manifest_missing_after_check": 0,
            "manifest_size_mismatches_after_check": 0, "manifest_hash_mismatches_after_check": 0,
        },
        "binary": pre.binary,
        "command": {"action": "check-engine", "http_status": 202, "accepted": True, "native_command_queued": True, "request_identifier_retained": False},
        "initial_state": {**safe_state(pre.status, final=False), "plan_exists": pre.plan_sha256 is not None},
        "supervision": {
            "lineage_verified": True, "same_backend_identity_before_and_after": True,
            "request_receipt_identity_matched": True, "sampled_receipt_phases": sampled,
            "terminal_sequence": 9, "terminal_phase": "initialized", "finalization_outcome": "initialized",
            "receipt_removed": True, "cancel_removed": True, "command_removed": True,
            "sampling_note": "The final identity-bound receipt retained the complete monotonic phase history; the launcher finalized the unchanged backend generation and removed all control artifacts.",
        },
        "final_state": safe_state(final_status, final=True),
        "events": [
            {"sequence": index + 1, "type": event["type"], "verification_state": event.get("verification_state")}
            for index, event in enumerate(events)
        ],
        "preservation": preservation,
        "assertions": {
            "check_engine_accepted": True, "backend_identity_preserved": True, "engine_initialized": True,
            "idle_restored": True, "supervisor_finalized": True, "diagnostic_events_exact": True,
            "game_input_absent": True, "new_adb_processes": 0, "configuration_preserved": True,
            "warning_html_absent": True, "browser_child_absent": True, "outbound_backend_connections": 0,
        },
        "privacy": "Only allowlisted operational state and integrity digests are retained. Raw request, launch-token, process, creation-time, profile-name, account, player, clan, chat, payment, path, machine, and operator identifiers are omitted.",
    }
    artifact_bytes = (json.dumps(artifact, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    artifact_relative = f"tests/evidence/runtime/artifacts/{artifact_id}.json"
    record = {
        "schema_version": 1, "evidence_id": evidence_id,
        "capability_id": "orchestration.engine-initialization", "test_type": "end-to-end",
        "result": "passed", "captured_at": captured_at, "commit_sha": source_commit,
        "redacted": True, "environment": environment, "binary": pre.binary,
        "checks": [
            {"id": "check-engine.accepted", "result": "passed", "details": "The loopback Control Center accepted one check-engine command in the fresh reviewed backend."},
            {"id": "backend.identity-preserved", "result": "passed", "details": "The same exact backend generation remained alive from idle/not-run through idle/passed."},
            {"id": "engine.initialized", "result": "passed", "details": "The identity-bound receipt retained the complete monotonic real-host phase sequence through initialized."},
            {"id": "idle.restored", "result": "passed", "details": "The command returned to idle with no active run, plan, or session."},
            {"id": "supervisor.finalized", "result": "passed", "details": "The launcher finalized initialized sequence 9 and removed receipt, cancel, and command artifacts."},
            {"id": "diagnostic-events.exact", "result": "passed", "details": "The exact event delta was engine.check.started followed by engine.check.passed."},
            {"id": "game-input.absent", "result": "passed", "details": "No emulator or ADB process existed, no browser child or warning HTML appeared, and the backend opened no observed outbound connection."},
            {"id": "configuration.preserved", "result": "passed", "details": "The manifest, saved-plan state, external profile, installed English file, emulator set, and ADB set were unchanged."},
        ],
        "reviewer": {"name": config.reviewer_name, "reviewed_at": captured_at},
        "artifact_refs": [{"kind": "repository", "path": artifact_relative, "sha256": sha256_bytes(artifact_bytes), "bytes": len(artifact_bytes)}],
        "notes": "Redacted exact-current real-backend initialization draft. It proves no-input engine readiness only, not battle or other gameplay.",
    }
    write_new_json(config.output_directory / f"{artifact_id}.json", artifact)
    write_new_json(config.output_directory / f"{evidence_id}.json", record)
    return artifact, record


def preflight_summary(pre: Preflight) -> dict[str, Any]:
    return {
        "ok": True, "action": "dry-run", "would_queue": "check-engine",
        "manifest_records": pre.manifest_integrity["records"],
        "manifest_missing": pre.manifest_integrity["missing"],
        "manifest_size_mismatches": pre.manifest_integrity["size_mismatches"],
        "manifest_hash_mismatches": pre.manifest_integrity["hash_mismatches"],
        "lineage_verified": True, "idle_not_run": True, "emulator_absent": True,
        "adb_absent": True, "saved_plan_exists": pre.plan_sha256 is not None,
        "privacy": "No process identifiers, paths, request identifiers, tokens, profile names, or account data are retained.",
    }


def parse_args(argv: list[str] | None = None) -> CaptureConfig:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, default=local / "Programs" / "My Bot 2.0")
    parser.add_argument("--profiles-root", type=Path, default=local / "My Bot 2.0" / "Profiles")
    parser.add_argument("--package-zip", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--emulator-version", required=True)
    parser.add_argument("--game-version", required=True)
    parser.add_argument("--instance-name", default="Pie64")
    parser.add_argument("--instance-index", type=int, default=0)
    parser.add_argument("--reviewer-name", default="My Bot 2.0 runtime review")
    parser.add_argument("--timeout-seconds", type=float, default=135.0)
    parser.add_argument("--execute", action="store_true", help="queue exactly one live check-engine command")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not 120.0 <= args.timeout_seconds <= 180.0:
        parser.error("--timeout-seconds must be between 120 and 180")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", args.instance_name):
        parser.error("--instance-name must be a simple identifier")
    if args.instance_index < 0:
        parser.error("--instance-index cannot be negative")
    if args.execute and args.output_directory is None:
        parser.error("--execute requires --output-directory")
    return CaptureConfig(
        install_root=args.install_root, profiles_root=args.profiles_root,
        package_zip=args.package_zip, output_directory=args.output_directory,
        host=args.host, port=args.port, emulator_version=args.emulator_version,
        game_version=args.game_version, instance_name=args.instance_name,
        instance_index=args.instance_index, reviewer_name=args.reviewer_name,
        execute=args.execute, timeout_seconds=args.timeout_seconds,
    )


def main(argv: list[str] | None = None) -> int:
    try:
        config = parse_args(argv)
        if config.execute:
            artifact, record = capture(config)
            print(json.dumps({
                "ok": True, "artifact_id": artifact["artifact_id"],
                "evidence_id": record["evidence_id"], "output_directory": str(config.output_directory),
            }, indent=2))
        else:
            print(json.dumps(preflight_summary(preflight(config)), indent=2))
        return 0
    except CaptureError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
