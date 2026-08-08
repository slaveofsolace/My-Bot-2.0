#!/usr/bin/env python3
"""Serve the local Run Planner control center.

The server is deliberately small: standard library only, loopback only, no credentials, and no
remote assets. It validates and atomically writes the flat planner document consumed by AutoIt.

Merge note (cloud base + Windows hardening):
    The save contract is strict in one direction only. A POST naming a setting this planner does not
    have is refused with 400 and nothing is written, because the caller and the server disagree about
    what exists and guessing would silently drop the caller's intent. Values that are merely out of
    range, or a boolean spelled as a word, or a Hero list over the ceiling, are adjusted, saved, and
    reported -- those are recoverable. The AutoIt reader stays deliberately lenient; different
    direction, different concern.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import tempfile
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "config/ui/run-planner.settings.json"
CAPABILITIES = ROOT / "config/current-client-capabilities.json"
UI_HTML = ROOT / "ui/planner.html"
UI_CSS = ROOT / "ui/planner.css"
UI_JS = ROOT / "ui/planner.js"

PLAN_PATH = ROOT / "config/run-plan.local.json"
EVENTS_PATH = ROOT / "logs/run-events.jsonl"

MAX_REQUEST_BYTES = 256 * 1024
MAX_TAIL_BYTES = 512 * 1024
LOCAL_HOSTS = {"127.0.0.1", "localhost"}


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def metadata_document() -> dict:
    return read_json(METADATA, {"sections": []})


def settings_index() -> dict[str, dict]:
    return {
        setting["id"]: setting
        for section in metadata_document().get("sections", [])
        for setting in section.get("settings", [])
    }


def normalized_default(setting: dict):
    value = setting.get("default", "")
    if setting.get("type") == "multi-select":
        if isinstance(value, list):
            return list(value)
        return [] if value in (None, "") else [value]
    return value


def default_plan() -> dict:
    return {setting_id: normalized_default(setting) for setting_id, setting in settings_index().items()}


def validate_plan(submitted: dict) -> tuple[dict, list[str], list[str]]:
    """Normalize the complete planner document without guessing ambiguous values.

    Returns (clean, adjustments, rejected). `adjustments` records values that were coerced or
    clamped and then saved. `rejected` records settings this planner does not have; a caller that
    names one gets a 400 and nothing is written.
    """
    known = settings_index()
    clean: dict = {}
    adjustments: list[str] = []
    rejected: list[str] = []

    for key, value in submitted.items():
        setting = known.get(key)
        if setting is None:
            rejected.append(f"{key} is not a setting this planner has")
            continue

        kind = setting.get("type")
        default = normalized_default(setting)

        if kind == "boolean":
            if isinstance(value, bool):
                clean[key] = value
            elif isinstance(value, str):
                token = value.strip().lower()
                if token in {"true", "1", "yes", "on"}:
                    clean[key] = True
                elif token in {"false", "0", "no", "off", ""}:
                    clean[key] = False
                else:
                    adjustments.append(f"{key}: {value!r} is not a yes/no value, kept the default")
                    clean[key] = default
            else:
                adjustments.append(f"{key}: {type(value).__name__} is not a yes/no value, kept the default")
                clean[key] = default

        elif kind == "integer":
            if isinstance(value, bool):
                adjustments.append(f"{key}: boolean is not a whole number, kept the default")
                clean[key] = default
                continue
            try:
                number = int(value)
            except (TypeError, ValueError, OverflowError):
                adjustments.append(f"{key}: not a whole number, kept the default")
                clean[key] = default
                continue
            rules = setting.get("validation", {})
            low, high = rules.get("minimum"), rules.get("maximum")
            if isinstance(low, int) and number < low:
                adjustments.append(f"{key}: {number} is below {low}, clamped")
                number = low
            if isinstance(high, int) and number > high:
                adjustments.append(f"{key}: {number} is above {high}, clamped")
                number = high
            clean[key] = number

        elif kind in {"select", "multi-select"}:
            choices = {option["value"] for option in setting.get("options", [])}
            if kind == "multi-select":
                incoming = value if isinstance(value, list) else [value]
                picked: list[str] = []
                for item in incoming:
                    if not isinstance(item, str) or item not in choices:
                        adjustments.append(f"{key}: {item!r} is not an option")
                    elif item not in picked:
                        picked.append(item)
                # A MISSING ceiling is treated as a fault, not as "no ceiling". Silently falling
                # through on None is exactly how the Hero four-slot cap would disappear from the
                # server while still looking enforced in the browser and the metadata validator.
                # Every multi-select is required to declare a ceiling, so absence is a real defect.
                limit = setting.get("max_selected")
                if isinstance(limit, bool) or not isinstance(limit, int):
                    adjustments.append(f"{key}: no selection ceiling is declared for this setting")
                elif len(picked) > limit:
                    adjustments.append(f"{key}: only {limit} selections are allowed")
                    picked = picked[:limit]
                clean[key] = picked
            elif isinstance(value, str) and value in choices:
                clean[key] = value
            else:
                adjustments.append(f"{key}: {value!r} is not an option, kept the default")
                clean[key] = default

        else:
            if isinstance(value, str):
                clean[key] = value.strip()
            else:
                adjustments.append(f"{key}: expected text, kept the default")
                clean[key] = default

    for key, setting in known.items():
        clean.setdefault(key, normalized_default(setting))
    return clean, adjustments, rejected


def read_plan() -> dict:
    raw = read_json(PLAN_PATH, default_plan())
    if not isinstance(raw, dict):
        return default_plan()
    return validate_plan(raw)[0]


def write_plan_atomic(plan: dict, path: Path | None = None) -> None:
    """Write through a unique same-directory file, flush it, then replace the destination."""
    destination = path or PLAN_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(plan, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def plan_status() -> dict:
    """Report what is on disk.

    A file that exists but cannot be parsed is reported as "unreadable", not "saved". The AutoIt
    loader is strict and would refuse such a file, and a status that disagrees with the reader is
    worse than no status at all.
    """
    if not PLAN_PATH.exists():
        return {"exists": False, "state": "defaults", "written_at": None}
    try:
        written = datetime.fromtimestamp(PLAN_PATH.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        written = None
    parsed = read_json(PLAN_PATH, None)
    if not isinstance(parsed, dict):
        return {"exists": True, "state": "unreadable", "written_at": written}
    return {"exists": True, "state": "saved", "written_at": written}


def displayed_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def tail_events(limit: int = 200) -> list[dict]:
    """Read a bounded tail and ignore malformed lines without losing the complete feed."""
    if not EVENTS_PATH.exists():
        return []
    try:
        with EVENTS_PATH.open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - MAX_TAIL_BYTES))
            blob = stream.read()
        if size > MAX_TAIL_BYTES:
            blob = blob.split(b"\n", 1)[-1]
        lines = blob.decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []

    events: list[dict] = []
    for line in lines[-limit:]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def health_payload() -> dict:
    metadata = metadata_document()
    settings = [setting for section in metadata.get("sections", []) for setting in section.get("settings", [])]
    return {
        "ok": True,
        "service": "run-planner",
        "bridge": "autoit-plan-file-v1",
        "sections": len(metadata.get("sections", [])),
        "settings": len(settings),
        "plan": plan_status(),
    }


def local_request_allowed(handler: BaseHTTPRequestHandler) -> bool:
    try:
        host = urlsplit("//" + handler.headers.get("Host", "")).hostname
        port = urlsplit("//" + handler.headers.get("Host", "")).port
    except ValueError:
        return False
    expected_port = handler.server.server_address[1]
    if host not in LOCAL_HOSTS or port not in (None, expected_port):
        return False

    origin = handler.headers.get("Origin")
    if not origin:
        return True
    try:
        parsed = urlsplit(origin)
        return parsed.scheme == "http" and parsed.hostname in LOCAL_HOSTS and parsed.port == expected_port
    except ValueError:
        return False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code: int, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, code: int = 200):
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def _allow_local(self) -> bool:
        if local_request_allowed(self):
            return True
        self._json({"ok": False, "problems": ["request origin is not this local planner"]}, 403)
        return False

    def do_GET(self):
        if not self._allow_local():
            return
        assets = {
            "/": (UI_HTML, "text/html; charset=utf-8"),
            "/index.html": (UI_HTML, "text/html; charset=utf-8"),
            "/planner.css": (UI_CSS, "text/css; charset=utf-8"),
            "/planner.js": (UI_JS, "text/javascript; charset=utf-8"),
        }
        if self.path in assets:
            path, content_type = assets[self.path]
            if not path.exists():
                self._send(500, f"{path.relative_to(ROOT)} is missing".encode(), "text/plain; charset=utf-8")
                return
            self._send(200, path.read_bytes(), content_type)
        elif self.path == "/api/health":
            self._json(health_payload())
        elif self.path == "/api/metadata":
            self._json({"metadata": metadata_document(), "capabilities": read_json(CAPABILITIES, {})})
        elif self.path == "/api/plan":
            self._json(read_plan())
        elif self.path == "/api/events":
            self._json({"events": tail_events()})
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if not self._allow_local():
            return
        if self.path != "/api/plan":
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        if self.headers.get_content_type() != "application/json":
            self._json({"ok": False, "problems": ["Content-Type must be application/json"]}, 415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json({"ok": False, "problems": ["Content-Length was not a number"]}, 400)
            return
        if length < 0 or length > MAX_REQUEST_BYTES:
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

        clean, adjustments, rejected = validate_plan(submitted)

        # An unknown setting means the caller and this server disagree about what exists. Saving the
        # rest would silently drop the caller's intent, so refuse the whole document and write nothing.
        if rejected:
            self._json({"ok": False, "problems": rejected, "written": None}, 400)
            return

        try:
            write_plan_atomic(clean)
        except OSError:
            self._json({"ok": False, "problems": ["the plan could not be written atomically"]}, 500)
            return
        self._json({
            "ok": True,
            "problems": adjustments,
            "written": displayed_path(PLAN_PATH),
            "plan": clean,
            "status": plan_status(),
        })


class PlannerServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def selftest() -> int:
    failures: list[str] = []

    def check(condition, message):
        print(f"  {'ok  ' if condition else 'FAIL'}  {message}")
        if not condition:
            failures.append(message)

    plan = default_plan()
    setting_ids = set(settings_index())
    check(set(plan) == setting_ids, "default plan covers every setting exactly")
    check(isinstance(plan["run.heroes"], list), "multi-select defaults use a stable list shape")

    clean, adjustments, rejected = validate_plan({"run.max_failures": 9999})
    check(clean["run.max_failures"] == 100 and any("clamped" in item for item in adjustments), "integer maximum is enforced")
    clean, adjustments, rejected = validate_plan({"run.diagnostic_mode": "false"})
    check(clean["run.diagnostic_mode"] is False and not adjustments, "the string 'false' reads as off")
    clean, adjustments, rejected = validate_plan({"run.diagnostic_mode": "0"})
    check(clean["run.diagnostic_mode"] is False and not adjustments, "the string '0' reads as off")
    for ambiguous in (0, None, [], {}):
        clean, adjustments, rejected = validate_plan({"run.diagnostic_mode": ambiguous})
        check(clean["run.diagnostic_mode"] is False and bool(adjustments), f"ambiguous boolean {ambiguous!r} is rejected")
    clean, adjustments, rejected = validate_plan({"run.heroes": ["barbarian-king", "archer-queen", "minion-prince", "grand-warden", "royal-champion"]})
    check(len(clean["run.heroes"]) == 4 and any("only 4" in item for item in adjustments), "Hero selection is capped at four")

    # Strict rejection: unknown settings are never silently dropped.
    clean, adjustments, rejected = validate_plan({"run.not_a_real_setting": 1})
    check(len(rejected) == 1 and "not a setting" in rejected[0], "an unknown setting is rejected, not ignored")
    clean, adjustments, rejected = validate_plan({"run.max_failures": 9999, "run.not_a_real_setting": 1})
    check(bool(rejected) and bool(adjustments), "rejections and adjustments are reported separately")

    # The pacing section arrives with the cloud metadata; prove its bounds are live.
    check("pacing.settle_ms" in setting_ids, "the pacing section is present in the metadata")
    clean, adjustments, rejected = validate_plan({"pacing.settle_ms": 999999})
    check(clean["pacing.settle_ms"] == 10000 and any("clamped" in item for item in adjustments), "pacing settle bound is enforced")

    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "plan.json"
        write_plan_atomic(plan, target)
        check(read_json(target, {}) == plan, "atomic writer produces the complete plan")
        target.write_text('{"sentinel": true}\n', encoding="utf-8")
        with mock.patch("os.replace", side_effect=OSError("interrupted")):
            try:
                write_plan_atomic(plan, target)
            except OSError:
                pass
        check(read_json(target, {}) == {"sentinel": True}, "interrupted replacement preserves the previous plan")
        check(not list(target.parent.glob(".*.tmp")), "failed writes leave no temporary plan behind")

    global PLAN_PATH, EVENTS_PATH
    original_plan, original_events = PLAN_PATH, EVENTS_PATH
    with tempfile.TemporaryDirectory() as folder:
        PLAN_PATH = Path(folder) / "plan.json"
        EVENTS_PATH = Path(folder) / "events.jsonl"

        # A corrupt plan file must not be reported as saved, because AutoIt would refuse it.
        PLAN_PATH.write_text("{ this is not json", encoding="utf-8")
        check(plan_status()["state"] == "unreadable", "a corrupt plan file is reported as unreadable")
        PLAN_PATH.unlink()

        server = PlannerServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("GET", "/api/health")
            response = connection.getresponse()
            check(response.status == 200 and json.loads(response.read())["bridge"] == "autoit-plan-file-v1", "health endpoint reports the AutoIt bridge")

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("GET", "/api/health")
            headers = connection.getresponse().headers
            check(headers.get("Content-Security-Policy") is not None and headers.get("X-Content-Type-Options") == "nosniff", "security headers are present")

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.putrequest("GET", "/api/health", skip_host=True)
            connection.putheader("Host", "example.invalid")
            connection.endheaders()
            check(connection.getresponse().status == 403, "non-local Host is refused")

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("POST", "/api/plan", body=b"{}", headers={
                "Content-Type": "application/json", "Origin": "https://example.invalid"
            })
            check(connection.getresponse().status == 403, "foreign Origin is refused")

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.request("POST", "/api/plan", body=b"{}", headers={"Content-Type": "text/plain"})
            check(connection.getresponse().status == 415, "a non-JSON Content-Type is refused")

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            connection.putrequest("POST", "/api/plan")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(MAX_REQUEST_BYTES + 1))
            connection.endheaders()
            check(connection.getresponse().status == 413, "oversized plan is refused before reading")

            # Strict rejection over the wire: 400, and the file on disk is untouched.
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            body = json.dumps({"run.not_a_real_setting": 1}).encode()
            connection.request("POST", "/api/plan", body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            check(response.status == 400 and payload["ok"] is False, "an unknown setting is refused with 400")
            check(not PLAN_PATH.exists(), "a refused save writes nothing")

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            body = json.dumps({"run.diagnostic_mode": False}).encode()
            connection.request("POST", "/api/plan", body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            check(response.status == 200 and payload["ok"] and set(payload["plan"]) == setting_ids, "valid partial plan is normalized and written")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
    PLAN_PATH, EVENTS_PATH = original_plan, original_events

    print(f"\n{'selftest passed' if not failures else str(len(failures)) + ' check(s) failed'}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--selftest", action="store_true", help="check the complete local server contract")
    args = parser.parse_args()

    if args.selftest:
        return selftest()
    if not METADATA.exists():
        print(f"missing {METADATA.relative_to(ROOT)}; run tools/generate_run_planner_settings.py first")
        return 2
    if not all(path.exists() for path in (UI_HTML, UI_CSS, UI_JS)):
        print("missing one or more planner UI files")
        return 2

    server = PlannerServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
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
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
