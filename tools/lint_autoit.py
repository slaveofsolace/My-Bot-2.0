#!/usr/bin/env python3
"""Structural checks for AutoIt sources.

Au3Check only runs on Windows, so this catches the mistakes that would otherwise wait for a Windows CI job:
unbalanced blocks, ByRef parameters carrying defaults, required parameters following optional ones, duplicate
function definitions, calls to project functions that no longer exist, and uses of a g_-prefixed global that is
never declared anywhere in the tree.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Directories holding first-party code. Inherited upstream sources are checked for balance only, because their
# call graph reaches into AutoIt's standard library which is not present in this repository.
FIRST_PARTY = (
    "COCBot/functions/Run",
    "COCBot/functions/Game",
    "COCBot/functions/Other/CurrentClientCompat.au3",
    "COCBot/functions/Android/AndroidLDPlayer9.au3",
    "COCBot/functions/Android/AndroidMumu.au3",
    "COCBot/GUI/MBR GUI Design Run Planner.au3",
    "COCBot/GUI/MBR GUI Control Run Planner.au3",
    "COCBot/GUI/RunPlannerMetadata.generated.au3",
    "tests/autoit",
)

# Compiled entry points. Each has its own include graph, and a function or global defined in the repository
# but absent from a given graph is an error for that build even though it resolves fine for another.
ENTRY_POINTS = (
    "MyBot.run.au3",
    "MyBot.run.MiniGui.au3",
    "MyBot.run.Watchdog.au3",
    "MyBot.run.EngineProbe.au3",
    "tests/autoit/RunContractsTest.au3",
    "tests/autoit/GameCatalogTest.au3",
    "tests/autoit/RunEngineTest.au3",
    "tests/autoit/RunVillageReadinessTest.au3",
    "tests/autoit/PassiveCurrentArmyReadinessTest.au3",
    "tests/autoit/ManualViewportMappingTest.au3",
)

# Small standalone scripts that define local stubs of AutoIt standard UDFs (they do not include the standard
# library). Their definitions must not make a standard-library name look repository-defined.
STUB_SCRIPTS = {
    "MyBot.run.Wmi.au3",
    "MyBot.run.Watchdog.au3",
    "MyBot.run.EngineProbe.au3",
    "MyBot.run.MiniGui.au3",
}

STRING_RE = re.compile(r'"[^"]*"' + r"|'[^']*'")
FUNC_DEF_RE = re.compile(r"^\s*Func\s+([A-Za-z_]\w*)\s*\((.*)$", re.IGNORECASE)
INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"', re.IGNORECASE)
# Declarations may list several variables on one line and continue across lines, so the whole
# statement is scanned for names rather than just the first one.
GLOBAL_DECL_RE = re.compile(r"^\s*(?:Global|Local|Dim|ReDim|Const|Static|Enum)\b(.*)$", re.IGNORECASE)
GLOBAL_USE_RE = re.compile(r"\$(g_[A-Za-z_]\w*)")
VARNAME_RE = re.compile(r"\$([A-Za-z_]\w*)")
CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")

# Keywords that can precede "(" without being a call.
NON_CALL = {
    "if", "elseif", "while", "until", "return", "and", "or", "not", "then", "select", "switch",
    "case", "for", "to", "step", "in", "func", "local", "global", "dim", "redim", "const", "static",
    "byref", "exit", "continueloop", "exitloop", "with", "do", "next", "wend", "endif", "endfunc",
}

OPENERS = {
    "func": "endfunc",
    "switch": "endswitch",
    "select": "endselect",
    "with": "endwith",
    "while": "wend",
    "do": "until",
}
CLOSERS = {"endfunc", "endswitch", "endselect", "endwith", "wend", "until", "endif", "next"}


def strip_noise(line: str) -> str:
    """Remove string literals then trailing comments, so keywords inside text are not parsed as code."""
    without_strings = STRING_RE.sub('""', line)
    semi = without_strings.find(";")
    if semi >= 0:
        without_strings = without_strings[:semi]
    return without_strings.rstrip()


def is_multiline_if(code: str) -> bool:
    """True when an If opens a block, i.e. the line ends with Then and carries no trailing statement."""
    match = re.search(r"\bthen\b(.*)$", code, re.IGNORECASE)
    if not match:
        return False
    return match.group(1).strip() == ""


def split_params(raw: str) -> list[str]:
    """Split a parameter list on commas that are not nested inside brackets."""
    params, depth, current = [], 0, ""
    for char in raw:
        if char in "([":
            depth += 1
        elif char in ")]":
            if depth == 0:
                break
            depth -= 1
        if char == "," and depth == 0:
            params.append(current)
            current = ""
            continue
        current += char
    if current.strip():
        params.append(current)
    return [p.strip() for p in params if p.strip()]


def check_file(path: Path, errors: list[str]) -> tuple[set[str], set[str]]:
    """Balance-check one file and return the (definitions, calls) it contains."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    relative = path.relative_to(ROOT).as_posix()
    stack: list[tuple[str, int]] = []
    definitions: set[str] = set()
    calls: set[str] = set()
    declared_globals: set[str] = set()
    used_globals: dict[str, int] = {}
    byref_positions: dict[str, set[int]] = {}
    call_sites: list[tuple[int, str, list[str]]] = []

    # AutoIt continues a statement onto the next line with a trailing underscore. Join those first so a condition
    # split across lines is still recognised as opening a block.
    joined: list[tuple[int, str]] = []
    pending, pending_line = "", 0
    in_block_comment = False
    for number, raw_line in enumerate(text.splitlines(), start=1):
        # #cs / #ce (and their #comments-start / #comments-end spellings) fence off whole regions.
        directive = raw_line.strip().lower()
        if directive.startswith("#cs") or directive.startswith("#comments-start"):
            in_block_comment = True
            continue
        if directive.startswith("#ce") or directive.startswith("#comments-end"):
            in_block_comment = False
            continue
        if in_block_comment:
            continue

        code = strip_noise(raw_line)
        if pending:
            code = pending + " " + code.strip()
        # A continuation is a bare trailing underscore. An identifier may legitimately end in "_"
        # (for example $g_bGUIControlDisabled_), so whitespace must precede it.
        if re.search(r"(?:^|\s)_$", code.rstrip()):
            pending = code.rstrip()[:-1].rstrip()
            if not pending_line:
                pending_line = number
            continue
        joined.append((pending_line or number, code))
        pending, pending_line = "", 0
    if pending:
        joined.append((pending_line, pending))

    for number, code in joined:
        if not code.strip():
            continue

        stripped = code.strip()
        # A line may legitimately begin with "(" (a continued expression), leaving no leading keyword.
        head = stripped.split("(")[0].split()
        first = head[0].lower() if head else ""

        definition = FUNC_DEF_RE.match(code)
        if definition:
            name = definition.group(1)
            if name.lower() in {d.lower() for d in definitions}:
                errors.append(f"{relative}:{number}: duplicate function definition: {name}")
            definitions.add(name)

            params = split_params(definition.group(2))
            byref_positions[name.casefold()] = {
                index for index, param in enumerate(params) if re.match(r"^byref\b", param, re.IGNORECASE)
            }
            seen_optional = False
            for param in params:
                is_byref = bool(re.match(r"^byref\b", param, re.IGNORECASE))
                has_default = "=" in param
                if is_byref and has_default:
                    errors.append(
                        f"{relative}:{number}: ByRef parameter cannot have a default value in {name}: {param}"
                    )
                if has_default:
                    seen_optional = True
                elif seen_optional and not is_byref:
                    errors.append(
                        f"{relative}:{number}: required parameter follows an optional one in {name}: {param}"
                    )

        for match in CALL_RE.finditer(code):
            candidate = match.group(1)
            if candidate.lower() in NON_CALL:
                continue
            calls.add(candidate)
            # A Func line declares its parameters, it does not pass arguments, so it is not a call site.
            if definition:
                continue
            call_sites.append((number, candidate, split_params(code[match.end():])))

        # Track g_-prefixed globals so a use with no declaration anywhere in the tree is reported here
        # rather than by Au3Check on a Windows runner.
        declaration = GLOBAL_DECL_RE.match(code)
        if declaration:
            for name in VARNAME_RE.findall(declaration.group(1)):
                declared_globals.add(name.casefold())
        for name in GLOBAL_USE_RE.findall(code):
            used_globals.setdefault(name, number)  # original casing kept for the message

        # Block balance.
        if first == "if":
            if is_multiline_if(code):
                stack.append(("endif", number))
        elif first == "for":
            stack.append(("next", number))
        elif first in OPENERS:
            stack.append((OPENERS[first], number))
        elif first in CLOSERS:
            if not stack:
                errors.append(f"{relative}:{number}: {stripped.split()[0]} closes a block that was never opened")
            else:
                expected, opened_at = stack[-1]
                if first != expected:
                    errors.append(
                        f"{relative}:{number}: found {stripped.split()[0]} but the block opened on line {opened_at} needs {expected}"
                    )
                stack.pop()

    for expected, opened_at in stack:
        errors.append(f"{relative}:{opened_at}: block is never closed, expected {expected}")

    return definitions, calls, declared_globals, used_globals, byref_positions, call_sites


def resolve_include(source: Path, target: str) -> Path:
    return (source.parent / target.replace("\\", "/")).resolve()


def _case_index() -> dict[str, Path]:
    """Casefolded path index. AutoIt include resolution is case-insensitive; a Linux filesystem is not."""
    return {p.resolve().as_posix().casefold(): p.resolve() for p in ROOT.rglob("*.au3")}


_CASE_INDEX: dict[str, Path] | None = None


def _resolve_case_insensitive(candidate: Path) -> Path | None:
    global _CASE_INDEX
    if _CASE_INDEX is None:
        _CASE_INDEX = _case_index()
    return _CASE_INDEX.get(candidate.resolve().as_posix().casefold())


def include_graph(entry: Path) -> list[Path]:
    """Files reachable from an entry point, in load order, mirroring how AutoIt resolves #include."""
    seen: set[Path] = set()
    order: list[Path] = []

    def walk(path: Path) -> None:
        path = path.resolve()
        if path in seen or not path.exists():
            return
        seen.add(path)
        order.append(path)
        in_block_comment = False
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            # An include inside a #cs/#ce region is commented out and must not join the graph.
            directive = line.strip().lower()
            if directive.startswith("#cs") or directive.startswith("#comments-start"):
                in_block_comment = True
                continue
            if directive.startswith("#ce") or directive.startswith("#comments-end"):
                in_block_comment = False
                continue
            if in_block_comment:
                continue
            match = INCLUDE_RE.match(line)
            if not match:
                continue
            target = match.group(1).replace("\\", "/")
            for candidate in (path.parent / target, ROOT / target, ROOT / "COCBot" / target):
                resolved = _resolve_case_insensitive(candidate)
                if resolved is not None:
                    walk(resolved)
                    break

    walk(entry)
    return order


def check_entry_points(errors: list[str]) -> dict[str, int]:
    """Every project symbol a build uses must be defined somewhere in that build's own include graph."""
    repo_definitions: dict[str, set[str]] = {}
    repo_declarations: dict[str, set[str]] = {}
    file_calls: dict[str, set[str]] = {}
    file_globals: dict[str, dict[str, int]] = {}

    for path in sorted(ROOT.rglob("*.au3")):
        definitions, calls, declared, used, _byref, _sites = check_file(path, [])
        key = path.resolve().as_posix()
        repo_definitions[key] = definitions
        repo_declarations[key] = declared
        file_calls[key] = calls
        file_globals[key] = used

    known_functions = {
        name.casefold()
        for key, names in repo_definitions.items()
        if Path(key).name not in STUB_SCRIPTS
        for name in names
    }
    known_globals = {name for names in repo_declarations.values() for name in names}

    sizes: dict[str, int] = {}
    for entry_name in ENTRY_POINTS:
        entry = ROOT / entry_name
        if not entry.exists():
            errors.append(f"entry point is missing: {entry_name}")
            continue
        graph = include_graph(entry)
        sizes[entry_name] = len(graph)
        keys = [p.resolve().as_posix() for p in graph]
        in_graph_functions = {n.casefold() for k in keys for n in repo_definitions.get(k, set())}
        in_graph_globals = {n for k in keys for n in repo_declarations.get(k, set())}

        for key in keys:
            relative = Path(key).relative_to(ROOT.resolve()).as_posix()
            for call in sorted(file_calls.get(key, set())):
                folded = call.casefold()
                # Only names this repository defines somewhere are checked; anything else is an AutoIt built-in.
                if folded in known_functions and folded not in in_graph_functions:
                    errors.append(
                        f"{relative}: {call}() is not reachable from {entry_name}; "
                        f"it is defined in the repository but not in that build's include graph"
                    )
            for name in sorted(file_globals.get(key, {})):
                if name.casefold() in {g.casefold() for g in known_globals} and name.casefold() not in {g.casefold() for g in in_graph_globals}:
                    errors.append(
                        f"{relative}: ${name} is not declared in {entry_name}'s include graph"
                    )
    return sizes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--all", action="store_true", help="balance-check every AutoIt file in the repository")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    first_party: list[Path] = []
    for entry in FIRST_PARTY:
        candidate = ROOT / entry
        if candidate.is_dir():
            first_party.extend(sorted(candidate.rglob("*.au3")))
        elif candidate.is_file():
            first_party.append(candidate)
        else:
            errors.append(f"configured lint target is missing: {entry}")

    # Balance checking is safe everywhere; include and call resolution only make sense for first-party code,
    # whose call graph does not reach into AutoIt's standard library.
    targets = sorted(ROOT.rglob("*.au3")) if args.all else list(first_party)

    all_definitions: set[str] = set()
    all_calls: dict[str, set[str]] = {}
    all_declared: set[str] = set()
    all_used: dict[str, dict[str, int]] = {}
    all_byref: dict[str, set[int]] = {}
    all_sites: dict[str, list] = {}
    for path in targets:
        definitions, calls, declared, used, byref, sites = check_file(path, errors)
        all_byref.update(byref)
        all_sites[path.relative_to(ROOT).as_posix()] = sites
        all_definitions |= definitions
        relative = path.relative_to(ROOT).as_posix()
        all_calls[relative] = calls
        all_declared |= declared
        all_used[relative] = used

    # Every include a first-party file names must exist on disk.
    for path in first_party:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for line in text.splitlines():
            match = INCLUDE_RE.match(line)
            if not match:
                continue
            target = match.group(1)
            if target.startswith("<"):
                continue
            resolved = resolve_include(path, target)
            if not resolved.exists():
                errors.append(f"{path.relative_to(ROOT).as_posix()}: include does not resolve: {target}")

    # Calls that look like project functions must resolve somewhere in the first-party set.
    project_prefixes = ("RunPlan", "RunSession", "RunEvent", "RunIntent", "RunVerification", "BattleRoute",
                        "BattleQuota", "HeroLoadout", "AccountQueue", "CurrentGame", "_CurrentGame")
    # Undeclared globals are checked across the whole tree regardless of --all, because a global is
    # declared in one file and used in another: restricting either side to first-party code misses the
    # exact case Au3Check reports.
    if not args.all:
        for path in ROOT.rglob("*.au3"):
            if path in targets:
                continue
            _, _, declared, used, byref, _sites = check_file(path, [])
            all_byref.update(byref)
            all_declared |= declared
            all_used[path.relative_to(ROOT).as_posix()] = used

    for relative in sorted(all_used):
        for name, line in sorted(all_used[relative].items()):
            if name.casefold() not in all_declared:
                errors.append(f"{relative}:{line}: undeclared global variable: ${name}")

    simple_variable = re.compile(r"^\$\w+(?:\[[^\]]*\])*$")
    for relative, sites in sorted(all_sites.items()):
        for line, name, arguments in sites:
            positions = all_byref.get(name.casefold())
            if not positions:
                continue
            for index in sorted(positions):
                if index >= len(arguments):
                    continue
                argument = arguments[index].strip()
                if argument and not simple_variable.fullmatch(argument):
                    errors.append(
                        f"{relative}:{line}: {name}() binds an expression to ByRef parameter {index + 1}: {argument}"
                    )

    first_party_relative = {p.relative_to(ROOT).as_posix() for p in first_party}
    for relative, calls in all_calls.items():
        if relative not in first_party_relative:
            continue
        for call in sorted(calls):
            if not call.startswith(project_prefixes):
                continue
            if call not in all_definitions:
                errors.append(f"{relative}: call to undefined project function: {call}")

    entry_sizes = check_entry_points(errors)

    report = {
        "schema_version": 1,
        "entry_points": entry_sizes,
        "files": len(targets),
        "definitions": len(all_definitions),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    if args.json_path:
        args.json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
