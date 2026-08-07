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


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def tail_events(limit: int = 200) -> list[dict]:
    """Last N events. Malformed lines are skipped rather than killing the feed."""
    if not EVENTS_PATH.exists():
        return []
    try:
        lines = EVENTS_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
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


def validate_plan(submitted: dict) -> tuple[dict, list[str]]:
    """Keep only known settings, coerce to the declared type, and report anything rejected.

    The UI is not the authority on what is valid: the engine re-validates everything. This exists so a
    typo or a stale browser tab cannot write a plan file the engine will choke on.
    """
    metadata = read_json(METADATA, {"sections": []})
    known = {}
    for section in metadata.get("sections", []):
        for setting in section.get("settings", []):
            known[setting["id"]] = setting

    clean, problems = {}, []
    for key, value in submitted.items():
        setting = known.get(key)
        if setting is None:
            problems.append(f"unknown setting ignored: {key}")
            continue
        kind = setting.get("type")
        if kind == "boolean":
            clean[key] = bool(value)
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
            picked = [v for v in (value if isinstance(value, list) else [value]) if v in values]
            rejected = [v for v in (value if isinstance(value, list) else [value]) if v not in values]
            for bad in rejected:
                problems.append(f"{key}: {bad!r} is not an option")
            clean[key] = picked if kind == "multi-select" else (picked[0] if picked else setting.get("default"))
        else:
            clean[key] = str(value)

    for key, setting in known.items():
        clean.setdefault(key, setting.get("default", ""))
    return clean, problems


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
            submitted = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self._json({"ok": False, "problems": ["request was not valid JSON"]}, 400)
            return
        if not isinstance(submitted, dict):
            self._json({"ok": False, "problems": ["expected an object of setting ids"]}, 400)
            return

        clean, problems = validate_plan(submitted)
        PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
        PLAN_PATH.write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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

    clean, problems = validate_plan({"run.max_failures": 9999})
    check(clean["run.max_failures"] == 100, "integer above maximum is clamped")
    check(any("above" in p for p in problems), "clamp is reported")

    clean, problems = validate_plan({"run.max_failures": -5})
    check(clean["run.max_failures"] == 0, "integer below minimum is clamped")

    clean, problems = validate_plan({"nonexistent.setting": "x"})
    check("nonexistent.setting" not in clean, "unknown setting is dropped")
    check(any("unknown" in p for p in problems), "unknown setting is reported")

    clean, problems = validate_plan({"run.surface": "not-a-surface"})
    check(clean["run.surface"] != "not-a-surface", "invalid select value is refused")
    check(any("not an option" in p for p in problems), "invalid select value is reported")

    clean, _ = validate_plan({"run.stop_on_star_bonus": "true"})
    check(clean["run.stop_on_star_bonus"] is True, "boolean is coerced from a string")

    clean, _ = validate_plan({})
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
