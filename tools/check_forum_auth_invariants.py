#!/usr/bin/env python3
"""Validate the retired forum-auth compatibility contract offline."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MBR_SOURCE = ROOT / "COCBot" / "functions" / "Other" / "MBRFunc.au3"
AUTH_SOURCE = ROOT / "COCBot" / "functions" / "Other" / "ForumAuthentication.au3"


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"(?ims)^Func\s+{re.escape(name)}\s*\(.*?^EndFunc(?:\s*;[^\r\n]*)?",
        source,
    )
    if not match:
        raise AssertionError(f"missing AutoIt function: {name}")
    return match.group(0)


def assert_static_contract(mbr: str, auth: str) -> None:
    ready = function_body(auth, "ForumAuthorizationReady")
    authenticate = function_body(auth, "ForumAuthentication")

    assert re.search(r"Global\s+\$g_bForumAuthorizationReady\s*=\s*True", auth)
    assert re.search(r"(?im)^\s*Return\s+True\s*$", ready)
    assert "$g_bForumAuthorizationReady = True" in authenticate
    assert re.search(r"(?im)^\s*Return\s+True\s*$", authenticate)

    # Official v8.2.0 retired this network exchange. Reintroducing any of these
    # calls would turn user credentials into a prerequisite again.
    forbidden = (
        "CheckForumAuthentication",
        "ForumLogin",
        "FileExists",
        "FileMove",
        "FileDelete",
        "GUICtrlCreateInput",
        "CreateSplashScreen",
    )
    for token in forbidden:
        assert token not in authenticate, f"retired auth path returned via {token}"

    # The dormant DLL wrappers may remain for upstream ABI compatibility, but
    # response bodies and credentials must never be copied into logs.
    login = function_body(mbr, "ForumLogin")
    assert "Forum login failed, message:" not in login
    assert not re.search(r"(?i)SetDebugLog\([^\r\n]*&\s*\$result\[0\]", login)


def discover_autoit(explicit: Path | None) -> Path | None:
    candidates = [
        explicit,
        Path(r"C:\Program Files (x86)\AutoIt3\AutoIt3.exe"),
        Path(r"C:\Program Files\AutoIt3\AutoIt3.exe"),
    ]
    return next((path for path in candidates if path and path.is_file()), None)


def run_autoit_contract(auth: str, autoit: Path) -> str:
    functions = "\n\n".join(
        (
            function_body(auth, "ForumAuthorizationReady"),
            function_body(auth, "ForumAuthentication"),
        )
    )
    harness = f'''#NoTrayIcon
Opt("MustDeclareVars", 1)

Global $g_bForumAuthorizationReady = False

{functions}

If Not ForumAuthorizationReady() Then Exit 20
$g_bForumAuthorizationReady = False
If Not ForumAuthentication() Then Exit 21
If Not $g_bForumAuthorizationReady Then Exit 22
ConsoleWrite("Forum authorization compatibility tests passed: 3 assertions" & @CRLF)
Exit 0
'''
    with tempfile.TemporaryDirectory(prefix="mybot-forum-auth-") as temp_name:
        harness_path = Path(temp_name) / "ForumAuthenticationContract.au3"
        harness_path.write_text(harness, encoding="utf-8-sig")
        completed = subprocess.run(
            [str(autoit), "/ErrorStdOut", str(harness_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        output = (completed.stdout + completed.stderr).strip()
        if completed.returncode != 0:
            raise AssertionError(
                f"AutoIt forum-auth contract failed with {completed.returncode}:\n{output}"
            )
        return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--autoit", type=Path, help="path to AutoIt3.exe")
    parser.add_argument("--require-autoit", action="store_true")
    args = parser.parse_args()

    mbr = MBR_SOURCE.read_text(encoding="utf-8-sig")
    auth = AUTH_SOURCE.read_text(encoding="utf-8-sig")
    assert_static_contract(mbr, auth)

    autoit = discover_autoit(args.autoit)
    if not autoit:
        if args.require_autoit:
            raise SystemExit("AutoIt3.exe was not found")
        runtime = "AutoIt runtime contract skipped (AutoIt3.exe not found)"
    else:
        runtime = run_autoit_contract(auth, autoit)

    print("Forum authorization upstream-compatibility contract passed")
    print(runtime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
