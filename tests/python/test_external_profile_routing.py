from __future__ import annotations

import base64
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = (ROOT / "My Bot 2.0.au3").read_text(encoding="utf-8-sig")
BACKEND = (ROOT / "MyBot.run.au3").read_text(encoding="utf-8-sig")
MINI = (ROOT / "MyBot.run.MiniGui.au3").read_text(encoding="utf-8-sig")
PLANNER_PATH = ROOT / "tools" / "planner_ui.py"
PLANNER_CONTROL = (
    ROOT / "COCBot" / "GUI" / "MBR GUI Control Run Planner.au3"
).read_text(encoding="utf-8-sig")
MBR_FUNC = (
    ROOT / "COCBot" / "functions" / "Other" / "MBRFunc.au3"
).read_text(encoding="utf-8-sig")

SPEC = importlib.util.spec_from_file_location("planner_ui_profile_routing", PLANNER_PATH)
PLANNER_UI = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PLANNER_UI)


def autoit_function(source: str, name: str) -> str:
    match = re.search(rf"(?ims)^Func {re.escape(name)}\b.*?^EndFunc[^\r\n]*", source)
    if match is None:
        raise AssertionError(f"missing AutoIt function {name}")
    return match.group(0)


def pinned_mini_parse(arguments: list[str]) -> tuple[list[str], list[str]]:
    """Faithful model of pinned Mini's option filter and backend reconstruction."""
    supported = {
        "/restart", "/r", "-restart", "-r", "/autostart", "/a", "-autostart", "-a",
        "/nowatchdog", "/nwd", "-nowatchdog", "-nwd", "/dpiaware", "/da", "-dpiaware",
        "-da", "/dock1", "/d1", "-dock1", "-d1", "/dock", "/d", "-dock", "-d",
        "/dock2", "/d2", "-dock2", "-d2", "/nobotslot", "/nbs", "-nobotslot",
        "-nbs", "/debug", "/debugmode", "/dev", "-debug", "-dev", "/minigui", "/mg",
        "-minigui", "-mg", "/nogui", "/ng", "-nogui", "-ng", "/console", "/c",
        "-console", "-c",
    }
    positional = [item for item in arguments if item not in supported and not item.startswith("/guipid=")]
    forwarded = [item for item in arguments if item not in {"/ng", "/mg", "/restart"}]
    return positional, forwarded


class ExternalProfileRoutingSourceTests(unittest.TestCase):
    def test_launcher_uses_exact_pinned_mini_argv_and_requires_verified_junction(self) -> None:
        body = autoit_function(LAUNCHER, "_BuildControllerArguments")
        self.assertIn('Return $sProfile & " /nowatchdog"', body)
        self.assertNotIn("profiles64", body.casefold())
        self.assertNotIn("/profiles=", body)
        self.assertIn("Func _InstalledProfilesJunctionMatches()", LAUNCHER)
        self.assertIn("BitAND($aAttributes[0], 0x400)", LAUNCHER)
        self.assertIn("StringLower($sActual) = StringLower($sExpected)", LAUNCHER)

    def test_pinned_mini_treats_only_profile_as_positional_and_forwards_it(self) -> None:
        process = autoit_function(MINI, "ProcessCommandLine")
        launch = autoit_function(MINI, "LaunchBotBackend")
        self.assertIn('Case "/nowatchdog"', process)
        self.assertIn("$g_asCmdLine[$g_asCmdLine[0]] = $CmdLine[$i]", process)
        self.assertIn("$sParam = $CmdLine[$i]", launch)
        positional, forwarded = pinned_mini_parse(["MyVillage", "/nowatchdog"])
        self.assertEqual(positional, ["MyVillage"])
        self.assertEqual(forwarded, ["MyVillage", "/nowatchdog"])
        poisoned, _ = pinned_mini_parse(["MyVillage", "/profiles64=abc", "/nowatchdog"])
        self.assertEqual(poisoned, ["MyVillage", "/profiles64=abc"])

    def test_compiled_backend_adopts_only_exact_external_junction(self) -> None:
        process = autoit_function(BACKEND, "ProcessCommandLine")
        self.assertIn("If @Compiled Then", process)
        self.assertIn("_InstalledBackendProfilesRoot()", process)
        self.assertIn("$g_sProfilePath = $sInstalledProfilesRoot", process)
        helper = autoit_function(BACKEND, "_InstalledBackendProfilesRoot")
        self.assertIn('@ScriptDir & "\\Profiles"', helper)
        self.assertIn('$g_sMBRFuncRuntimeLocalAppData & "\\My Bot 2.0\\Profiles"', helper)
        self.assertIn("BitAND($aAttributes[0], 0x400)", helper)
        self.assertIn("StringLower($sActual) <> StringLower($sExpected)", helper)
        self.assertNotIn("MYBOT_PROFILES_ROOT64", BACKEND)

    def test_isolated_localappdata_override_is_guarded_and_shared(self) -> None:
        launcher = autoit_function(LAUNCHER, "_LauncherRuntimeLocalAppDataDir")
        backend = autoit_function(MBR_FUNC, "_MBRFuncRuntimeLocalAppDataDir")
        for body in (launcher, backend):
            self.assertIn('EnvGet("MYBOT_RUN_PYTHON_INTEGRATION") <> "1" Then Return @LocalAppDataDir', body)
            self.assertIn('EnvGet("MYBOT_INSTALL_TEST_ROOT")', body)
            self.assertIn('EnvGet("LOCALAPPDATA")', body)
            self.assertIn('StringLower($sTestRoot & "\\")', body)
            self.assertIn('"\\.invalid-test-localappdata"', body)
            self.assertNotIn('Then Return EnvGet("LOCALAPPDATA")', body)

        self.assertIn(
            'Global Const $g_sUserDataRoot = _LauncherRuntimeLocalAppDataDir() & "\\My Bot 2.0"',
            LAUNCHER,
        )
        self.assertIn(
            'Global Const $g_sMBRFuncRuntimeLocalAppData = _MBRFuncRuntimeLocalAppDataDir()',
            MBR_FUNC,
        )
        self.assertIn('$g_sMBRFuncRuntimeLocalAppData & "\\My Bot 2.0\\planner-owner-v1.json"', PLANNER_CONTROL)

    def test_legacy_profile_switch_is_source_only_and_bad_paths_are_fatal(self) -> None:
        process = autoit_function(BACKEND, "ProcessCommandLine")
        self.assertIn('ElseIf StringInStr($CmdLine[$i], "/profiles=") = 1 Then', process)
        self.assertIn("$bProfilesOptionSeen = True", process)
        self.assertIn("Profiles Path doesn't exist", process)
        self.assertIn("Exit 10", process)

    def test_planner_and_recovery_require_same_canonical_profile_root(self) -> None:
        self.assertIn(' --profiles-root "\' & $g_sProfilePath & \'"', PLANNER_CONTROL)
        expected = (
            'If _RunPlannerNormalizeRoot(Json_ObjGet($oPayload, "profiles_root")) '
            '<> _RunPlannerNormalizeRoot($g_sProfilePath) Then Return False'
        )
        self.assertGreaterEqual(PLANNER_CONTROL.count(expected), 2)
        self.assertIn('"""profiles_root_token"": """ & $sProfilesRootToken & """"', LAUNCHER)
        self.assertIn(
            '_PlannerReceiptString($sReceipt, "profiles_root_token") <> _ProfilesRootToken($g_sProfilesRoot)',
            LAUNCHER,
        )
        self.assertIn("refused planner service: receipt or service identity mismatch", LAUNCHER)


class ExternalProfileRoutingPlannerTests(unittest.TestCase):
    def test_validation_accepts_exact_external_root_and_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mybot-profile-local-") as folder:
            local = Path(folder) / "Local App Data"
            profiles = local / "My Bot 2.0" / "Profiles"
            outside = Path(folder) / "Outside" / "Profiles"
            profiles.mkdir(parents=True)
            outside.mkdir(parents=True)
            self.assertEqual(
                PLANNER_UI.validated_external_profiles_root(str(profiles), local_app_data=local),
                profiles.resolve(),
            )
            for unsafe in (str(profiles) + '"', str(outside), str(local), "relative\\Profiles"):
                with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                    PLANNER_UI.validated_external_profiles_root(unsafe, local_app_data=local)

    def test_health_token_and_native_log_report_external_tree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mybot-profile-health-") as folder:
            local = Path(folder) / "Local App Data"
            profiles = local / "My Bot 2.0" / "Profiles"
            logs = profiles / "MyVillage" / "Logs"
            logs.mkdir(parents=True)
            log = logs / "2026-08-13_12.00.00.log"
            log.write_text("external profile log\n", encoding="utf-8")
            resolved = PLANNER_UI.validated_external_profiles_root(str(profiles), local_app_data=local)
            with mock.patch.object(PLANNER_UI, "PROFILES_ROOT", resolved), mock.patch.object(
                PLANNER_UI, "control_status", return_value={"profile": "MyVillage"}
            ):
                health = PLANNER_UI.health_payload()
                payload = PLANNER_UI.native_log_payload()
            expected_token = base64.urlsafe_b64encode(str(resolved).encode("utf-8")).decode("ascii").rstrip("=")
            self.assertEqual(health["profiles_root"], str(resolved))
            self.assertEqual(health["profiles_root_token"], expected_token)
            self.assertTrue(payload["available"])
            self.assertEqual(Path(payload["path"]), log)
            self.assertEqual(payload["text"], "external profile log")

    def test_cli_rejects_tampered_profile_root_before_binding(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mybot-profile-cli-") as folder:
            local = Path(folder) / "Local App Data"
            profiles = local / "My Bot 2.0" / "Profiles"
            profiles.mkdir(parents=True)
            env = os.environ.copy()
            env["LOCALAPPDATA"] = str(local)
            result = subprocess.run(
                [sys.executable, str(PLANNER_PATH), "--no-browser", "--profiles-root", str(profiles) + '"'],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=5, check=False,
            )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("invalid profiles root", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
