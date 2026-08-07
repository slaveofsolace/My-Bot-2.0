#!/usr/bin/env python3
"""Serve the Run Planner as a local web UI.

    python tools/planner_ui.py            then open http://127.0.0.1:8765

Reads the same generated metadata the AutoIt tab renders from, so the two cannot describe different
settings. Writes a run plan the engine can pick up, and tails the JSONL event stream for live status.

Standard library only, no build step, and it binds to loopback so nothing is exposed off the machine.
"""

from __future__ import annotations

import argparse
import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "config/ui/run-planner.settings.json"
CAPABILITIES = ROOT / "config/current-client-capabilities.json"
UI_HTML = ROOT / "ui/planner.html"

# Written by this UI, read by the engine. Local to the machine, so it stays out of git.
PLAN_PATH = ROOT / "config/run-plan.local.json"
# The engine appends one JSON object per line here while a run is going.
EVENTS_PATH = ROOT / "logs/run-events.jsonl"

MAX_REQUEST_BYTES = 256 * 1024   # a run plan is a few KB; anything larger is a mistake
MAX_TAIL_BYTES = 512 * 1024      # how far back to seek when tailing the event log


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def tail_events(limit: int = 200) -> list[dict]:
    """Last N events. Malformed lines are skipped rather than killing the feed."""
    if not EVENTS_PATH.exists():
        return []
    # A long run's event log can reach hundreds of megabytes. Seek to the tail and read only the
    # last slice rather than pulling the whole file in to take 200 lines off the end.
    try:
        with EVENTS_PATH.open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - MAX_TAIL_BYTES))
            blob = stream.read()
        if size > MAX_TAIL_BYTES:
            blob = blob.split(b"\n", 1)[-1]      # drop the partial first line
        lines = blob.decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []
    events = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def default_plan() -> dict:
    """Every setting at its declared default, so a fresh UI matches a fresh AutoIt tab."""
    metadata = read_json(METADATA, {"sections": []})
    plan = {}
    for section in metadata.get("sections", []):
        for setting in section.get("settings", []):
            plan[setting["id"]] = setting.get("default", "")
    return plan


def validate_plan(submitted: dict) -> tuple[dict, list[str], list[str]]:
    """Coerce a submission to the declared types and report what happened to it.

    Returns the cleaned plan, the adjustments made to it, and the outright rejections.

    Adjustments are values the server could repair - an integer past its bound, a boolean written as a
    word - and they are reported but do not stop the write. Rejections are keys that name no setting at
    all, and they do stop it: the browser loaded its controls from this same server, so a key it does
    not recognise means the tab is stale or something else is writing, and quietly dropping it would
    save a plan that is not the one the operator was looking at.

    Note the asymmetry with the AutoIt reader, which ignores settings it does not have. That direction
    is a build reading a file it did not write, where tolerating an unknown key is what lets an older
    and a newer build share one file. This direction is a client writing to its own server.
    """
    metadata = read_json(METADATA, {"sections": []})
    known = {}
    for section in metadata.get("sections", []):
        for setting in section.get("settings", []):
            known[setting["id"]] = setting

    clean, problems, rejected = {}, [], []
    for key, value in submitted.items():
        setting = known.get(key)
        if setting is None:
            rejected.append(f"{key} is not a setting this planner has")
            continue
        kind = setting.get("type")
        if kind == "boolean":
            # bool("false") is True in Python, so a client sending the *string* "false" would switch
            # the setting on. That matters most for run.diagnostic_mode, which is what permits
            # unverified surfaces to run, so strings are matched explicitly and anything
            # unrecognised falls back to the declared default rather than guessing.
            if isinstance(value, bool):
                clean[key] = value
            elif isinstance(value, (int, float)):
                clean[key] = bool(value)
            elif isinstance(value, str):
                token = value.strip().lower()
                if token in ("true", "1", "yes", "on"):
                    clean[key] = True
                elif token in ("false", "0", "no", "off", ""):
                    clean[key] = False
                else:
                    problems.append(f"{key}: {value!r} is not a yes/no value, kept the default")
                    clean[key] = bool(setting.get("default", False))
            else:
                problems.append(f"{key}: {type(value).__name__} is not a yes/no value, kept the default")
                clean[key] = bool(setting.get("default", False))
        elif kind == "integer":
            try:
                number = int(value)
            except (TypeError, ValueError):
                problems.append(f"{key}: not a whole number, kept the default")
                clean[key] = setting.get("default", 0)
                continue
            rules = setting.get("validation", {})
            low, high = rules.get("minimum"), rules.get("maximum")
            if isinstance(low, int) and number < low:
                problems.append(f"{key}: {number} is below {low}, clamped")
                number = low
            if isinstance(high, int) and number > high:
                problems.append(f"{key}: {number} is above {high}, clamped")
                number = high
            clean[key] = number
        elif kind in ("select", "multi-select"):
            values = {o["value"] for o in setting.get("options", [])}
            submitted_values = value if isinstance(value, list) else [value]
            picked = [v for v in submitted_values if v in values]
            for bad in [v for v in submitted_values if v not in values]:
                problems.append(f"{key}: {bad!r} is not an option")
            if kind == "multi-select":
                # A browser respects the ceiling, but the plan file is a file: anyone can put six
                # Heroes in four slots with a text editor, and the engine would refuse the whole plan.
                ceiling = setting.get("max_selected")
                seen: list = []
                for item in picked:
                    if item in seen:
                        problems.append(f"{key}: {item!r} listed more than once, kept one")
                        continue
                    seen.append(item)
                if isinstance(ceiling, int) and len(seen) > ceiling:
                    problems.append(f"{key}: {len(seen)} selected but only {ceiling} fit, kept the first {ceiling}")
                    seen = seen[:ceiling]
                clean[key] = seen
            else:
                clean[key] = picked[0] if picked else setting.get("default")
        else:
            clean[key] = str(value)

    for key, setting in known.items():
        clean.setdefault(key, setting.get("default", ""))
    return clean, problems, rejected


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # the console stays readable; the UI shows what matters

    def _send(self, code: int, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, code: int = 200):
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            if not UI_HTML.exists():
                self._send(500, b"ui/planner.html is missing", "text/plain; charset=utf-8")
                return
            self._send(200, UI_HTML.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/metadata":
            self._json({
                "metadata": read_json(METADATA, {}),
                "capabilities": read_json(CAPABILITIES, {}),
            })
        elif self.path == "/api/plan":
            self._json(read_json(PLAN_PATH, default_plan()))
        elif self.path == "/api/events":
            self._json({"events": tail_events()})
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path != "/api/plan":
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json({"ok": False, "problems": ["Content-Length was not a number"]}, 400)
            return
        if length < 0 or length > MAX_REQUEST_BYTES:
            # A plan is a few kilobytes. Reading an arbitrary declared length would let one bad
            # request pull the process's memory out from under it.
            self._json({"ok": False, "problems": [f"request body exceeds {MAX_REQUEST_BYTES} bytes"]}, 413)
            return
        try:
            submitted = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self._json({"ok": False, "problems": ["request was not valid JSON"]}, 400)
            return
        if not isinstance(submitted, dict):
            self._json({"ok": False, "problems": ["expected an object of setting ids"]}, 400)
            return

        clean, problems, rejected = validate_plan(submitted)
        if rejected:
            # Nothing is written. A partial save here is worse than no save: the operator would be
            # looking at a plan the file does not contain.
            self._json({"ok": False, "problems": rejected, "written": None}, 400)
            return

        PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Written via a temporary file and renamed, so the engine never reads a half-written plan
        # if this process dies mid-write. os.replace is atomic on both Windows and POSIX.
        temporary = PLAN_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, PLAN_PATH)
        self._json({"ok": True, "problems": problems, "written": str(PLAN_PATH.relative_to(ROOT))})


def selftest() -> int:
    """Exercise the validation and defaults logic without a browser, so CI can check it.

    The HTML is verified separately by tools/preview_run_planner.py; this covers the server contract:
    every setting has a default, and the validator coerces, clamps, and rejects the way the UI relies on.
    """
    failures = []

    def check(condition, message):
        print(f"  {'ok  ' if condition else 'FAIL'}  {message}")
        if not condition:
            failures.append(message)

    plan = default_plan()
    metadata = read_json(METADATA, {"sections": []})
    setting_ids = {s["id"] for sec in metadata.get("sections", []) for s in sec.get("settings", [])}
    check(set(plan) == setting_ids, "default plan covers every setting exactly")

    clean, problems, _ = validate_plan({"run.max_failures": 9999})
    check(clean["run.max_failures"] == 100, "integer above maximum is clamped")
    check(any("above" in p for p in problems), "clamp is reported")

    clean, problems, _ = validate_plan({"run.max_failures": -5})
    check(clean["run.max_failures"] == 0, "integer below minimum is clamped")

    # An unknown key is a rejection, not an adjustment: the browser loaded its controls from this
    # server, so a key it does not recognise means the tab is stale. Saving the rest would leave the
    # operator looking at a plan the file does not contain.
    clean, _, rejected = validate_plan({"nonexistent.setting": "x"})
    check("nonexistent.setting" not in clean, "unknown setting is not written")
    check(any("nonexistent.setting" in r for r in rejected), "unknown setting is rejected by name")

    _, _, rejected = validate_plan({"run.max_battles": 5})
    check(not rejected, "a known setting is not rejected")

    # A repairable value stays repairable: clamping must not start refusing the whole plan.
    _, problems, rejected = validate_plan({"run.max_failures": 9999})
    check(problems and not rejected, "an out-of-range value is adjusted, not rejected")

    clean, problems, _ = validate_plan({"run.surface": "not-a-surface"})
    check(clean["run.surface"] != "not-a-surface", "invalid select value is refused")
    check(any("not an option" in p for p in problems), "invalid select value is reported")

    clean, _, _ = validate_plan({"run.stop_on_star_bonus": "true"})
    check(clean["run.stop_on_star_bonus"] is True, "boolean is coerced from a string")

    # The regression that matters: bool("false") is True in Python, so a client sending the string
    # "false" used to switch the setting on. On run.diagnostic_mode that silently permits
    # unverified surfaces to run, which is the one default that must never flip by accident.
    clean, _, _ = validate_plan({"run.diagnostic_mode": "false"})
    check(clean["run.diagnostic_mode"] is False, "the string 'false' does not switch a boolean on")
    for falsey in ("0", "no", "off", ""):
        clean, _, _ = validate_plan({"run.diagnostic_mode": falsey})
        check(clean["run.diagnostic_mode"] is False, f"{falsey!r} reads as off")
    for truthy in ("1", "yes", "on", "TRUE"):
        clean, _, _ = validate_plan({"run.diagnostic_mode": truthy})
        check(clean["run.diagnostic_mode"] is True, f"{truthy!r} reads as on")
    clean, problems, _ = validate_plan({"run.diagnostic_mode": "banana"})
    check(clean["run.diagnostic_mode"] is False, "an unrecognised boolean falls back to the default")
    check(any("yes/no" in p for p in problems), "an unrecognised boolean is reported")

    check(MAX_REQUEST_BYTES > 0 and MAX_TAIL_BYTES > 0, "request and tail limits are set")

    # Four Hero slots out of six. A browser cannot submit a fifth, but the plan file is a file and a
    # text editor can, so the ceiling is enforced here rather than left to the engine to refuse.
    clean, problems, _ = validate_plan({"run.heroes": [
        "barbarian-king", "archer-queen", "grand-warden", "royal-champion", "minion-prince"]})
    check(len(clean["run.heroes"]) == 4, "a multi-select is capped at its declared ceiling")
    check(any("only 4 fit" in p for p in problems), "going over the ceiling is reported")

    clean, problems, _ = validate_plan({"run.heroes": ["archer-queen", "archer-queen"]})
    check(clean["run.heroes"] == ["archer-queen"], "a duplicate selection is collapsed")
    check(any("more than once" in p for p in problems), "a duplicate selection is reported")

    clean, _, _ = validate_plan({"run.heroes": ["archer-queen", "not-a-hero"]})
    check(clean["run.heroes"] == ["archer-queen"], "an unknown selection is dropped, the rest kept")

    clean, _, _ = validate_plan({})
    check(set(clean) == setting_ids, "a partial submission is filled out to every setting")

    print(f"\n{'selftest passed' if not failures else str(len(failures)) + ' check(s) failed'}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--selftest", action="store_true", help="check the server contract, no browser")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if not METADATA.exists():
        print(f"missing {METADATA.relative_to(ROOT)}; run tools/generate_run_planner_settings.py first")
        return 2

    address = ("127.0.0.1", args.port)
    server = ThreadingHTTPServer(address, Handler)
    url = f"http://{address[0]}:{address[1]}"
    print(f"Run Planner UI on {url}")
    print(f"  plan file   {PLAN_PATH.relative_to(ROOT)}")
    print(f"  event feed  {EVENTS_PATH.relative_to(ROOT)}")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
