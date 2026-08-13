from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = (ROOT / "tools" / "Install-LocalRuntime.ps1").read_text(encoding="utf-8")
INSTALL_CMD = (ROOT / "Install My Bot 2.0.cmd").read_text(encoding="utf-8")
UNINSTALL_CMD = (ROOT / "Uninstall My Bot 2.0.cmd").read_text(encoding="utf-8")
PACKAGER = (ROOT / "tools" / "Build-Release.ps1").read_text(encoding="utf-8")


class LocalRuntimeInstallContract(unittest.TestCase):
    def test_package_contains_double_click_installers(self) -> None:
        for name in (
            '"Install My Bot 2.0.cmd"',
            '"Uninstall My Bot 2.0.cmd"',
            '"tools\\Install-LocalRuntime.ps1"',
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
        self.assertIn('mode -cne "LocalRuntime"', INSTALLER)
        self.assertIn("source_tree_clean -ne $true", INSTALLER)
        self.assertIn("MyBot.run.txt must remain exactly zero bytes", INSTALLER)
        self.assertIn("does not match binary provenance", INSTALLER)

    def test_install_is_staged_and_refuses_to_update_running_owned_processes(self) -> None:
        self.assertIn("Get-OwnedRunningProcesses", INSTALLER)
        self.assertIn("Close the installed My Bot 2.0 before updating it", INSTALLER)
        self.assertIn('.My Bot 2.0.install-', INSTALLER)
        self.assertIn('.My Bot 2.0.previous', INSTALLER)
        self.assertIn("Move-Item -LiteralPath $stage -Destination $installRoot", INSTALLER)

    def test_command_launchers_use_bundled_windows_powershell(self) -> None:
        expected = "%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
        self.assertIn(expected, INSTALL_CMD)
        self.assertIn(expected, UNINSTALL_CMD)
        self.assertIn("Install-LocalRuntime.ps1", INSTALL_CMD)
        self.assertIn("-Uninstall", UNINSTALL_CMD)


if __name__ == "__main__":
    unittest.main()

