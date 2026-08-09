#!/usr/bin/env python3
"""Reject translation-key collisions and duplicate English catalog entries."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "COCBot"
ENGLISH_CATALOG = ROOT / "Languages" / "English.ini"
TRANSLATION_CALL = re.compile(
    r'GetTranslatedFileIni\(\s*"((?:""|[^"])*)"\s*,\s*'
    r'"((?:""|[^"])*)"\s*,\s*"((?:""|[^"])*)"\s*(?=[,)])'
)


def autoit_string(value: str) -> str:
    return value.replace('""', '"')


def translation_literals(line: str) -> list[tuple[str, str, str, bool]]:
    calls = []
    for match in TRANSLATION_CALL.finditer(line):
        calls.append(
            (
                autoit_string(match.group(1)),
                autoit_string(match.group(2)),
                autoit_string(match.group(3)),
                line[match.end() :].lstrip().startswith(","),
            )
        )
    return calls


def assert_parser_contract() -> None:
    fixtures = {
        'GetTranslatedFileIni("Section", "Plain", "Plain text")':
            [("Section", "Plain", "Plain text", False)],
        'GetTranslatedFileIni("Section", "Greeting", "Hello %s", $sName)':
            [("Section", "Greeting", "Hello %s", True)],
        'GetTranslatedFileIni("Section", "Quoted", "Say ""hello"" to %s", $sName)':
            [("Section", "Quoted", 'Say "hello" to %s', True)],
    }
    for source, expected in fixtures.items():
        actual = translation_literals(source)
        if actual != expected:
            raise RuntimeError(f"translation-call parser regression: {source!r} -> {actual!r}")


def source_defaults() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    calls: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for path in sorted(SOURCE_ROOT.rglob("*.au3")):
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            # A few inherited translation-heavy scripts are still Windows-1252.
            text = raw.decode("cp1252")
        for line_number, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith(";"):
                continue
            for section, key, default, has_arguments in translation_literals(line):
                if default == "-1":
                    continue
                calls[(section.casefold(), key.casefold())].append(
                    {
                        "section": section,
                        "key": key,
                        "default": default,
                        "has_arguments": has_arguments,
                        "file": str(path.relative_to(ROOT)),
                        "line": line_number,
                    }
                )

    errors: list[dict[str, object]] = []
    for _, entries in sorted(calls.items()):
        defaults = sorted({str(entry["default"]) for entry in entries})
        if len(defaults) > 1:
            errors.append(
                {
                    "code": "conflicting-defaults",
                    "section": entries[0]["section"],
                    "key": entries[0]["key"],
                    "defaults": defaults,
                    "locations": entries,
                }
            )
    return errors, [entry for entries in calls.values() for entry in entries]


def english_duplicates() -> tuple[list[dict[str, object]], int]:
    text = ENGLISH_CATALOG.read_text(encoding="utf-16")
    section = ""
    entries: dict[tuple[str, str], list[tuple[str, str, int]]] = defaultdict(list)
    count = 0
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if "=" not in raw_line:
            continue
        key = raw_line.split("=", 1)[0].strip()
        entries[(section.casefold(), key.casefold())].append((section, key, line_number))
        count += 1

    errors = [
        {
            "code": "duplicate-english-key",
            "section": locations[0][0],
            "key": locations[0][1],
            "lines": [location[2] for location in locations],
        }
        for _, locations in sorted(entries.items())
        if len(locations) > 1
    ]
    return errors, count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="write the report to this path")
    args = parser.parse_args()

    assert_parser_contract()
    source_errors, calls = source_defaults()
    catalog_errors, english_entries = english_duplicates()
    report = {
        "schema_version": 1,
        "parser_contract": "passed",
        "source_calls": len(calls),
        "placeholder_argument_calls": sum(bool(call["has_arguments"]) for call in calls),
        "english_entries": english_entries,
        "errors": source_errors + catalog_errors,
    }

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
