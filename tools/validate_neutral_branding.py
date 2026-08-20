#!/usr/bin/env python3
"""Fail closed when published text retains prohibited technology-origin branding."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_BYTES = 8 * 1024 * 1024
PUBLISH_EXCLUDE_GLOBS = ("*_HANDOFF_PROMPT.md",)


def _ascii_hex(value: str) -> str:
    return bytes.fromhex(value).decode("ascii")


# Encoded construction keeps this validator eligible to validate its own source.
PROHIBITED_CASEFOLD = tuple(
    _ascii_hex(value)
    for value in (
        "63 6f 64 65 78",
        "63 6c 61 75 64 65",
        "63 68 61 74 67 70 74",
        "6f 70 65 6e 61 69",
        "61 72 74 69 66 69 63 69 61 6c 20 69 6e 74 65 6c 6c 69 67 65 6e 63 65",
    )
)
PROHIBITED_ACRONYM = "".join(chr(value) for value in (65, 73))
# Treat Base64 alphabet and padding as identifier characters so encoded image/XML payloads do not
# become false wording findings merely because two decoded-unrelated bytes happen to be adjacent.
ACRONYM_RE = re.compile(rf"(?<![A-Za-z0-9_+/=]){PROHIBITED_ACRONYM}(?![A-Za-z0-9_+/=])")
MODEL_ORIGIN_ACRONYM = _ascii_hex("6c 6c 6d").upper()
MODEL_ORIGIN_RE = re.compile(rf"(?<![A-Za-z0-9_+/=]){MODEL_ORIGIN_ACRONYM}(?![A-Za-z0-9_+/=])", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--include-untracked", action="store_true")
    parser.add_argument("--json", type=Path, dest="json_path")
    return parser.parse_args()


def _decode_text(path: Path) -> str | None:
    try:
        payload = path.read_bytes()
    except OSError:
        raise
    if len(payload) > MAX_TEXT_BYTES:
        return None
    if payload.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return payload.decode("utf-16")
        except UnicodeDecodeError:
            return None
    if b"\x00" in payload:
        return None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _is_publish_excluded(relative: str) -> bool:
    return any(fnmatch.fnmatch(relative.casefold(), pattern.casefold()) for pattern in PUBLISH_EXCLUDE_GLOBS)


def _repository_files(root: Path, include_untracked: bool = False) -> list[Path]:
    command = ["git", "ls-files", "-z", "--cached"]
    if include_untracked:
        command.extend(("--others", "--exclude-standard"))
    proc = subprocess.run(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace").strip() or "git ls-files failed")
    files: list[Path] = []
    resolved_root = root.resolve()
    for raw in proc.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8", errors="strict").replace("\\", "/")
        if _is_publish_excluded(relative):
            continue
        candidate = (root / relative).resolve(strict=False)
        if candidate != resolved_root and resolved_root not in candidate.parents:
            raise RuntimeError(f"tracked path escapes repository: {relative}")
        if candidate.is_file():
            files.append(candidate)
    return sorted(files)


def _package_files(root: Path) -> list[Path]:
    resolved_root = root.resolve(strict=True)
    files: list[Path] = []
    for candidate in sorted(resolved_root.rglob("*")):
        if candidate.is_symlink():
            raise RuntimeError(f"package contains a symbolic link: {candidate.relative_to(resolved_root).as_posix()}")
        if candidate.is_file():
            files.append(candidate)
    return files


def _path_findings(relative: str) -> list[str]:
    folded = relative.casefold()
    findings = ["brand-term" for word in PROHIBITED_CASEFOLD if word.casefold() in folded]
    if ACRONYM_RE.search(relative) or MODEL_ORIGIN_RE.search(relative):
        findings.append("technology-origin")
    return sorted(set(findings))


def scan_paths(root: Path, paths: list[Path]) -> dict[str, object]:
    resolved_root = root.resolve()
    findings: list[dict[str, object]] = []
    scanned_text = 0
    skipped_binary = 0
    for path in paths:
        relative = path.relative_to(resolved_root).as_posix()
        path_kinds = _path_findings(relative)
        if path_kinds:
            findings.append({"path": relative, "line": 0, "kinds": path_kinds, "surface": "path"})
        text = _decode_text(path)
        if text is None:
            skipped_binary += 1
            continue
        scanned_text += 1
        for line_number, line in enumerate(text.splitlines(), start=1):
            folded = line.casefold()
            kinds = ["brand-term" for word in PROHIBITED_CASEFOLD if word.casefold() in folded]
            if ACRONYM_RE.search(line) or MODEL_ORIGIN_RE.search(line):
                kinds.append("technology-origin")
            if kinds:
                findings.append(
                    {
                        "path": relative,
                        "line": line_number,
                        "kinds": sorted(set(kinds)),
                        "surface": "content",
                    }
                )
    return {
        "schema_version": 1,
        "root": str(resolved_root),
        "files": len(paths),
        "text_files": scanned_text,
        "binary_or_oversize_files": skipped_binary,
        "findings": findings,
        "errors": [],
    }


def build_report(
    repository_root: Path,
    package_root: Path | None = None,
    include_untracked: bool = False,
) -> dict[str, object]:
    if package_root is None:
        root = repository_root.resolve(strict=True)
        report = scan_paths(root, _repository_files(root, include_untracked))
        report["mode"] = "publish-candidate-tree" if include_untracked else "tracked-tree"
        return report
    root = package_root.resolve(strict=True)
    report = scan_paths(root, _package_files(root))
    report["mode"] = "extracted-package"
    return report


def main() -> int:
    args = parse_args()
    try:
        report = build_report(args.repository_root, args.package_root, args.include_untracked)
    except (OSError, RuntimeError, UnicodeError) as exc:
        print(f"neutral-branding validation failed: {exc}", file=sys.stderr)
        return 2
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Neutral-branding audit: {report['files']} files, {report['text_files']} text, "
        f"{len(report['findings'])} findings"
    )
    for finding in report["findings"]:
        print(f"ERROR: {finding['path']}:{finding['line']} ({','.join(finding['kinds'])})")
    return 1 if report["findings"] or report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
