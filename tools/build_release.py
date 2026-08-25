#!/usr/bin/env python3
"""Build and package the reviewed My Bot 2.0 LocalRuntime release.

This is the non-PowerShell release boundary.  It intentionally implements the
same two-phase contract as ``Build-Release.ps1``:

1. compile six exact x86 candidates from a clean source commit;
2. review and promote those bytes plus binary provenance in a later commit;
3. package only the reviewed candidates from a clean descendant whose only
   intervening changes are the six binaries and binary provenance.

The tool never creates a public-distribution package.  The inherited ImgLoc
redistribution rights remain unresolved; ``LocalRuntime`` means local use only.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping, Sequence


class ReleaseError(RuntimeError):
    """A fail-closed release-contract violation."""


@dataclass(frozen=True)
class CompileTarget:
    source: str
    output: str
    subsystem: str
    pragma_output: str

    @property
    def flags(self) -> tuple[str, ...]:
        return ("/x86", self.subsystem, "/nopack", "/comp", "2")


@dataclass(frozen=True)
class ReleaseContract:
    compile_targets: tuple[CompileTarget, ...]
    runtime_directories: tuple[str, ...]
    runtime_files: tuple[str, ...]
    runtime_config_directories: tuple[str, ...]
    compiler_sha256: str
    compiler_version: str
    compiler_signer: str
    compiler_thumbprint: str
    provenance_tool_signer: str


DEFAULT_CONTRACT = ReleaseContract(
    compile_targets=(
        CompileTarget("My Bot 2.0.au3", "My Bot 2.0.exe", "/gui", "My Bot 2.0.exe"),
        CompileTarget(
            "MyBot.run.EngineProbe.au3",
            "MyBot.run.EngineProbe.exe",
            "/gui",
            "MyBot.run.EngineProbe.exe",
        ),
        CompileTarget("MyBot.run.au3", "MyBot.run.exe", "/gui", "MyBot.run.exe"),
        CompileTarget(
            "MyBot.run.MiniGui.au3",
            "MyBot.run.MiniGui.exe",
            "/gui",
            "MyBot.run.MiniGui.dev.exe",
        ),
        CompileTarget(
            "MyBot.run.Watchdog.au3",
            "MyBot.run.Watchdog.exe",
            "/gui",
            "MyBot.run.Watchdog.exe",
        ),
        CompileTarget("MyBot.run.Wmi.au3", "MyBot.run.Wmi.exe", "/console", "MyBot.run.Wmi.exe"),
    ),
    runtime_directories=(
        "COCBot",
        "CSV",
        "Help",
        "images",
        "imgxml",
        "Languages",
        "lib",
        "Strategies",
        "ui",
    ),
    runtime_files=(
        "Install My Bot 2.0.cmd",
        "Uninstall My Bot 2.0.cmd",
        "My Bot 2.0.au3",
        "MyBot.run.au3",
        "MyBot.run.EngineProbe.au3",
        "MyBot.run.EngineProbe.exe.config",
        "MyBot.run.MiniGui.au3",
        "MyBot.run.Watchdog.au3",
        "MyBot.run.Wmi.au3",
        "MyBot.run.version.au3",
        "MyBot.run.exe.config",
        "MyBot.run Community Support Key.asc",
        "README.md",
        "SECURITY.md",
        "License.txt",
        "upstreams.lock.json",
        "docs/INSTALL.md",
        "packaging/README.md",
        "tools/planner_ui.py",
        "tools/capture_check_engine_evidence.py",
        "tools/Install-LocalRuntime.ps1",
        "tools/install_local_runtime.py",
        "config/account-queue.schema.json",
        "config/battle-route.schema.json",
        "config/binary-provenance.json",
        "config/current-client-capabilities.json",
        "config/redistribution-rights.json",
        "config/redistribution-rights.schema.json",
        "config/run-event.schema.json",
        "config/run-plan.schema.json",
        "config/run-session.schema.json",
        "config/runtime-evidence.schema.json",
    ),
    runtime_config_directories=("config/game", "config/ui"),
    compiler_sha256="921e51d0d9f94c05c5ed10d2d2a80620c8ed930cc48d71e2ce0a5bab4a4f8158",
    compiler_version="3.3.16.1",
    compiler_signer="CN=AutoIt Consulting Ltd, O=AutoIt Consulting Ltd, L=Birmingham, C=GB",
    compiler_thumbprint="B64DDF46C16DEECAA165BB0EC1D640F51588CBEF",
    provenance_tool_signer="AutoIt Consulting Ltd",
)

MODE = "LocalRuntime"
PRODUCT = "My Bot 2.0"
PLATFORM = "windows"
ARCHITECTURE = "x86"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
PYTHON_RUNTIME_PREFIX = "runtime/python/"
PYTHON_RUNTIME_REQUIRED_FILES = frozenset({"python.exe", "pythonw.exe", "LICENSE.txt"})
SAFE_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "version",
        "architecture",
        "compiler_version",
        "compiler_sha256",
        "compiler_signer",
        "source_commit",
        "source_tree_clean",
        "signing_claim",
        "binaries",
    }
)
SAFE_CANDIDATE_RECORD_KEYS = frozenset(
    {"path", "source", "pragma_output", "subsystem", "flags", "bytes", "sha256"}
)
OUT_PRAGMA_RE = re.compile(
    r"(?im)^\s*#pragma\s+compile\(Out,\s*([^)]+?)\s*\)\s*(?:;[^\r\n]*)?$"
)


def _run(
    args: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path | None = None,
    timeout: float = 30.0,
    text: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    rendered = [os.fspath(value) for value in args]
    try:
        return subprocess.run(
            rendered,
            cwd=os.fspath(cwd) if cwd else None,
            check=check,
            capture_output=True,
            text=text,
            timeout=timeout,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise ReleaseError(f"Command timed out after {timeout:g}s: {rendered[0]}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout
        detail = (stderr or stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise ReleaseError(f"Command failed ({exc.returncode}): {rendered[0]}{suffix}") from exc
    except OSError as exc:
        raise ReleaseError(f"Could not start command {rendered[0]}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deterministic_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def normalize_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    raw_parts = normalized.split("/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or "\0" in normalized
        or path.is_absolute()
        or normalized.startswith("/")
        or any(part in ("", ".", "..") for part in raw_parts)
        or any(":" in part for part in raw_parts)
        or path.as_posix() != normalized
    ):
        raise ReleaseError(f"Unsafe relative path: {value}")
    return path.as_posix()


def is_excluded_release_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    lower = normalized.casefold()
    if lower == "languages/english.ini":
        return True
    if re.search(r"(?i)(^|/)[^/]+_HANDOFF_PROMPT\.md$", normalized):
        return True
    if re.match(r"(?i)^lib/[^/]+\.html$", normalized):
        return True
    if re.match(r"(?i)^tools/_[^/]*\.exe$", normalized):
        return True
    if re.search(
        r"(?i)(^|/)(Profiles|logs|artifacts|__pycache__|\.pytest_cache|node_modules|temp|tmp|cache)(/|$)",
        normalized,
    ):
        return True
    if re.search(r"(?i)(^|/)[^/]+\.local\.json$", normalized):
        return True
    if re.search(
        r"(?i)(^|/)(control-command|control-status|run-plan)(?:\.[^/]*)?\.local\.json$",
        normalized,
    ):
        return True
    if re.search(r"(?i)(^|/)run-events(?:\.[^/]*)?\.jsonl$", normalized):
        return True
    if re.search(r"(?i)\.(log|tmp|bak|cache|pyc|pyo)$", normalized):
        return True
    return False


def _git(repo: Path, args: Sequence[str], *, binary: bool = False) -> str | bytes:
    result = _run(["git", "-C", repo, *args], cwd=repo, timeout=30, text=not binary)
    return result.stdout


def repository_root(path: Path) -> Path:
    resolved = path.resolve()
    top = Path(str(_git(resolved, ["rev-parse", "--show-toplevel"])).strip()).resolve()
    if top != resolved:
        raise ReleaseError(f"Repository root mismatch: expected {resolved}, Git reports {top}")
    return top


def current_commit(repo: Path) -> str:
    commit = str(_git(repo, ["rev-parse", "HEAD"])).strip().lower()
    if not COMMIT_RE.fullmatch(commit):
        raise ReleaseError("The source commit could not be resolved to a full SHA-1.")
    return commit


def assert_clean_source(repo: Path) -> None:
    status = str(_git(repo, ["status", "--porcelain=v1", "--untracked-files=all"]))
    if status:
        first = status.splitlines()[0]
        raise ReleaseError(f"The release source tree is dirty: {first}")


def git_blob(repo: Path, commit: str, relative_path: str) -> bytes:
    normalized = normalize_relative_path(relative_path)
    return bytes(_git(repo, ["cat-file", "blob", f"{commit}:{normalized}"], binary=True))


def tracked_files(repo: Path, commit: str) -> dict[str, str]:
    raw = bytes(_git(repo, ["ls-tree", "-r", "-z", "--full-tree", commit], binary=True))
    records: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item:
            continue
        try:
            metadata, raw_path = item.split(b"\t", 1)
            mode, object_type, _blob = metadata.decode("ascii").split(" ")
            path = normalize_relative_path(raw_path.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ReleaseError("Git returned an invalid tracked-file record.") from exc
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise ReleaseError(f"Release input is not a regular tracked file: {path} ({mode}, {object_type})")
        key = path.casefold()
        if key in records:
            raise ReleaseError(f"Tracked release paths collide case-insensitively: {path}")
        records[key] = path
    return records


def assert_output_boundary(repo: Path, output: Path) -> Path:
    resolved = output.resolve()
    try:
        repo.relative_to(resolved)
    except ValueError:
        pass
    else:
        raise ReleaseError("Output directory must not be the repository root or one of its parents.")
    try:
        relative = resolved.relative_to(repo)
    except ValueError:
        return resolved
    if not relative.parts or relative.parts[0].casefold() != "artifacts":
        raise ReleaseError("An output inside the repository must remain below the excluded artifacts directory.")
    return resolved


def validate_version(repo: Path, commit: str, version: str) -> None:
    if not VERSION_RE.fullmatch(version):
        raise ReleaseError(f"Invalid release version: {version}")
    source = git_blob(repo, commit, "MyBot.run.version.au3").decode("utf-8", errors="strict")
    match = re.search(r'Global Const \$g_sProductVersion\s*=\s*"v([^"\r\n]+)"', source)
    if not match or match.group(1) != version:
        raise ReleaseError(f"Requested release version {version} does not match MyBot.run.version.au3.")


def _windows_file_version(path: Path) -> str:
    if os.name != "nt":
        raise ReleaseError("AutoIt compiler validation is supported only on Windows.")
    version = ctypes.WinDLL("version", use_last_error=True)
    size = version.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        raise ReleaseError("Could not read the AutoIt compiler version resource.")
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, buffer):
        raise ReleaseError("Could not load the AutoIt compiler version resource.")
    pointer = ctypes.c_void_p()
    length = ctypes.c_uint()
    if not version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        raise ReleaseError("Could not query the AutoIt compiler version resource.")
    fixed = ctypes.string_at(pointer, length.value)
    if len(fixed) < 16:
        raise ReleaseError("The AutoIt compiler version resource is malformed.")
    ms = int.from_bytes(fixed[8:12], "little")
    ls = int.from_bytes(fixed[12:16], "little")
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"


def _verify_authenticode(path: Path, contract: ReleaseContract) -> None:
    if os.name != "nt":
        raise ReleaseError("Authenticode compiler validation is supported only on Windows.")
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = (
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        )

    class WINTRUST_FILE_INFO(ctypes.Structure):
        _fields_ = (
            ("cbStruct", wintypes.DWORD),
            ("pcwszFilePath", wintypes.LPCWSTR),
            ("hFile", wintypes.HANDLE),
            ("pgKnownSubject", ctypes.POINTER(GUID)),
        )

    class WINTRUST_DATA(ctypes.Structure):
        _fields_ = (
            ("cbStruct", wintypes.DWORD),
            ("pPolicyCallbackData", wintypes.LPVOID),
            ("pSIPClientData", wintypes.LPVOID),
            ("dwUIChoice", wintypes.DWORD),
            ("fdwRevocationChecks", wintypes.DWORD),
            ("dwUnionChoice", wintypes.DWORD),
            ("pFile", ctypes.POINTER(WINTRUST_FILE_INFO)),
            ("dwStateAction", wintypes.DWORD),
            ("hWVTStateData", wintypes.HANDLE),
            ("pwszURLReference", wintypes.LPCWSTR),
            ("dwProvFlags", wintypes.DWORD),
            ("dwUIContext", wintypes.DWORD),
        )

    action = GUID(
        0x00AAC56B,
        0xCD44,
        0x11D0,
        (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE),
    )
    file_info = WINTRUST_FILE_INFO(
        ctypes.sizeof(WINTRUST_FILE_INFO), str(path), None, None
    )
    trust_data = WINTRUST_DATA(
        ctypes.sizeof(WINTRUST_DATA),
        None,
        None,
        2,  # WTD_UI_NONE
        0,  # WTD_REVOKE_NONE; timestamp trust remains enforced
        1,  # WTD_CHOICE_FILE
        ctypes.pointer(file_info),
        0,  # WTD_STATEACTION_IGNORE
        None,
        None,
        0x1000,  # WTD_CACHE_ONLY_URL_RETRIEVAL: bounded and deterministic
        0,
    )
    wintrust = ctypes.WinDLL("wintrust", use_last_error=True)
    verify = wintrust.WinVerifyTrust
    verify.argtypes = (wintypes.HWND, ctypes.POINTER(GUID), ctypes.POINTER(WINTRUST_DATA))
    verify.restype = ctypes.c_long
    trust_status = verify(None, ctypes.byref(action), ctypes.byref(trust_data))
    if trust_status != 0:
        raise ReleaseError(f"The AutoIt compiler Authenticode trust check failed: 0x{trust_status & 0xFFFFFFFF:08x}")

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    query = crypt32.CryptQueryObject
    query.argtypes = (
        wintypes.DWORD,
        wintypes.LPCVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.HANDLE),
        ctypes.POINTER(wintypes.HANDLE),
        ctypes.POINTER(wintypes.LPVOID),
    )
    query.restype = wintypes.BOOL
    encoding = wintypes.DWORD()
    content = wintypes.DWORD()
    fmt = wintypes.DWORD()
    store = wintypes.HANDLE()
    message = wintypes.HANDLE()
    if not query(
        1,  # CERT_QUERY_OBJECT_FILE
        ctypes.cast(ctypes.c_wchar_p(str(path)), wintypes.LPCVOID),
        1 << 10,  # CERT_QUERY_CONTENT_FLAG_PKCS7_SIGNED_EMBED
        1 << 1,  # CERT_QUERY_FORMAT_FLAG_BINARY
        0,
        ctypes.byref(encoding),
        ctypes.byref(content),
        ctypes.byref(fmt),
        ctypes.byref(store),
        ctypes.byref(message),
        None,
    ):
        raise ReleaseError("The AutoIt compiler signer certificate store could not be opened.")

    enumerate_certificate = crypt32.CertEnumCertificatesInStore
    enumerate_certificate.argtypes = (wintypes.HANDLE, wintypes.LPVOID)
    enumerate_certificate.restype = wintypes.LPVOID
    get_property = crypt32.CertGetCertificateContextProperty
    get_property.argtypes = (wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID, ctypes.POINTER(wintypes.DWORD))
    get_property.restype = wintypes.BOOL
    get_name = crypt32.CertGetNameStringW
    get_name.argtypes = (
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPWSTR,
        wintypes.DWORD,
    )
    get_name.restype = wintypes.DWORD
    free_context = crypt32.CertFreeCertificateContext
    free_context.argtypes = (wintypes.LPVOID,)
    free_context.restype = wintypes.BOOL
    close_message = crypt32.CryptMsgClose
    close_message.argtypes = (wintypes.HANDLE,)
    close_message.restype = wintypes.BOOL
    close_store = crypt32.CertCloseStore
    close_store.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    close_store.restype = wintypes.BOOL

    expected_thumbprint = bytes.fromhex(contract.compiler_thumbprint)
    signer_subject: str | None = None
    current = None
    try:
        while True:
            current = enumerate_certificate(store, current)
            if not current:
                break
            size = wintypes.DWORD()
            if not get_property(current, 3, None, ctypes.byref(size)):  # CERT_SHA1_HASH_PROP_ID
                continue
            value = (ctypes.c_ubyte * size.value)()
            if not get_property(current, 3, value, ctypes.byref(size)):
                continue
            if bytes(value[: size.value]) != expected_thumbprint:
                continue

            fields: list[tuple[str, str]] = []
            for prefix, oid in (
                ("CN", b"2.5.4.3"),
                ("O", b"2.5.4.10"),
                ("L", b"2.5.4.7"),
                ("C", b"2.5.4.6"),
            ):
                oid_pointer = ctypes.c_char_p(oid)
                required = get_name(current, 3, 0, ctypes.cast(oid_pointer, wintypes.LPVOID), None, 0)
                if required <= 1:
                    fields = []
                    break
                buffer = ctypes.create_unicode_buffer(required)
                if get_name(
                    current,
                    3,
                    0,
                    ctypes.cast(oid_pointer, wintypes.LPVOID),
                    buffer,
                    required,
                ) != required:
                    fields = []
                    break
                fields.append((prefix, buffer.value))
            if fields:
                signer_subject = ", ".join(f"{prefix}={value}" for prefix, value in fields)
            break
    finally:
        # CertEnum frees each preceding context. If the loop stopped early, the
        # last returned context is still caller-owned.
        if current:
            free_context(current)
        if message:
            close_message(message)
        if store:
            close_store(store, 0)
    if signer_subject != contract.compiler_signer:
        raise ReleaseError("The AutoIt compiler signer subject or thumbprint does not match the pinned identity.")


def find_and_validate_compiler(autoit_root: Path, contract: ReleaseContract = DEFAULT_CONTRACT) -> Path:
    root = autoit_root.resolve()
    if not root.is_dir():
        raise ReleaseError(f"AutoIt root does not exist: {root}")
    candidates = sorted(
        (path for path in root.rglob("Aut2Exe.exe") if "x64" not in {part.casefold() for part in path.parts}),
        key=lambda path: str(path).casefold(),
    )
    if not candidates:
        raise ReleaseError(f"The x86 Aut2Exe.exe was not found under {root}")
    compiler = candidates[0]
    if sha256_file(compiler) != contract.compiler_sha256:
        raise ReleaseError("Aut2Exe does not match the pinned compiler SHA-256.")
    if _windows_file_version(compiler) != contract.compiler_version:
        raise ReleaseError("Aut2Exe does not match the pinned compiler version.")
    _verify_authenticode(compiler, contract)
    return compiler


def _wait_for_stable_output(paths: Sequence[Path], deadline_seconds: float = 30.0) -> Path:
    deadline = time.monotonic() + deadline_seconds
    selected: Path | None = None
    last_size = -1
    stable_samples = 0
    while time.monotonic() < deadline:
        present = [path for path in paths if path.is_file()]
        if len(present) > 1:
            raise ReleaseError("Aut2Exe produced both the isolated and pragma output paths.")
        if present:
            candidate = present[0]
            size = candidate.stat().st_size
            if selected == candidate and size > 0 and size == last_size:
                stable_samples += 1
            else:
                selected = candidate
                stable_samples = 0
            last_size = size
            if stable_samples >= 2:
                return candidate
        time.sleep(0.1)
    raise ReleaseError("Aut2Exe output did not become present, non-empty, and stable within 30 seconds.")


def _declared_pragma_output(repo: Path, source: Path, target: CompileTarget) -> Path:
    try:
        text = source.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise ReleaseError(f"Compile source is not readable UTF-8: {target.source}") from exc
    matches = OUT_PRAGMA_RE.findall(text)
    if len(matches) != 1:
        raise ReleaseError(f"Compile source must declare exactly one output pragma: {target.source}")
    declared = normalize_relative_path(matches[0].strip().replace("\\", "/"))
    expected = normalize_relative_path(target.pragma_output)
    if declared != expected:
        raise ReleaseError(
            f"Compile source output pragma does not match the release contract: {target.source} "
            f"(declared={declared}, expected={expected})"
        )
    return repo.joinpath(*PurePosixPath(expected).parts)


def _compile_one(compiler: Path, repo: Path, stage: Path, target: CompileTarget) -> Path:
    source = repo / Path(target.source)
    if not source.is_file():
        raise ReleaseError(f"Compile source is missing: {target.source}")
    isolated_output = stage / target.output
    pragma_output = _declared_pragma_output(repo, source, target)
    # Keep the rollback copy beside the source output, not under the temporary
    # candidate stage.  If a hostile/broken compiler replaces the output path
    # with a directory or reparse point, the original bytes survive cleanup and
    # the operator receives the exact recovery path.
    backup = pragma_output.with_name(
        f".{pragma_output.name}.release-backup-{uuid.uuid4().hex}.exe"
    )
    if pragma_output.exists() and (_is_reparse_point(pragma_output) or not pragma_output.is_file()):
        raise ReleaseError(f"Compile output path is not a regular non-reparse file: {pragma_output}")
    had_original = pragma_output.is_file()
    if had_original:
        pragma_output.replace(backup)
    try:
        result = _run(
            [
                compiler,
                "/in",
                source,
                "/out",
                isolated_output,
                *target.flags,
            ],
            cwd=repo,
            timeout=120,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise ReleaseError(f"Aut2Exe failed for {target.source} with exit code {result.returncode}: {detail}")
        produced = _wait_for_stable_output((isolated_output, pragma_output))
        if produced == pragma_output:
            produced.replace(isolated_output)
        return isolated_output
    finally:
        unsafe_output: Path | None = None
        if pragma_output.exists():
            if pragma_output.is_file() and not pragma_output.is_symlink():
                pragma_output.unlink()
            else:
                unsafe_output = pragma_output
        if had_original and backup.is_file() and not pragma_output.exists():
            backup.replace(pragma_output)
        if unsafe_output is not None:
            recovery = f" Original bytes remain at {backup}." if backup.exists() else ""
            raise ReleaseError(f"Aut2Exe left an unsafe output object: {unsafe_output}.{recovery}")


def _candidate_record(path: Path, target: CompileTarget) -> dict[str, object]:
    return {
        "path": target.output,
        "source": target.source,
        "pragma_output": target.pragma_output,
        "subsystem": target.subsystem,
        "flags": list(target.flags),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def compile_for_review(
    repo: Path,
    autoit_root: Path,
    version: str,
    output_directory: Path,
    contract: ReleaseContract = DEFAULT_CONTRACT,
) -> Path:
    repo = repository_root(repo)
    assert_clean_source(repo)
    source_commit = current_commit(repo)
    validate_version(repo, source_commit, version)
    output_root = assert_output_boundary(repo, output_directory)
    output_root.mkdir(parents=True, exist_ok=True)
    candidate = output_root / f"MyBot-{version}-win-x86-candidate"
    if candidate.exists():
        raise ReleaseError(f"Candidate output already exists: {candidate}")
    compiler = find_and_validate_compiler(autoit_root, contract)

    with tempfile.TemporaryDirectory(prefix=".release-compile-", dir=output_root) as temporary:
        stage = Path(temporary) / "compiled"
        stage.mkdir()
        records: list[dict[str, object]] = []
        for target in contract.compile_targets:
            built = _compile_one(compiler, repo, stage, target)
            records.append(_candidate_record(built, target))
        assert_clean_source(repo)
        if current_commit(repo) != source_commit:
            raise ReleaseError("The source commit changed while candidates were compiling.")
        manifest = {
            "schema_version": 1,
            "version": version,
            "architecture": ARCHITECTURE,
            "compiler_version": contract.compiler_version,
            "compiler_sha256": contract.compiler_sha256,
            "compiler_signer": contract.compiler_signer,
            "source_commit": source_commit,
            "source_tree_clean": True,
            "signing_claim": "none",
            "binaries": records,
        }
        write_new(stage / "candidate-hashes.json", deterministic_json(manifest))
        stage.replace(candidate)
    return candidate


def _require_exact_keys(value: Mapping[str, object], expected: frozenset[str], label: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise ReleaseError(f"{label} keys differ from the release contract.")


def read_candidate_manifest(
    directory: Path,
    version: str,
    contract: ReleaseContract = DEFAULT_CONTRACT,
) -> dict[str, object]:
    supplied = directory.absolute()
    if _is_reparse_point(supplied):
        raise ReleaseError(f"Reviewed candidate directory is a reparse point: {supplied}")
    root = supplied.resolve()
    if not root.is_dir():
        raise ReleaseError(f"Reviewed candidate directory is missing or unsafe: {root}")
    expected_files = {"candidate-hashes.json", *(target.output for target in contract.compile_targets)}
    actual_files: set[str] = set()
    for child in root.iterdir():
        if _is_reparse_point(child) or not child.is_file():
            raise ReleaseError(f"Reviewed candidate contains an unsafe object: {child.name}")
        actual_files.add(child.name)
    if actual_files != expected_files:
        raise ReleaseError("Reviewed candidate directory does not contain the exact compile matrix and manifest.")
    try:
        manifest = json.loads((root / "candidate-hashes.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError("Reviewed candidate manifest is not valid UTF-8 JSON.") from exc
    if not isinstance(manifest, dict):
        raise ReleaseError("Reviewed candidate manifest must be an object.")
    _require_exact_keys(manifest, SAFE_MANIFEST_KEYS, "Candidate manifest")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("version") != version
        or manifest.get("architecture") != ARCHITECTURE
        or manifest.get("compiler_version") != contract.compiler_version
        or manifest.get("compiler_sha256") != contract.compiler_sha256
        or manifest.get("compiler_signer") != contract.compiler_signer
        or manifest.get("source_tree_clean") is not True
        or manifest.get("signing_claim") != "none"
    ):
        raise ReleaseError("Reviewed candidate manifest does not match the product/compiler contract.")
    source_commit = manifest.get("source_commit")
    if not isinstance(source_commit, str) or not COMMIT_RE.fullmatch(source_commit):
        raise ReleaseError("Reviewed candidate manifest has an invalid source commit.")
    records = manifest.get("binaries")
    if not isinstance(records, list) or len(records) != len(contract.compile_targets):
        raise ReleaseError("Reviewed candidate manifest does not contain the exact compile matrix.")
    seen: set[str] = set()
    for target, record in zip(contract.compile_targets, records, strict=True):
        if not isinstance(record, dict):
            raise ReleaseError(f"Reviewed candidate record is not an object: {target.output}")
        _require_exact_keys(record, SAFE_CANDIDATE_RECORD_KEYS, f"Candidate record {target.output}")
        if (
            record.get("path") != target.output
            or record.get("source") != target.source
            or record.get("pragma_output") != target.pragma_output
            or record.get("subsystem") != target.subsystem
            or record.get("flags") != list(target.flags)
        ):
            raise ReleaseError(f"Reviewed candidate identity or flags mismatch: {target.output}")
        key = target.output.casefold()
        if key in seen:
            raise ReleaseError(f"Reviewed candidate contains a duplicate path: {target.output}")
        seen.add(key)
        path = root / target.output
        expected_bytes = record.get("bytes")
        expected_sha = record.get("sha256")
        if (
            isinstance(expected_bytes, bool)
            or not isinstance(expected_bytes, int)
            or expected_bytes <= 0
            or not isinstance(expected_sha, str)
            or not SHA256_RE.fullmatch(expected_sha)
            or path.stat().st_size != expected_bytes
            or sha256_file(path) != expected_sha
        ):
            raise ReleaseError(f"Reviewed candidate bytes do not match candidate-hashes.json: {target.output}")
    return manifest


def assert_candidate_ancestry(
    repo: Path,
    candidate_commit: str,
    package_commit: str,
    contract: ReleaseContract = DEFAULT_CONTRACT,
) -> None:
    result = _run(
        ["git", "-C", repo, "merge-base", "--is-ancestor", candidate_commit, package_commit],
        cwd=repo,
        timeout=30,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseError("Reviewed candidate source commit is not an ancestor of the package source commit.")
    if candidate_commit == package_commit:
        return
    changed = str(_git(repo, ["diff", "--name-only", f"{candidate_commit}..{package_commit}", "--"])).splitlines()
    allowed = {"config/binary-provenance.json", *(target.output for target in contract.compile_targets)}
    allowed_folded = {path.casefold() for path in allowed}
    for path in changed:
        normalized = normalize_relative_path(path)
        if normalized.casefold() not in allowed_folded:
            raise ReleaseError(f"Package source changed after candidate compilation: {normalized}")


def _parse_iso_date(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ReleaseError(f"{label} must be an ISO calendar date.")
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ReleaseError(f"{label} must be an ISO calendar date.") from exc
    if parsed.isoformat() != value:
        raise ReleaseError(f"{label} must be an ISO calendar date.")
    return value


def read_provenance(data: bytes) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError("Binary provenance is not valid UTF-8 JSON.") from exc
    if not isinstance(document, dict) or set(document) != {"schema_version", "reviewed_at", "artifacts"}:
        raise ReleaseError("Binary provenance has an invalid top-level shape.")
    if document.get("schema_version") != 1:
        raise ReleaseError("Unsupported binary provenance schema.")
    _parse_iso_date(document.get("reviewed_at"), "Binary provenance reviewed_at")
    artifacts = document.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ReleaseError("Binary provenance contains no artifacts.")
    indexed: dict[str, dict[str, object]] = {}
    for raw in artifacts:
        if not isinstance(raw, dict) or set(raw) != {"path", "sha256", "bytes", "provenance"}:
            raise ReleaseError("Binary provenance contains a malformed artifact record.")
        path = normalize_relative_path(str(raw.get("path", "")))
        key = path.casefold()
        if key in indexed:
            raise ReleaseError(f"Binary provenance contains a duplicate path: {path}")
        digest = raw.get("sha256")
        size = raw.get("bytes")
        origin = raw.get("provenance")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise ReleaseError(f"Binary provenance contains an invalid SHA-256: {path}")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ReleaseError(f"Binary provenance contains an invalid byte count: {path}")
        if not isinstance(origin, dict):
            raise ReleaseError(f"Binary provenance contains an invalid origin: {path}")
        normalized_record = dict(raw)
        normalized_record["path"] = path
        indexed[key] = normalized_record
    return document, indexed


def _validate_local_build_provenance(
    indexed: Mapping[str, dict[str, object]],
    candidate: Path,
    manifest: Mapping[str, object],
    contract: ReleaseContract,
) -> None:
    records = manifest["binaries"]
    assert isinstance(records, list)
    candidate_commit = str(manifest["source_commit"])
    for target, candidate_record in zip(contract.compile_targets, records, strict=True):
        record = indexed.get(target.output.casefold())
        if record is None:
            raise ReleaseError(f"Compiled target has no provenance record: {target.output}")
        origin = record["provenance"]
        assert isinstance(origin, dict)
        required_origin = {
            "kind": "local-build",
            "source": target.source,
            "pragma_output": target.pragma_output,
            "toolchain": "AutoIt Aut2Exe",
            "tool_version": contract.compiler_version,
            "tool_signer": contract.provenance_tool_signer,
            "source_commit": candidate_commit,
            "compiler_sha256": contract.compiler_sha256,
            "compile_flags": list(target.flags),
        }
        for key, expected in required_origin.items():
            if origin.get(key) != expected:
                raise ReleaseError(f"Compiled target provenance {key} mismatch: {target.output}")
        _parse_iso_date(origin.get("built_at"), f"Compiled target built_at for {target.output}")
        path = candidate / target.output
        if record["bytes"] != path.stat().st_size or record["sha256"] != sha256_file(path):
            raise ReleaseError(f"Compiled target provenance bytes mismatch: {target.output}")
        if record["bytes"] != candidate_record["bytes"] or record["sha256"] != candidate_record["sha256"]:
            raise ReleaseError(f"Candidate and provenance identity differ: {target.output}")


def _selected_release_paths(
    tracked: Mapping[str, str], contract: ReleaseContract
) -> list[str]:
    selected: dict[str, str] = {}

    def add(path: str) -> None:
        normalized = normalize_relative_path(path)
        if is_excluded_release_path(normalized):
            return
        tracked_path = tracked.get(normalized.casefold())
        if tracked_path is None:
            raise ReleaseError(f"Release input is not tracked by Git: {normalized}")
        selected[tracked_path.casefold()] = tracked_path

    for directory in (*contract.runtime_directories, *contract.runtime_config_directories):
        prefix = normalize_relative_path(directory).rstrip("/") + "/"
        matches = [path for path in tracked.values() if path.casefold().startswith(prefix.casefold())]
        if not matches:
            raise ReleaseError(f"Allowlisted release directory has no tracked files: {directory}")
        for path in matches:
            add(path)
    for path in contract.runtime_files:
        add(path)
    # English is deliberately exported from Git even though live copies are excluded.
    english = tracked.get("languages/english.ini")
    if english is None:
        raise ReleaseError("Canonical tracked Languages/English.ini is missing.")
    selected[english.casefold()] = english
    return sorted(selected.values(), key=lambda item: (item.casefold(), item))


def _safe_payload_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for directory, names, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(directory)
        for name in list(names):
            path = current / name
            if _is_reparse_point(path):
                raise ReleaseError(f"Release payload contains a reparse-point directory: {path}")
        for name in filenames:
            path = current / name
            if _is_reparse_point(path) or not path.is_file():
                raise ReleaseError(f"Release payload contains an unsafe file: {path}")
            relative = path.relative_to(root).as_posix()
            normalize_relative_path(relative)
            files.append(path)
    return sorted(files, key=lambda item: (item.relative_to(root).as_posix().casefold(), item.as_posix()))


def _is_reparse_point(path: Path) -> bool:
    try:
        status = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(status, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def assert_repository_audit(repo: Path) -> None:
    audit = repo / "tools" / "repo_audit.py"
    if not audit.is_file() or _is_reparse_point(audit):
        raise ReleaseError("The tracked repository audit is missing or unsafe.")
    result = _run(
        [sys.executable, audit, "--root", repo],
        cwd=repo,
        timeout=120,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ReleaseError(f"Repository audit failed before packaging: {detail}")


def _write_deterministic_zip(payload: Path, destination: Path) -> None:
    parent = payload.parent
    files = _safe_payload_files(payload)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    if destination.exists() or temporary.exists():
        raise ReleaseError(f"Release ZIP or temporary output already exists: {destination}")
    try:
        with zipfile.ZipFile(
            temporary,
            mode="x",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=True,
        ) as archive:
            for path in files:
                entry_name = path.relative_to(parent).as_posix()
                info = zipfile.ZipInfo(entry_name, date_time=ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                info.flag_bits = 0
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        # Hard-link promotion is a same-volume, atomic create-if-absent.  Unlike
        # os.replace(), it cannot clobber a release another process won the race
        # to publish after the initial existence check.
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise ReleaseError(f"Release ZIP already exists: {destination}") from exc
        except OSError as exc:
            raise ReleaseError(f"Could not atomically publish release ZIP: {exc}") from exc
        temporary.unlink()
    finally:
        if temporary.exists():
            temporary.unlink()


def _copy_local_python_runtime(source: Path, payload: Path) -> list[dict[str, object]]:
    source = source.resolve()
    if not source.is_dir() or _is_reparse_point(source):
        raise ReleaseError(f"Python runtime directory is missing or unsafe: {source}")
    present = {path.name for path in source.iterdir() if path.is_file()}
    missing = sorted(PYTHON_RUNTIME_REQUIRED_FILES - present)
    if missing:
        raise ReleaseError("Python runtime directory is incomplete: missing " + ", ".join(missing))
    destination = payload / "runtime" / "python"
    if destination.exists():
        raise ReleaseError(f"Python runtime destination already exists: {destination}")
    for directory, names, filenames in os.walk(source, topdown=True, followlinks=False):
        current = Path(directory)
        for name in list(names):
            child = current / name
            if _is_reparse_point(child):
                raise ReleaseError(f"Python runtime contains a reparse-point directory: {child}")
        relative_dir = current.relative_to(source)
        target_dir = destination / relative_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            child = current / name
            if _is_reparse_point(child) or not child.is_file():
                raise ReleaseError(f"Python runtime contains an unsafe file: {child}")
            relative = child.relative_to(source).as_posix()
            normalize_relative_path(relative)
            target = target_dir / name
            if target.exists():
                raise ReleaseError(f"Python runtime duplicate destination path: {target}")
            shutil.copy2(child, target)
    return [
        {
            "path": PYTHON_RUNTIME_PREFIX + path.relative_to(destination).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in _safe_payload_files(destination)
    ]


def package_reviewed(
    repo: Path,
    candidate_directory: Path,
    version: str,
    output_directory: Path,
    contract: ReleaseContract = DEFAULT_CONTRACT,
    python_runtime_directory: Path | None = None,
) -> Path:
    repo = repository_root(repo)
    assert_clean_source(repo)
    package_commit = current_commit(repo)
    validate_version(repo, package_commit, version)
    assert_repository_audit(repo)
    assert_clean_source(repo)
    if current_commit(repo) != package_commit:
        raise ReleaseError("The source commit changed while the repository audit was running.")
    output_root = assert_output_boundary(repo, output_directory)
    output_root.mkdir(parents=True, exist_ok=True)
    final_zip = output_root / f"MyBot-{version}-win-x86.zip"
    if final_zip.exists():
        raise ReleaseError(f"Release ZIP already exists: {final_zip}")

    supplied_candidate = candidate_directory.absolute()
    manifest = read_candidate_manifest(supplied_candidate, version, contract)
    candidate = supplied_candidate.resolve()
    candidate_commit = str(manifest["source_commit"])
    assert_candidate_ancestry(repo, candidate_commit, package_commit, contract)
    tracked = tracked_files(repo, package_commit)

    # The promoted, tracked binaries must be the exact reviewed candidate bytes.
    for target in contract.compile_targets:
        promoted = git_blob(repo, package_commit, target.output)
        reviewed = (candidate / target.output).read_bytes()
        if promoted != reviewed:
            raise ReleaseError(f"Promoted Git binary differs from the reviewed candidate: {target.output}")

    provenance_data = git_blob(repo, package_commit, "config/binary-provenance.json")
    _provenance, indexed = read_provenance(provenance_data)
    _validate_local_build_provenance(indexed, candidate, manifest, contract)

    package_name = f"MyBot-{version}-win-x86"
    with tempfile.TemporaryDirectory(prefix=".release-package-", dir=output_root) as temporary:
        payload = Path(temporary) / package_name
        payload.mkdir()
        for relative in _selected_release_paths(tracked, contract):
            write_new(payload / Path(relative), git_blob(repo, package_commit, relative))

        marker = git_blob(repo, package_commit, "MyBot.run.txt")
        if marker != b"":
            raise ReleaseError("MyBot.run.txt must exist in Git and remain exactly zero bytes.")
        write_new(payload / "MyBot.run.txt", b"")

        for target in contract.compile_targets:
            write_new(payload / target.output, (candidate / target.output).read_bytes())

        python_runtime_records: list[dict[str, object]] = []
        if python_runtime_directory is not None:
            python_runtime_records = _copy_local_python_runtime(python_runtime_directory, payload)
        python_runtime_index = {str(record["path"]).casefold(): record for record in python_runtime_records}

        for path in _safe_payload_files(payload):
            relative = path.relative_to(payload).as_posix()
            if relative.casefold() != "languages/english.ini" and is_excluded_release_path(relative):
                raise ReleaseError(f"A forbidden runtime or local-state path entered the payload: {relative}")

        packaged_native = [
            path
            for path in _safe_payload_files(payload)
            if path.suffix.casefold() in {".exe", ".dll", ".sys"}
        ]
        provenance_native_paths: set[str] = set()
        for path in packaged_native:
            relative = path.relative_to(payload).as_posix()
            if relative.casefold().startswith(PYTHON_RUNTIME_PREFIX):
                record = python_runtime_index.get(relative.casefold())
                if record is None:
                    raise ReleaseError(f"Packaged Python runtime binary has no runtime record: {relative}")
                if record["bytes"] != path.stat().st_size or record["sha256"] != sha256_file(path):
                    raise ReleaseError(f"Packaged Python runtime binary differs from runtime record: {relative}")
                continue
            record = indexed.get(relative.casefold())
            if record is None:
                raise ReleaseError(f"Packaged native binary has no provenance record: {relative}")
            if record["bytes"] != path.stat().st_size or record["sha256"] != sha256_file(path):
                raise ReleaseError(f"Packaged native binary differs from provenance: {relative}")
            provenance_native_paths.add(relative.casefold())
        native_paths = provenance_native_paths
        if set(indexed) != native_paths:
            missing = sorted(native_paths - set(indexed))
            extra = sorted(set(indexed) - native_paths)
            raise ReleaseError(
                "Binary provenance and packaged native file sets differ "
                f"(missing={missing[:1]}, extra={extra[:1]})."
            )

        file_records = [
            {
                "path": path.relative_to(payload).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in _safe_payload_files(payload)
        ]
        rights_relative = "config/redistribution-rights.json"
        rights_path = payload / rights_relative
        if not rights_path.is_file():
            raise ReleaseError("The packaged redistribution-rights record is missing.")
        redistribution_rights_record = {
            "path": rights_relative,
            "bytes": rights_path.stat().st_size,
            "sha256": sha256_file(rights_path),
        }
        release_manifest = {
            "schema_version": 1,
            "product": PRODUCT,
            "version": version,
            "mode": MODE,
            "platform": PLATFORM,
            "architecture": ARCHITECTURE,
            "compiler_version": manifest["compiler_version"],
            "compiler_sha256": manifest["compiler_sha256"],
            "compiler_signer": manifest["compiler_signer"],
            "compile_flags": ["/x86", "/gui or /console", "/nopack", "/comp 2"],
            "compiled_targets": [
                {
                    "path": target.output,
                    "source": target.source,
                    "pragma_output": target.pragma_output,
                    "subsystem": target.subsystem,
                    "flags": list(target.flags),
                }
                for target in contract.compile_targets
            ],
            "source_commit": package_commit,
            "source_tree_clean": True,
            "binary_provenance_verified": True,
            "python_runtime": {
                "included": python_runtime_directory is not None,
                "path": "runtime/python" if python_runtime_directory is not None else None,
                "required": sorted(PYTHON_RUNTIME_REQUIRED_FILES),
                "files": python_runtime_records,
            },
            "code_signing_performed": False,
            "signing_claim": "none",
            "imgloc_redistribution_permission_acknowledged": False,
            "redistribution_rights_record": redistribution_rights_record,
            "files": file_records,
        }
        write_new(payload / "release-manifest.json", deterministic_json(release_manifest))
        assert_clean_source(repo)
        if current_commit(repo) != package_commit:
            raise ReleaseError("The source commit changed while the release payload was being assembled.")
        _write_deterministic_zip(payload, final_zip)
    return final_zip


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--action",
        required=True,
        choices=("compile-for-review", "package-reviewed"),
        help="Use the mandatory two-phase reviewed-binary workflow.",
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--mode", default=MODE, help="Only LocalRuntime is permitted.")
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--autoit-root", type=Path)
    parser.add_argument("--reviewed-binary-directory", type=Path)
    parser.add_argument("--python-runtime-directory", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.mode != MODE:
            raise ReleaseError(
                "This Python release boundary creates LocalRuntime packages only. PublicDistribution remains "
                "blocked until ImgLoc permission or a licensed replacement is independently validated."
            )
        output = args.output_directory or (args.repository_root / "artifacts" / "release")
        if args.action == "compile-for-review":
            if args.autoit_root is None:
                raise ReleaseError("--autoit-root is required for compile-for-review.")
            if args.reviewed_binary_directory is not None:
                raise ReleaseError("--reviewed-binary-directory is not valid for compile-for-review.")
            if args.python_runtime_directory is not None:
                raise ReleaseError("--python-runtime-directory is not valid for compile-for-review.")
            result = compile_for_review(args.repository_root, args.autoit_root, args.version, output)
            print(f"Compiled review candidates: {result}")
        else:
            if args.reviewed_binary_directory is None:
                raise ReleaseError("--reviewed-binary-directory is required for package-reviewed.")
            if args.autoit_root is not None:
                raise ReleaseError("--autoit-root is not valid for package-reviewed.")
            result = package_reviewed(
                args.repository_root,
                args.reviewed_binary_directory,
                args.version,
                output,
                python_runtime_directory=args.python_runtime_directory,
            )
            print(f"Release package: {result}")
            print(f"SHA-256: {sha256_file(result)}")
        return 0
    except ReleaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
