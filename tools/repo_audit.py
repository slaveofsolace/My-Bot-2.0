#!/usr/bin/env python3
"""Static repository checks for the My Bot 2.0 integration branch.

The script uses only the Python standard library so it can run locally and in
GitHub Actions without installing project dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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

REQUIRED_PATHS = (
    "README.md",
    "License.txt",
    "MyBot.run.au3",
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
    ".github/workflows/repository-audit.yml",
)

REQUIRED_UPSTREAM_IDS = {
    "mybotrun-v8",
    "xbebenk-mod",
    "clash-autoloot",
    "canmurat-lineage-check",
}

INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"', re.IGNORECASE)
VERSION_RE = re.compile(r'Global\s+\$g_sBotVersion\s*=\s*"([^"]+)"')

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
    files: list[Path] = []
    for path in root.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.is_file():
            files.append(path)
    return files


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
    if binaries:
        sample = ", ".join(relative_path(root, path) for path in binaries[:8])
        suffix = "" if len(binaries) <= 8 else f", and {len(binaries) - 8} more"
        findings.append(
            Finding(
                "warning",
                "binary-artifacts-present",
                f"Repository contains {len(binaries)} binary/archive artifacts: {sample}{suffix}. Track provenance before publishing new releases.",
            )
        )

    version_path = root / "MyBot.run.version.au3"
    version_text = read_text(version_path) if version_path.is_file() else None
    if version_text:
        version_match = VERSION_RE.search(version_text)
        if version_match:
            metrics["botVersion"] = version_match.group(1)
        else:
            findings.append(
                Finding(
                    "warning",
                    "bot-version-unreadable",
                    "Could not read g_sBotVersion from MyBot.run.version.au3.",
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
    if "botVersion" in metrics:
        print(f"  Bot version: {metrics['botVersion']}")
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
