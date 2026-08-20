#!/usr/bin/env python3
"""Fail closed when an AutoIt actuator owner is unclassified.

The scanner intentionally works at the direct-owner boundary: every intended
tracked or untracked non-test AutoIt function that calls a game-input,
process-control, or dynamic-dispatch sink must match exactly one registry rule.
A canonical owner/sink fingerprint pins the reviewed source set, so a newly
added call fails even when it happens to match a broad path rule.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "actuator-registry.json"
FUNC_DEF_RE = re.compile(r"^\s*Func\s+([A-Za-z_]\w*)\s*\(", re.IGNORECASE)
FUNC_END_RE = re.compile(r"^\s*EndFunc\b", re.IGNORECASE)
CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
DYNAMIC_DISPATCH_RE = re.compile(r"(?<![A-Za-z0-9_])Call\s*\(", re.IGNORECASE)
LITERAL_DYNAMIC_TARGET_RE = re.compile(r"\s*([\"'])([A-Za-z_]\w*)\1\s*(?:,|\))", re.IGNORECASE)
STRING_RE = re.compile(r'"(?:[^"]|"")*"' + r"|'(?:[^']|'')*'")
POLICIES = {"capability", "blocked", "infrastructure", "test-only"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="store_true", help="print the canonical owner inventory")
    parser.add_argument("--json", action="store_true", help="emit the validation report as JSON")
    return parser.parse_args()


def _inventory_autoit_paths() -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.au3"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace").strip() or "git ls-files failed")
    result: list[Path] = []
    for raw in proc.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8", errors="strict").replace("\\", "/")
        if relative.startswith("tests/"):
            continue
        path = ROOT / relative
        if path.is_file():
            result.append(path)
    return sorted(result)


def _masked_strings(line: str) -> str:
    """Preserve offsets while hiding string contents from token matching."""
    return STRING_RE.sub(lambda match: " " * len(match.group(0)), line)


def _line_sinks(uncommented: str, folded_sinks: dict[str, str]) -> set[str]:
    masked = _masked_strings(uncommented)
    found: set[str] = set()
    for match in CALL_RE.finditer(masked):
        canonical = folded_sinks.get(match.group(1).casefold())
        if canonical:
            found.add(canonical)
    dynamic_sink = folded_sinks.get("dynamiccall")
    for match in DYNAMIC_DISPATCH_RE.finditer(masked):
        if dynamic_sink:
            found.add(dynamic_sink)
        target = LITERAL_DYNAMIC_TARGET_RE.match(uncommented, match.end())
        if target:
            canonical = folded_sinks.get(target.group(2).casefold())
            if canonical:
                found.add(canonical)
    return found


def _without_comment(line: str) -> str:
    """Remove an AutoIt trailing comment without treating semicolons in strings as comments."""
    quote = ""
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == quote:
                if index + 1 < len(line) and line[index + 1] == quote:
                    index += 2
                    continue
                quote = ""
        elif char in {'"', "'"}:
            quote = char
        elif char == ";":
            return line[:index]
        index += 1
    return line


def _canonical_inventory(owners: dict[str, set[str]]) -> tuple[list[str], str]:
    lines = [f"{owner}={'|'.join(sorted(sinks, key=str.casefold))}" for owner, sinks in sorted(owners.items())]
    digest = hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
    return lines, digest


def scan_owners(sink_names: set[str]) -> tuple[dict[str, set[str]], list[dict[str, object]]]:
    folded_sinks = {name.casefold(): name for name in sink_names}
    owners: dict[str, set[str]] = defaultdict(set)
    sites: list[dict[str, object]] = []
    for path in _inventory_autoit_paths():
        relative = path.relative_to(ROOT).as_posix()
        function = "<top-level>"
        in_block_comment = False
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            directive = raw_line.strip().casefold()
            if directive.startswith("#cs") or directive.startswith("#comments-start"):
                in_block_comment = True
                continue
            if directive.startswith("#ce") or directive.startswith("#comments-end"):
                in_block_comment = False
                continue
            if in_block_comment:
                continue

            uncommented = _without_comment(raw_line)
            definition = FUNC_DEF_RE.match(uncommented)
            if definition:
                function = definition.group(1)
                continue
            if FUNC_END_RE.match(uncommented):
                function = "<top-level>"
                continue

            found = _line_sinks(uncommented, folded_sinks)
            if not found:
                continue
            owner = f"{relative}::{function}"
            owners[owner].update(found)
            sites.append(
                {
                    "owner": owner,
                    "line": line_number,
                    "sinks": sorted(found, key=str.casefold),
                }
            )
    return dict(owners), sites


def _rule_matches(rule: dict[str, object], owner: str) -> bool:
    path, function = owner.rsplit("::", 1)
    path_globs = rule.get("path_globs", [])
    function_globs = rule.get("function_globs", ["*"])
    if not isinstance(path_globs, list) or not isinstance(function_globs, list):
        return False
    return any(fnmatch.fnmatchcase(path, str(pattern)) for pattern in path_globs) and any(
        fnmatch.fnmatchcase(function, str(pattern)) for pattern in function_globs
    )


def build_report() -> dict[str, object]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
    errors: list[str] = []
    warnings: list[str] = []
    sink_groups = registry.get("sink_groups", {})
    if not isinstance(sink_groups, dict):
        raise ValueError("sink_groups must be an object")
    sink_names = {
        str(name)
        for values in sink_groups.values()
        if isinstance(values, list)
        for name in values
    }
    if not sink_names:
        errors.append("registry has no actuator sink functions")

    owners, sites = scan_owners(sink_names)
    inventory, digest = _canonical_inventory(owners)
    expected = registry.get("owner_fingerprint", {})
    if expected.get("count") != len(owners):
        errors.append(f"owner count drifted: expected {expected.get('count')!r}, found {len(owners)}")
    if expected.get("sha256") != digest:
        errors.append(f"owner fingerprint drifted: expected {expected.get('sha256')!r}, found {digest}")

    capabilities = json.loads(
        (ROOT / "config" / "current-client-capabilities.json").read_text(encoding="utf-8-sig")
    )
    capability_ids = {item.get("id") for item in capabilities.get("capabilities", []) if isinstance(item, dict)}
    rules = registry.get("mappings", [])
    if not isinstance(rules, list):
        errors.append("mappings must be an array")
        rules = []

    rule_hits: dict[str, int] = defaultdict(int)
    classifications: dict[str, dict[str, object]] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            errors.append("every mapping must be an object")
            continue
        rule_id = str(rule.get("id", ""))
        policy = rule.get("policy")
        if not rule_id:
            errors.append("mapping id must be non-empty")
            continue
        if policy not in POLICIES:
            errors.append(f"{rule_id}: invalid policy {policy!r}")
        mapped_capabilities = rule.get("capability_ids", [])
        if not isinstance(mapped_capabilities, list):
            errors.append(f"{rule_id}: capability_ids must be an array")
            mapped_capabilities = []
        unknown = sorted(set(mapped_capabilities) - capability_ids)
        if unknown:
            errors.append(f"{rule_id}: unknown capability ids: {unknown}")
        if policy == "capability" and not mapped_capabilities:
            errors.append(f"{rule_id}: capability policy requires capability_ids")
        if not str(rule.get("reason", "")).strip():
            errors.append(f"{rule_id}: reason must be non-empty")

    for owner in sorted(owners):
        matching = [rule for rule in rules if isinstance(rule, dict) and _rule_matches(rule, owner)]
        if not matching:
            errors.append(f"unowned actuator: {owner} -> {sorted(owners[owner])}")
            continue
        if len(matching) != 1:
            errors.append(f"ambiguous actuator mapping: {owner} -> {[rule.get('id') for rule in matching]}")
            continue
        rule = matching[0]
        rule_id = str(rule.get("id"))
        rule_hits[rule_id] += 1
        classifications[owner] = {
            "sinks": sorted(owners[owner], key=str.casefold),
            "mapping": rule_id,
            "policy": rule.get("policy"),
            "capability_ids": rule.get("capability_ids", []),
        }
        if "GemClick" in owners[owner] and rule.get("policy") not in {"blocked", "infrastructure"}:
            errors.append(f"gem actuator must be blocked or infrastructure-only: {owner}")

    for rule in rules:
        if isinstance(rule, dict) and rule.get("id") and rule_hits[str(rule["id"])] == 0:
            errors.append(f"mapping matches no reviewed owner: {rule['id']}")

    owner_policy_counts = Counter(
        str(classification.get("policy", "unclassified"))
        for classification in classifications.values()
    )
    owner_policy_counts["unclassified"] = len(owners) - len(classifications)
    mapping_policy_counts = Counter(
        str(rule.get("policy", "invalid")) for rule in rules if isinstance(rule, dict)
    )

    return {
        "schema_version": 1,
        "registry": REGISTRY_PATH.relative_to(ROOT).as_posix(),
        "owners": len(owners),
        "sites": len(sites),
        "sink_functions": len(sink_names),
        "fingerprint": digest,
        "owner_policy_counts": dict(sorted(owner_policy_counts.items())),
        "mapping_policy_counts": dict(sorted(mapping_policy_counts.items())),
        "inventory": inventory,
        "classifications": classifications,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    args = parse_args()
    try:
        report = build_report()
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"actuator registry validation failed: {exc}", file=sys.stderr)
        return 2
    if args.json or args.inventory:
        if not args.inventory:
            report = {key: value for key, value in report.items() if key not in {"inventory", "classifications"}}
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"Actuator registry: {report['owners']} owners, {report['sites']} sites, "
            f"{report['sink_functions']} sinks, "
            f"{report['owner_policy_counts'].get('capability', 0)} capability-owned, "
            f"{report['owner_policy_counts'].get('blocked', 0)} blocked, "
            f"{len(report['errors'])} errors, "
            f"{len(report['warnings'])} warnings"
        )
        for error in report["errors"]:
            print(f"ERROR: {error}")
        for warning in report["warnings"]:
            print(f"WARNING: {warning}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
