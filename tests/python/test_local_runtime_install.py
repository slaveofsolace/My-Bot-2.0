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

    def test_installer_is_per_user_and_registers_windows_search(self) -> None:
        self.assertIn('Join-Path $env:LOCALAPPDATA "Programs"', INSTALLER)
        self.assertIn('Microsoft\\Windows\\Start Menu\\Programs\\My Bot 2.0', INSTALLER)
        self.assertIn('$shell.CreateShortcut($shortcutPath)', INSTALLER)
        self.assertIn('HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\MyBot2.0', INSTALLER)
        self.assertNotIn("#RequireAdmin", INSTALLER)

    def test_install_fails_closed_on_unreviewed_or_changed_package(self) -> None:
        self.assertIn("Assert-LocalRuntimePackage", INSTALLER)
        self.assertIn("Assert-ManifestFileSet", INSTALLER)
        self.assertIn("The package manifest contains a duplicate path", INSTALLER)
        self.assertIn("Package file SHA-256 mismatch", INSTALLER)
        self.assertIn("The package contains a file not recorded by the manifest", INSTALLER)
        self.assertIn("A package file recorded by the manifest is missing", INSTALLER)
        self.assertIn('mode -cne "LocalRuntime"', INSTALLER)
        self.assertIn("source_tree_clean -ne $true", INSTALLER)
        self.assertIn("MyBot.run.txt must remain exactly zero bytes", INSTALLER)
        self.assertIn("does not match binary provenance", INSTALLER)
        self.assertIn('"MyBot.run.EngineProbe.exe.config"', INSTALLER)
        self.assertIn("$g_sEngineProbeConfigPath", LAUNCHER)

    def test_install_is_staged_and_refuses_to_update_running_owned_processes(self) -> None:
        self.assertIn("Get-OwnedRunningProcesses", INSTALLER)
        self.assertIn("Close the installed My Bot 2.0 before updating it", INSTALLER)
        self.assertIn('.My Bot 2.0.install-', INSTALLER)
        self.assertIn('.My Bot 2.0.previous', INSTALLER)
        self.assertIn("Move-Item -LiteralPath $stage -Destination $installRoot", INSTALLER)

    def test_payload_and_windows_registration_commit_as_one_recoverable_transaction(self) -> None:
        transaction = INSTALLER[INSTALLER.index("$parent = Split-Path -Parent $installRoot") :]
        install_payload = transaction.index("Move-Item -LiteralPath $stage -Destination $installRoot")
        register = transaction.index("Install-Registration")
        verify = transaction.index("Assert-Registration")
        delete_backup = transaction.index("Remove-Item -LiteralPath $backup -Recurse -Force")
        self.assertLess(install_payload, register)
        self.assertLess(register, verify)
        self.assertLess(verify, delete_backup)
        self.assertIn("Save-RegistrationSnapshot", transaction)
        self.assertIn("Restore-RegistrationSnapshot", transaction)
        self.assertIn("$priorPayloadMoved", transaction)
        self.assertIn("$newPayloadInstalled", transaction)
        self.assertIn(".My Bot 2.0.repair-required.json", transaction)
        self.assertIn("preserved_payload_backup", transaction)
        self.assertIn("registration_snapshot", transaction)

    def test_registration_verification_reads_back_shortcuts_and_uninstall_key(self) -> None:
        verification = INSTALLER[
            INSTALLER.index("function Assert-Registration") : INSTALLER.index("if ($Uninstall) {")
        ]
        self.assertIn("$installedShortcut.TargetPath", verification)
        self.assertIn("$installedShortcut.WorkingDirectory", verification)
        self.assertIn("$installedUninstallShortcut.TargetPath", verification)
        self.assertIn("$installedUninstallShortcut.WorkingDirectory", verification)
        self.assertIn("Get-ItemProperty -LiteralPath $uninstallRegistryPath", verification)
        self.assertIn("$registration.InstallLocation", verification)
        self.assertIn("$registration.UninstallString", verification)

    def test_behavioral_powershell_gate_is_explicit_bounded_and_windowless(self) -> None:
        self.assertEqual(POWERSHELL_INTEGRATION_ENV, "MYBOT_RUN_POWERSHELL_INTEGRATION")
        self.assertEqual(POWERSHELL_TIMEOUT_SECONDS, 20)
        if os.name == "nt":
            self.assertNotEqual(POWERSHELL_NO_WINDOW, 0)

    def test_registration_failure_injection_is_confined_to_an_isolated_test_root(self) -> None:
        self.assertIn('$integrationTestEnabled = [string]$env:MYBOT_RUN_POWERSHELL_INTEGRATION -ceq "1"', INSTALLER)
        self.assertIn("MYBOT_INSTALL_TEST_ROOT", INSTALLER)
        self.assertIn("MYBOT_TEST_UNINSTALL_REGISTRY_PATH", INSTALLER)
        self.assertIn("HKCU:\\Software\\MyBot2.0.Tests", INSTALLER)
        self.assertIn("MYBOT_TEST_INSTALL_FAILURE_POINT", INSTALLER)
        self.assertIn('"after-registration"', INSTALLER)
        self.assertIn("Injected installer integration failure after registration mutation", INSTALLER)

    def test_launcher_creates_and_selects_a_persistent_first_run_profile(self) -> None:
        self.assertIn('@LocalAppDataDir & "\\My Bot 2.0"', LAUNCHER)
        self.assertIn('$g_sProfilesRoot = $g_sUserDataRoot & "\\Profiles"', LAUNCHER)
        self.assertIn('$g_sFirstRunProfile = "MyVillage"', LAUNCHER)
        self.assertIn('IniWrite($g_sProfilesIniPath, "general", "defaultprofile"', LAUNCHER)
        self.assertIn('"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"', LAUNCHER)
        self.assertIn("Local $sLaunchProfile = _PrepareUserProfile()", LAUNCHER)

    def test_launcher_preserves_quoted_profiles_path_through_pinned_mini(self) -> None:
        self.assertIn("Func _BuildControllerArguments($sProfile)", LAUNCHER)
        self.assertIn(
            r"""Return '"' & $sProfile & '" ' & '"/profiles=\"' & $g_sProfilesRoot & '\"" /nowatchdog'""",
            LAUNCHER,
        )
        self.assertIn(
            "ShellExecute($g_sControllerPath, _BuildControllerArguments($sLaunchProfile)",
            LAUNCHER,
        )

    def test_installer_migrates_profiles_only_to_an_empty_persistent_root(self) -> None:
        self.assertIn("[string]$ProfileSourceDirectory", INSTALLER)
        self.assertIn('Join-Path $env:LOCALAPPDATA $productName', INSTALLER)
        self.assertIn('$profilesRoot = Join-Path $userDataRoot "Profiles"', INSTALLER)
        self.assertIn("Assert-ProfileDirectory -Root $sourceRoot", INSTALLER)
        self.assertIn("Profile migration will not overwrite existing per-user data", INSTALLER)
        self.assertIn(".Profiles.migration-", INSTALLER)
        self.assertIn(
            "Copy-Item -LiteralPath $_.FullName -Destination $profileStage -Recurse",
            INSTALLER,
        )
        self.assertNotIn(
            "Copy-Item -LiteralPath $_.FullName -Destination $profileStage -Recurse -Force",
            INSTALLER,
        )
        self.assertIn("Move-Item -LiteralPath $profileStage -Destination $profilesRoot", INSTALLER)

    def test_installer_validates_default_profile_and_retains_data_on_uninstall(self) -> None:
        self.assertIn("function Test-SafeProfileName", INSTALLER)
        self.assertIn("function Get-DefaultProfileName", INSTALLER)
        self.assertIn("function Assert-ProfileDirectory", INSTALLER)
        self.assertIn('defaultprofile=MyVillage', INSTALLER)
        self.assertIn('Write-Host "Profiles were retained at $profilesRoot"', INSTALLER)
        install_flow = INSTALLER[INSTALLER.index("Assert-LocalRuntimePackage\n") :]
        self.assertLess(
            install_flow.index("Assert-LocalRuntimePackage\n"),
            install_flow.index("Initialize-UserProfiles\n"),
        )
        uninstall_flow = INSTALLER[
            INSTALLER.index("if ($Uninstall) {") : INSTALLER.index("Assert-LocalRuntimePackage\n")
        ]
        self.assertNotIn("Remove-Item -LiteralPath $profilesRoot", uninstall_flow)

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
