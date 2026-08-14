from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = (ROOT / "tools" / "Install-LocalRuntime.ps1").read_text(encoding="utf-8")
PYTHON_INSTALLER = (ROOT / "tools" / "install_local_runtime.py").read_text(encoding="utf-8")
INSTALL_CMD = (ROOT / "Install My Bot 2.0.cmd").read_text(encoding="utf-8")
UNINSTALL_CMD = (ROOT / "Uninstall My Bot 2.0.cmd").read_text(encoding="utf-8")
PACKAGER = (ROOT / "tools" / "Build-Release.ps1").read_text(encoding="utf-8")
LAUNCHER = (ROOT / "My Bot 2.0.au3").read_text(encoding="utf-8-sig")
POWERSHELL_INTEGRATION_ENV = "MYBOT_RUN_POWERSHELL_INTEGRATION"
POWERSHELL_TIMEOUT_SECONDS = 20
POWERSHELL_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class LocalRuntimeInstallContract(unittest.TestCase):
    def test_package_contains_double_click_installers(self) -> None:
        for name in (
            '"Install My Bot 2.0.cmd"',
            '"Uninstall My Bot 2.0.cmd"',
            '"tools\\Install-LocalRuntime.ps1"',
            '"tools\\install_local_runtime.py"',
        ):
            self.assertIn(name, PACKAGER)

    def test_powershell_compatibility_entrypoint_delegates_to_python(self) -> None:
        self.assertIn('Join-Path $PSScriptRoot "install_local_runtime.py"', INSTALLER)
        self.assertIn('Get-Command "py.exe"', INSTALLER)
        self.assertIn('Get-Command "python.exe"', INSTALLER)
        self.assertIn('& $python @arguments', INSTALLER)
        self.assertIn("MYBOT_RUN_PYTHON_INTEGRATION", INSTALLER)
        self.assertNotIn("#RequireAdmin", INSTALLER)

    def test_python_installer_owns_integrity_and_transaction(self) -> None:
        for literal in (
            "validate_package(package_root)",
            "copy_payload(package_root, stage)",
            "owned_processes(install_root)",
            "install_registration(install_root",
            "assert_registration(install_root",
            "restore_registration(snapshot",
            "create_profiles_junction(install_root, profiles_root)",
            "remove_install_payload(install_root, profiles_root",
        ):
            self.assertIn(literal, PYTHON_INSTALLER)
        self.assertIn("manifest must exclude the mutable Profiles tree", PYTHON_INSTALLER)
        self.assertIn("$g_sEngineProbeConfigPath", LAUNCHER)

    def test_profiles_junction_is_detached_before_every_recursive_remove(self) -> None:
        removal = PYTHON_INSTALLER[PYTHON_INSTALLER.index("def remove_install_payload") :]
        self.assertLess(removal.index("detach_profiles_junction"), removal.index("shutil.rmtree(install_root)"))
        self.assertNotIn("shutil.rmtree(install_root)", PYTHON_INSTALLER[: PYTHON_INSTALLER.index("def remove_install_payload")])
        self.assertIn("migrate_legacy_installed_profiles", PYTHON_INSTALLER)
        self.assertIn("Conflicting legacy profile data was preserved", PYTHON_INSTALLER)

    def test_behavioral_powershell_gate_is_explicit_bounded_and_windowless(self) -> None:
        self.assertEqual(POWERSHELL_INTEGRATION_ENV, "MYBOT_RUN_POWERSHELL_INTEGRATION")
        self.assertEqual(POWERSHELL_TIMEOUT_SECONDS, 20)
        if os.name == "nt":
            self.assertNotEqual(POWERSHELL_NO_WINDOW, 0)

    def test_registration_failure_injection_is_confined_to_an_isolated_test_root(self) -> None:
        self.assertIn("MYBOT_INSTALL_TEST_ROOT", PYTHON_INSTALLER)
        self.assertIn("MYBOT_TEST_UNINSTALL_REGISTRY_PATH", PYTHON_INSTALLER)
        self.assertIn("MYBOT_TEST_INSTALL_FAILURE_POINT", PYTHON_INSTALLER)
        self.assertIn('"after-registration"', PYTHON_INSTALLER)

    def test_launcher_creates_and_selects_a_persistent_first_run_profile(self) -> None:
        self.assertIn('@LocalAppDataDir & "\\My Bot 2.0"', LAUNCHER)
        self.assertIn('$g_sProfilesRoot = $g_sUserDataRoot & "\\Profiles"', LAUNCHER)
        self.assertIn('$g_sFirstRunProfile = "MyVillage"', LAUNCHER)
        self.assertIn('IniWrite($g_sProfilesIniPath, "general", "defaultprofile"', LAUNCHER)
        self.assertIn('"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"', LAUNCHER)
        self.assertIn("Local $sLaunchProfile = _PrepareUserProfile()", LAUNCHER)

    def test_launcher_passes_only_supported_pinned_mini_arguments(self) -> None:
        self.assertIn("Func _BuildControllerArguments($sProfile)", LAUNCHER)
        self.assertIn('Return $sProfile & " /nowatchdog"', LAUNCHER)
        self.assertNotIn("/profiles64=", LAUNCHER)
        self.assertIn("_InstalledProfilesJunctionMatches()", LAUNCHER)
        self.assertIn(
            "Run('\"' & $g_sControllerPath & '\" ' & _BuildControllerArguments($sLaunchProfile), @ScriptDir, @SW_SHOWNORMAL)",
            LAUNCHER,
        )
        self.assertIn("Local $iControllerLaunchError = @error", LAUNCHER)
        self.assertIn("_EngineSupervisorClearLaunchEnvironment()", LAUNCHER)

    def test_installer_migrates_and_preserves_legacy_profiles_without_overwrite(self) -> None:
        self.assertIn("def migrate_legacy_installed_profiles", PYTHON_INSTALLER)
        self.assertIn("if os.path.lexists(target):", PYTHON_INSTALLER)
        self.assertIn("Profiles.local-preserved-", PYTHON_INSTALLER)
        self.assertIn("shutil.copy2(source, target)", PYTHON_INSTALLER)

    def test_command_launchers_prefer_non_clr_python_installer(self) -> None:
        for source in (INSTALL_CMD, UNINSTALL_CMD):
            self.assertIn("install_local_runtime.py", source)
            self.assertIn("py.exe -3", source)
            self.assertIn("python.exe", source)
            self.assertNotIn("powershell.exe", source.lower())
        self.assertIn("--uninstall", UNINSTALL_CMD)


@unittest.skipUnless(
    os.environ.get(POWERSHELL_INTEGRATION_ENV) == "1",
    "set MYBOT_RUN_POWERSHELL_INTEGRATION=1 to exercise Windows PowerShell package validation",
)
class LocalRuntimePowerShellIntegration(unittest.TestCase):
    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _create_package(self, root: Path, marker: bytes = b"") -> Path:
        package = root / "Package"
        (package / "tools").mkdir(parents=True)
        (package / "config").mkdir()
        shutil.copy2(ROOT / "tools" / "Install-LocalRuntime.ps1", package / "tools" / "Install-LocalRuntime.ps1")
        shutil.copy2(ROOT / "tools" / "install_local_runtime.py", package / "tools" / "install_local_runtime.py")
        payloads = {
            "My Bot 2.0.exe": b"launcher-fixture" + marker,
            "MyBot.run.exe": b"controller-fixture" + marker,
            "MyBot.run.EngineProbe.exe": b"probe-fixture" + marker,
            "MyBot.run.EngineProbe.exe.config": b"<configuration />",
            "MyBot.run.MiniGui.exe": b"mini-fixture" + marker,
            "MyBot.run.txt": b"",
        }
        for relative, content in payloads.items():
            (package / relative).write_bytes(content)
        launcher = package / "My Bot 2.0.exe"
        provenance = {
            "schema_version": 1,
            "artifacts": [
                {
                    "path": "My Bot 2.0.exe",
                    "bytes": launcher.stat().st_size,
                    "sha256": self._sha256(launcher),
                }
            ],
        }
        (package / "config" / "binary-provenance.json").write_text(
            json.dumps(provenance), encoding="utf-8"
        )
        records = []
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = path.relative_to(package).as_posix()
            records.append({"path": relative, "bytes": path.stat().st_size, "sha256": self._sha256(path)})
        manifest = {
            "schema_version": 1,
            "mode": "LocalRuntime",
            "source_tree_clean": True,
            "files": records,
        }
        (package / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return package

    def _run_installer(
        self,
        package: Path,
        local_app_data: Path,
        *,
        validate_only: bool,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        system_root = Path(os.environ["SystemRoot"])
        powershell = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        env = os.environ.copy()
        for name in (
            "MYBOT_INSTALL_TEST_ROOT",
            "MYBOT_TEST_UNINSTALL_REGISTRY_PATH",
            "MYBOT_TEST_INSTALL_FAILURE_POINT",
        ):
            env.pop(name, None)
        env["LOCALAPPDATA"] = str(local_app_data)
        env["APPDATA"] = str(local_app_data.parent / "Roaming")
        env["MYBOT_INSTALL_TEST_ROOT"] = str(local_app_data.parent)
        env[POWERSHELL_INTEGRATION_ENV] = "1"
        if extra_env:
            env.update(extra_env)
        install_root = local_app_data / "Programs" / "My Bot 2.0"
        arguments = [
            str(powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle",
            "Hidden",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(package / "tools" / "Install-LocalRuntime.ps1"),
            "-InstallDirectory",
            str(install_root),
            "-NoLaunch",
        ]
        if validate_only:
            arguments.append("-ValidateOnly")
        return subprocess.run(
            arguments,
            cwd=package,
            env=env,
            capture_output=True,
            text=True,
            timeout=POWERSHELL_TIMEOUT_SECONDS,
            creationflags=POWERSHELL_NO_WINDOW,
            check=False,
        )

    def _validate(self, package: Path, local_app_data: Path) -> subprocess.CompletedProcess[str]:
        return self._run_installer(package, local_app_data, validate_only=True)

    def test_validate_only_accepts_exact_package_and_rejects_every_manifest_drift(self) -> None:
        cases = {
            "baseline": (lambda _package: None, 0, "LocalRuntime package integrity verified"),
            "changed-hash": (
                lambda package: (package / "MyBot.run.exe").write_bytes(b"Xontroller-fixture"),
                1,
                "SHA-256 mismatch",
            ),
            "extra": (lambda package: (package / "extra.bin").write_bytes(b"extra"), 1, "not recorded"),
            "missing": (lambda package: (package / "MyBot.run.exe").unlink(), 1, "missing"),
            "duplicate": (self._duplicate_manifest_record, 1, "duplicate path"),
        }
        with tempfile.TemporaryDirectory(prefix="mybot-installer-integrity-") as folder:
            base = Path(folder)
            for name, (mutate, expected_code, expected_text) in cases.items():
                with self.subTest(case=name):
                    case_root = base / name
                    package = self._create_package(case_root)
                    mutate(package)
                    result = self._validate(package, case_root / "LocalAppData")
                    combined = result.stdout + result.stderr
                    if expected_code == 0:
                        self.assertEqual(result.returncode, 0, combined)
                    else:
                        self.assertNotEqual(result.returncode, 0, combined)
                    self.assertIn(expected_text.lower(), combined.lower())

    def test_registration_failure_restores_prior_payload_shortcuts_and_test_registration(self) -> None:
        import winreg

        test_id = uuid.uuid4().hex
        registry_subkey = rf"Software\MyBot2.0.Tests\{test_id}"
        registry_provider_path = rf"HKCU:\Software\MyBot2.0.Tests\{test_id}"
        integration_env = {"MYBOT_TEST_UNINSTALL_REGISTRY_PATH": registry_provider_path}
        try:
            with tempfile.TemporaryDirectory(prefix="mybot-installer-rollback-") as folder:
                root = Path(folder)
                local_app_data = root / "LocalAppData"
                install_root = local_app_data / "Programs" / "My Bot 2.0"
                start_menu = root / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "My Bot 2.0"
                launch_shortcut = start_menu / "My Bot 2.0.lnk"
                uninstall_shortcut = start_menu / "Uninstall My Bot 2.0.lnk"

                old_package = self._create_package(root / "old", marker=b"-old")
                old_launcher = (old_package / "My Bot 2.0.exe").read_bytes()
                baseline = self._run_installer(
                    old_package,
                    local_app_data,
                    validate_only=False,
                    extra_env=integration_env,
                )
                self.assertEqual(baseline.returncode, 0, baseline.stdout + baseline.stderr)
                prior_shortcuts = {
                    launch_shortcut: self._sha256(launch_shortcut),
                    uninstall_shortcut: self._sha256(uninstall_shortcut),
                }
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    registry_subkey,
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Prior test registration")

                new_package = self._create_package(root / "new", marker=b"-new")
                injected = self._run_installer(
                    new_package,
                    local_app_data,
                    validate_only=False,
                    extra_env={
                        **integration_env,
                        "MYBOT_TEST_INSTALL_FAILURE_POINT": "after-registration",
                    },
                )
                combined = injected.stdout + injected.stderr
                self.assertNotEqual(injected.returncode, 0, combined)
                self.assertIn("injected installer integration failure after registration mutation", combined.lower())

                self.assertEqual((install_root / "My Bot 2.0.exe").read_bytes(), old_launcher)
                for shortcut, expected_hash in prior_shortcuts.items():
                    self.assertEqual(self._sha256(shortcut), expected_hash)
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_subkey) as key:
                    self.assertEqual(winreg.QueryValueEx(key, "DisplayName")[0], "Prior test registration")

                programs_root = local_app_data / "Programs"
                self.assertFalse((programs_root / ".My Bot 2.0.previous").exists())
                self.assertFalse((programs_root / ".My Bot 2.0.repair-required.json").exists())
                self.assertFalse(any(programs_root.glob(".My Bot 2.0.install-*")))
                self.assertFalse(any(programs_root.glob(".My Bot 2.0.registration-*")))
        finally:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, registry_subkey)
            except FileNotFoundError:
                pass

    @staticmethod
    def _duplicate_manifest_record(package: Path) -> None:
        path = package / "release-manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["files"].append(dict(manifest["files"][0]))
        path.write_text(json.dumps(manifest), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
