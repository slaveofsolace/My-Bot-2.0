#!/usr/bin/env python3
"""Static repository checks for the My Bot 2.0 integration branch.

The script uses only the Python standard library so it can run locally and in
GitHub Actions without installing project dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

MAX_TEXT_BYTES = 5 * 1024 * 1024

TEXT_SUFFIXES = {
    ".au3",
    ".bat",
    ".cmd",
    ".config",
    ".csv",
    ".ini",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

BINARY_SUFFIXES = {
    ".7z",
    ".apk",
    ".dll",
    ".exe",
    ".jar",
    ".rar",
    ".so",
    ".sys",
    ".zip",
}

BINARY_PROVENANCE_PATH = "config/binary-provenance.json"

REQUIRED_PATHS = (
    "README.md",
    "License.txt",
    "My Bot 2.0.au3",
    "My Bot 2.0.exe",
    "MyBot.run.au3",
    "MyBot.run.exe.config",
    "MyBot.run.EngineProbe.exe.config",
    "MyBot.run.txt",
    "MyBot.run.version.au3",
    "upstreams.lock.json",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "docs/README.md",
    "docs/audit/BASELINE_AUDIT_2026-08-06.md",
    "docs/compatibility/GAME_UPDATE_MATRIX.md",
    "docs/architecture/REPOSITORY_PLAN.md",
    "docs/development/MERGE_PLAYBOOK.md",
    "docs/ui/UI_HANDOFF.md",
    "docs/INSTALL.md",
    BINARY_PROVENANCE_PATH,
    "config/ui/run-planner.presets.json",
    "tools/check_town_hall_presets.py",
    "tools/build_release.py",
    "tools/install_local_runtime.py",
    "tools/run_supervised_battle_acceptance.ps1",
    "tools/validate_translation_keys.py",
    "ui/planner.html",
    ".github/workflows/ci.yml",
    ".github/workflows/windows-autoit.yml",
)

REQUIRED_EMPTY_PATHS = (
    "MyBot.run.txt",
)

REQUIRED_UPSTREAM_IDS = {
    "mybotrun-v8",
    "xbebenk-mod",
    "clash-autoloot",
    "canmurat-lineage-check",
}

INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"', re.IGNORECASE)
PRODUCT_VERSION_RE = re.compile(r'Global\s+Const\s+\$g_sProductVersion\s*=\s*"([^"]+)"')
ENGINE_VERSION_RE = re.compile(r'Global\s+Const\s+\$g_sEngineVersion\s*=\s*"([^"]+)"')

SECRET_PATTERNS = (
    (
        "private-key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,255}\b")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("generic-api-key", re.compile(r"\bsk-[A-Za-z0-9]{24,}\b")),
)


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str
    path: str | None = None
    line: int | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run static integrity and provenance checks for the repository."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to the parent of tools/.",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        type=Path,
        help="Write the complete report to this JSON file.",
    )
    return parser.parse_args()


def repository_files(root: Path) -> list[Path]:
    """Return files that could be published, excluding ignored local state.

    Git owns the repository's include/exclude rules.  Asking it for tracked and
    untracked non-ignored paths keeps profiles, screenshots, dependency installs,
    and temporary binaries out of both metrics and secret scanning.  Required
    packaged artifacts are added explicitly because the inherited ``*.exe``
    ignore rule deliberately hides locally rebuilt deliverables.
    """

    files: set[Path] = set()
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            check=True,
            capture_output=True,
        )
        for raw_path in result.stdout.split(b"\0"):
            if not raw_path:
                continue
            path = root / Path(os.fsdecode(raw_path))
            if path.is_file():
                files.add(path)
    except (OSError, subprocess.CalledProcessError):
        # Source archives have no Git metadata and normally contain only files
        # selected for publication, so retain a bounded archive-compatible path.
        for path in root.rglob("*"):
            if ".git" not in path.parts and path.is_file():
                files.add(path)

    for required in REQUIRED_PATHS:
        path = root / required
        if path.is_file():
            files.add(path)

    return sorted(files, key=lambda item: relative_path(root, item).casefold())


def relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            return None
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None


def casefold_index(root: Path, files: Iterable[Path]) -> dict[str, str]:
    return {
        relative_path(root, path).replace("\\", "/").casefold(): relative_path(root, path)
        for path in files
    }


def normalize_candidate(root: Path, candidate: Path) -> str | None:
    try:
        return candidate.resolve(strict=False).relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def include_candidates(root: Path, source: Path, include_value: str) -> list[str]:
    include_path = Path(include_value.replace("\\", "/"))
    candidates = [source.parent / include_path, root / include_path]

    # A number of legacy modules refer to paths relative to COCBot even when the
    # including file is nested more deeply. Keep that Windows-era behavior
    # explicit instead of assuming Linux path resolution.
    candidates.append(root / "COCBot" / include_path)

    normalized: list[str] = []
    for candidate in candidates:
        value = normalize_candidate(root, candidate)
        if value is not None and value not in normalized:
            normalized.append(value)
    return normalized


def check_required_paths(root: Path, findings: list[Finding]) -> None:
    for required in REQUIRED_PATHS:
        if not (root / required).is_file():
            findings.append(
                Finding(
                    "error",
                    "required-path-missing",
                    f"Required project file is missing: {required}",
                    required,
                )
            )

    for required in REQUIRED_EMPTY_PATHS:
        path = root / required
        if path.is_file() and path.stat().st_size != 0:
            findings.append(
                Finding(
                    "error",
                    "required-empty-path-modified",
                    f"Compatibility marker must remain empty: {required}",
                    required,
                )
            )


def check_upstream_lock(root: Path, findings: list[Finding], metrics: dict[str, object]) -> None:
    lock_path = root / "upstreams.lock.json"
    if not lock_path.is_file():
        return

    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(
            Finding(
                "error",
                "upstream-lock-invalid",
                f"upstreams.lock.json cannot be parsed: {exc}",
                "upstreams.lock.json",
            )
        )
        return

    sources = data.get("sources")
    if not isinstance(sources, list):
        findings.append(
            Finding(
                "error",
                "upstream-lock-shape",
                "upstreams.lock.json must contain a sources array.",
                "upstreams.lock.json",
            )
        )
        return

    ids: list[str] = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            findings.append(
                Finding(
                    "error",
                    "upstream-entry-shape",
                    f"Source entry {index} is not an object.",
                    "upstreams.lock.json",
                )
            )
            continue

        source_id = source.get("id")
        commit = source.get("commit")
        repository = source.get("repository")
        import_policy = source.get("importPolicy")

        if isinstance(source_id, str):
            ids.append(source_id)
        else:
            findings.append(
                Finding(
                    "error",
                    "upstream-id-missing",
                    f"Source entry {index} has no string id.",
                    "upstreams.lock.json",
                )
            )

        if not isinstance(repository, str) or "/" not in repository:
            findings.append(
                Finding(
                    "error",
                    "upstream-repository-invalid",
                    f"Source entry {source_id or index} has an invalid repository.",
                    "upstreams.lock.json",
                )
            )

        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            findings.append(
                Finding(
                    "error",
                    "upstream-commit-invalid",
                    f"Source entry {source_id or index} must pin a full lowercase 40-character commit SHA.",
                    "upstreams.lock.json",
                )
            )

        if not isinstance(import_policy, str) or not import_policy.strip():
            findings.append(
                Finding(
                    "error",
                    "upstream-policy-missing",
                    f"Source entry {source_id or index} has no import policy.",
                    "upstreams.lock.json",
                )
            )

    duplicate_ids = sorted(value for value, count in Counter(ids).items() if count > 1)
    if duplicate_ids:
        findings.append(
            Finding(
                "error",
                "upstream-id-duplicate",
                f"Duplicate upstream ids: {', '.join(duplicate_ids)}",
                "upstreams.lock.json",
            )
        )

    missing_ids = sorted(REQUIRED_UPSTREAM_IDS.difference(ids))
    if missing_ids:
        findings.append(
            Finding(
                "error",
                "upstream-required-missing",
                f"Required upstream records are missing: {', '.join(missing_ids)}",
                "upstreams.lock.json",
            )
        )

    metrics["upstreamSources"] = len(sources)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_iso_date(value: object) -> bool:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _git_commit_exists(root: Path, commit: str) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", f"{commit}^{{commit}}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return None
    return result.returncode == 0


def _git_object_exists(root: Path, object_spec: str) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", object_spec],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return None
    return result.returncode == 0


def _git_is_ancestor(root: Path, ancestor: str, descendant: str) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, descendant],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return None
    return result.returncode == 0


def check_binary_provenance(
    root: Path, files: list[Path], findings: list[Finding], metrics: dict[str, object]
) -> None:
    manifest_path = root / BINARY_PROVENANCE_PATH
    if not manifest_path.is_file():
        return

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(
            Finding(
                "error",
                "binary-provenance-invalid",
                f"Binary provenance manifest cannot be parsed: {exc}",
                BINARY_PROVENANCE_PATH,
            )
        )
        return

    if not isinstance(data, dict):
        findings.append(
            Finding(
                "error",
                "binary-provenance-shape",
                "Binary provenance manifest must be a JSON object.",
                BINARY_PROVENANCE_PATH,
            )
        )
        return

    if data.get("schema_version") != 1:
        findings.append(
            Finding(
                "error",
                "binary-provenance-schema",
                "Binary provenance manifest must use schema_version 1.",
                BINARY_PROVENANCE_PATH,
            )
        )

    reviewed_at = data.get("reviewed_at")
    if not _is_iso_date(reviewed_at):
        findings.append(
            Finding(
                "error",
                "binary-provenance-reviewed-date",
                "Binary provenance manifest must have a valid reviewed_at date.",
                BINARY_PROVENANCE_PATH,
            )
        )

    entries = data.get("artifacts")
    if not isinstance(entries, list):
        findings.append(
            Finding(
                "error",
                "binary-provenance-shape",
                "Binary provenance manifest must contain an artifacts array.",
                BINARY_PROVENANCE_PATH,
            )
        )
        return

    actual = {
        relative_path(root, path)
        for path in files
        if path.suffix.casefold() in BINARY_SUFFIXES
    }
    publishable = {relative_path(root, path) for path in files}
    declared: dict[str, int] = {}
    valid: set[str] = set()
    commit_checks: dict[str, bool | None] = {}
    commit_path_checks: dict[tuple[str, str], bool | None] = {}
    ancestry_checks: dict[tuple[str, str], bool | None] = {}
    locked_commits: dict[str, str] = {}
    try:
        lock_data = json.loads((root / "upstreams.lock.json").read_text(encoding="utf-8"))
        for source in lock_data.get("sources", []):
            if isinstance(source, dict) and isinstance(source.get("id"), str) and isinstance(source.get("commit"), str):
                locked_commits[source["id"]] = source["commit"]
    except (OSError, json.JSONDecodeError, AttributeError):
        pass

    for index, entry in enumerate(entries):
        entry_valid = True
        if not isinstance(entry, dict):
            findings.append(
                Finding(
                    "error",
                    "binary-provenance-entry-shape",
                    f"Binary provenance entry {index} is not an object.",
                    BINARY_PROVENANCE_PATH,
                )
            )
            continue

        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            findings.append(
                Finding(
                    "error",
                    "binary-provenance-path",
                    f"Binary provenance entry {index} has no path.",
                    BINARY_PROVENANCE_PATH,
                )
            )
            continue

        candidate = Path(raw_path)
        if candidate.is_absolute() or ".." in candidate.parts or candidate.as_posix() != raw_path:
            findings.append(
                Finding(
                    "error",
                    "binary-provenance-path",
                    f"Binary provenance path must be a normalized repository-relative path: {raw_path}",
                    BINARY_PROVENANCE_PATH,
                )
            )
            continue

        if raw_path in declared:
            findings.append(
                Finding(
                    "error",
                    "binary-provenance-duplicate",
                    f"Binary provenance path is duplicated: {raw_path}",
                    BINARY_PROVENANCE_PATH,
                )
            )
            continue
        declared[raw_path] = index

        artifact_path = root / candidate
        expected_hash = entry.get("sha256")
        expected_bytes = entry.get("bytes")
        hash_valid = isinstance(expected_hash, str) and re.fullmatch(r"[0-9a-f]{64}", expected_hash) is not None
        if not hash_valid:
            findings.append(
                Finding(
                    "error",
                    "binary-provenance-hash-shape",
                    f"Binary provenance entry has an invalid SHA-256: {raw_path}",
                    BINARY_PROVENANCE_PATH,
                )
            )
            entry_valid = False
        if not isinstance(expected_bytes, int) or isinstance(expected_bytes, bool) or expected_bytes < 0:
            findings.append(
                Finding(
                    "error",
                    "binary-provenance-size-shape",
                    f"Binary provenance entry has an invalid byte size: {raw_path}",
                    BINARY_PROVENANCE_PATH,
                )
            )
            entry_valid = False

        if not artifact_path.is_file():
            findings.append(
                Finding(
                    "error",
                    "binary-provenance-file-missing",
                    f"Provenanced artifact is missing: {raw_path}",
                    raw_path,
                )
            )
            entry_valid = False
        else:
            if isinstance(expected_bytes, int) and not isinstance(expected_bytes, bool):
                if artifact_path.stat().st_size != expected_bytes:
                    findings.append(
                        Finding(
                            "error",
                            "binary-provenance-size-mismatch",
                            f"Provenanced artifact size changed: {raw_path}",
                            raw_path,
                        )
                    )
                    entry_valid = False
            if hash_valid:
                try:
                    actual_hash = _sha256(artifact_path)
                except OSError as exc:
                    findings.append(
                        Finding(
                            "error",
                            "binary-provenance-read-failed",
                            f"Could not hash {raw_path}: {exc}",
                            raw_path,
                        )
                    )
                    entry_valid = False
                else:
                    if actual_hash != expected_hash:
                        findings.append(
                            Finding(
                                "error",
                                "binary-provenance-hash-mismatch",
                                f"Provenanced artifact hash changed: {raw_path}",
                                raw_path,
                            )
                        )
                        entry_valid = False

        provenance = entry.get("provenance")
        if not isinstance(provenance, dict):
            findings.append(
                Finding(
                    "error",
                    "binary-provenance-origin-shape",
                    f"Binary provenance origin is missing: {raw_path}",
                    BINARY_PROVENANCE_PATH,
                )
            )
            entry_valid = False
        else:
            kind = provenance.get("kind")
            if kind == "inherited-repository":
                source_id = provenance.get("source_id")
                if not isinstance(source_id, str) or source_id != "mybotrun-v8":
                    findings.append(
                        Finding(
                            "error",
                            "binary-provenance-source",
                            f"Inherited baseline artifact must use source_id mybotrun-v8: {raw_path}",
                            BINARY_PROVENANCE_PATH,
                        )
                    )
                    entry_valid = False
                introduced_commit = provenance.get("introduced_commit")
                commit_valid = (
                    isinstance(introduced_commit, str)
                    and re.fullmatch(r"[0-9a-f]{40}", introduced_commit) is not None
                )
                if not commit_valid:
                    findings.append(
                        Finding(
                            "error",
                            "binary-provenance-introduced-commit",
                            f"Inherited artifact has no full introduced_commit: {raw_path}",
                            BINARY_PROVENANCE_PATH,
                        )
                    )
                    entry_valid = False
                else:
                    if introduced_commit not in commit_checks:
                        commit_checks[introduced_commit] = _git_commit_exists(root, introduced_commit)
                    if commit_checks[introduced_commit] is False:
                        findings.append(
                            Finding(
                                "error",
                                "binary-provenance-commit-missing",
                                f"Introduced commit is not present in repository history: {raw_path}",
                                BINARY_PROVENANCE_PATH,
                            )
                        )
                        entry_valid = False
                    path_key = (introduced_commit, raw_path)
                    if path_key not in commit_path_checks:
                        commit_path_checks[path_key] = _git_object_exists(root, f"{introduced_commit}:{raw_path}")
                    if commit_path_checks[path_key] is False:
                        findings.append(
                            Finding(
                                "error",
                                "binary-provenance-path-history",
                                f"Artifact path did not exist at its introduced commit: {raw_path}",
                                BINARY_PROVENANCE_PATH,
                            )
                        )
                        entry_valid = False
                    locked_commit = locked_commits.get(source_id) if isinstance(source_id, str) else None
                    if isinstance(locked_commit, str) and re.fullmatch(r"[0-9a-f]{40}", locked_commit):
                        ancestry_key = (introduced_commit, locked_commit)
                        if ancestry_key not in ancestry_checks:
                            ancestry_checks[ancestry_key] = _git_is_ancestor(root, introduced_commit, locked_commit)
                        if ancestry_checks[ancestry_key] is False:
                            findings.append(
                                Finding(
                                    "error",
                                    "binary-provenance-history",
                                    f"Introduced commit is outside the locked upstream history: {raw_path}",
                                    BINARY_PROVENANCE_PATH,
                                )
                            )
                            entry_valid = False
            elif kind == "local-build":
                source = provenance.get("source")
                source_path = Path(source) if isinstance(source, str) else None
                expected_source = candidate.with_suffix(".au3").as_posix()
                if (
                    source_path is None
                    or not source
                    or source_path.is_absolute()
                    or ".." in source_path.parts
                    or source_path.as_posix() != source
                    or source != expected_source
                    or source not in publishable
                    or not (root / source_path).is_file()
                ):
                    findings.append(
                        Finding(
                            "error",
                            "binary-provenance-build-source",
                            f"Local build source is missing: {raw_path}",
                            BINARY_PROVENANCE_PATH,
                        )
                    )
                    entry_valid = False
                for field in ("toolchain", "tool_version", "tool_signer"):
                    if not isinstance(provenance.get(field), str) or not provenance[field].strip():
                        findings.append(
                            Finding(
                                "error",
                                "binary-provenance-toolchain",
                                f"Local build is missing {field}: {raw_path}",
                                BINARY_PROVENANCE_PATH,
                            )
                        )
                        entry_valid = False
                built_at = provenance.get("built_at")
                if not _is_iso_date(built_at):
                    findings.append(
                        Finding(
                            "error",
                            "binary-provenance-build-date",
                            f"Local build has an invalid built_at date: {raw_path}",
                            BINARY_PROVENANCE_PATH,
                        )
                    )
                    entry_valid = False
            else:
                findings.append(
                    Finding(
                        "error",
                        "binary-provenance-kind",
                        f"Binary provenance kind is unsupported for {raw_path}: {kind!r}",
                        BINARY_PROVENANCE_PATH,
                    )
                )
                entry_valid = False

        if entry_valid:
            valid.add(raw_path)

    missing = sorted(actual.difference(declared))
    extra = sorted(set(declared).difference(actual))
    if missing:
        findings.append(
            Finding(
                "error",
                "binary-provenance-missing",
                f"Binary artifacts lack provenance: {', '.join(missing)}",
                BINARY_PROVENANCE_PATH,
            )
        )
    if extra:
        findings.append(
            Finding(
                "error",
                "binary-provenance-extra",
                f"Provenance records do not match publishable artifacts: {', '.join(extra)}",
                BINARY_PROVENANCE_PATH,
            )
        )

    metrics["provenancedBinaryArtifacts"] = len(valid.intersection(actual))


def check_autoit_includes(
    root: Path,
    files: list[Path],
    path_index: dict[str, str],
    findings: list[Finding],
    metrics: dict[str, object],
) -> None:
    include_count = 0
    missing_count = 0

    for source in files:
        if source.suffix.casefold() != ".au3":
            continue
        text = read_text(source)
        if text is None:
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            match = INCLUDE_RE.match(line)
            if match is None:
                continue

            include_count += 1
            include_value = match.group(1)
            candidates = include_candidates(root, source, include_value)
            if not any(candidate.casefold() in path_index for candidate in candidates):
                missing_count += 1
                findings.append(
                    Finding(
                        "error",
                        "autoit-include-missing",
                        f"Local AutoIt include does not resolve: {include_value}",
                        relative_path(root, source),
                        line_number,
                    )
                )

    metrics["localAutoItIncludes"] = include_count
    metrics["missingAutoItIncludes"] = missing_count


def check_secrets(root: Path, files: list[Path], findings: list[Finding]) -> None:
    for path in files:
        if path.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        text = read_text(path)
        if text is None:
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            for code, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            "error",
                            f"secret-{code}",
                            f"Potential committed secret detected ({code}).",
                            relative_path(root, path),
                            line_number,
                        )
                    )


def collect_metrics(
    root: Path, files: list[Path], findings: list[Finding], metrics: dict[str, object]
) -> None:
    suffix_counts = Counter(path.suffix.casefold() or "<none>" for path in files)
    metrics["files"] = len(files)
    metrics["autoItFiles"] = suffix_counts.get(".au3", 0)
    metrics["imageFiles"] = sum(
        suffix_counts.get(suffix, 0)
        for suffix in (".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".webp")
    )

    binaries = [path for path in files if path.suffix.casefold() in BINARY_SUFFIXES]
    metrics["binaryArtifacts"] = len(binaries)

    version_path = root / "MyBot.run.version.au3"
    version_text = read_text(version_path) if version_path.is_file() else None
    if version_text:
        product_match = PRODUCT_VERSION_RE.search(version_text)
        engine_match = ENGINE_VERSION_RE.search(version_text)
        if product_match:
            metrics["productVersion"] = product_match.group(1)
        if engine_match:
            metrics["engineVersion"] = engine_match.group(1)
        if not product_match or not engine_match:
            findings.append(
                Finding(
                    "warning",
                    "version-unreadable",
                    "Could not read the product and engine versions from MyBot.run.version.au3.",
                    "MyBot.run.version.au3",
                )
            )


def build_report(root: Path) -> dict[str, object]:
    findings: list[Finding] = []
    metrics: dict[str, object] = {}
    files = repository_files(root)
    path_index = casefold_index(root, files)

    check_required_paths(root, findings)
    check_upstream_lock(root, findings, metrics)
    check_autoit_includes(root, files, path_index, findings, metrics)
    check_secrets(root, files, findings)
    collect_metrics(root, files, findings, metrics)
    check_binary_provenance(root, files, findings, metrics)

    severity_order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(
        key=lambda item: (
            severity_order.get(item.severity, 99),
            item.path or "",
            item.line or 0,
            item.code,
        )
    )

    summary = Counter(item.severity for item in findings)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root.resolve()),
        "summary": {
            "errors": summary.get("error", 0),
            "warnings": summary.get("warning", 0),
            "info": summary.get("info", 0),
        },
        "metrics": metrics,
        "findings": [asdict(item) for item in findings],
    }


def print_report(report: dict[str, object]) -> None:
    summary = report["summary"]
    metrics = report["metrics"]
    print("Repository audit")
    print(f"  Files: {metrics.get('files', 0)}")
    print(f"  AutoIt files: {metrics.get('autoItFiles', 0)}")
    print(f"  Local includes: {metrics.get('localAutoItIncludes', 0)}")
    print(f"  Missing includes: {metrics.get('missingAutoItIncludes', 0)}")
    print(f"  Binary/archive artifacts: {metrics.get('binaryArtifacts', 0)}")
    print(f"  Provenanced binaries: {metrics.get('provenancedBinaryArtifacts', 0)}")
    if "productVersion" in metrics:
        print(f"  Product version: {metrics['productVersion']}")
    if "engineVersion" in metrics:
        print(f"  Engine version: {metrics['engineVersion']}")
    print(
        "  Findings: "
        f"{summary['errors']} error(s), {summary['warnings']} warning(s), "
        f"{summary['info']} info"
    )

    for finding in report["findings"]:
        location = ""
        if finding["path"]:
            location = f" {finding['path']}"
            if finding["line"]:
                location += f":{finding['line']}"
        print(
            f"[{finding['severity'].upper()}] {finding['code']}{location}: "
            f"{finding['message']}"
        )


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        print(f"Repository root does not exist: {root}", file=sys.stderr)
        return 2

    report = build_report(root)
    print_report(report)

    if args.json_path:
        output_path = args.json_path
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"JSON report: {output_path}")

    return 1 if report["summary"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
