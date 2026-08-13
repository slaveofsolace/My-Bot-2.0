from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "install_local_runtime.py"
SPEC = importlib.util.spec_from_file_location("mybot_python_installer", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PythonLocalRuntimeInstall(unittest.TestCase):
    def create_package(self, root: Path, marker: bytes = b"") -> Path:
        package = root / "Package"
        (package / "tools").mkdir(parents=True)
        (package / "config").mkdir()
        (package / "tools" / "install_local_runtime.py").write_bytes(MODULE_PATH.read_bytes())
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
        (package / "config" / "binary-provenance.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "artifacts": [
                        {
                            "path": "My Bot 2.0.exe",
                            "bytes": launcher.stat().st_size,
                            "sha256": digest(launcher),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        records = []
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            records.append(
                {
                    "path": path.relative_to(package).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": digest(path),
                }
            )
        (package / "release-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "mode": "LocalRuntime",
                    "source_tree_clean": True,
                    "files": records,
                }
            ),
            encoding="utf-8",
        )
        return package

    @contextmanager
    def isolated_environment(self, root: Path, key_id: str):
        local = root / "LocalAppData"
        roaming = root / "Roaming"
        local.mkdir(parents=True)
        roaming.mkdir(parents=True)
        values = {
            "LOCALAPPDATA": str(local),
            "APPDATA": str(roaming),
            "MYBOT_RUN_PYTHON_INTEGRATION": "1",
            "MYBOT_INSTALL_TEST_ROOT": str(root),
            "MYBOT_TEST_UNINSTALL_REGISTRY_PATH": rf"Software\MyBot2.0.Tests\{key_id}",
        }
        with mock.patch.dict(os.environ, values, clear=False):
            yield local, roaming

    def test_validate_only_accepts_exact_package_and_rejects_manifest_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mybot-python-installer-") as folder:
            base = Path(folder)
            baseline = self.create_package(base / "baseline")
            installer.validate_package(baseline)

            changed = self.create_package(base / "changed")
            (changed / "MyBot.run.exe").write_bytes(b"Xontroller-fixture")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                installer.validate_package(changed)

            extra = self.create_package(base / "extra")
            (extra / "extra.bin").write_bytes(b"extra")
            with self.assertRaisesRegex(ValueError, "not recorded"):
                installer.validate_package(extra)

            missing = self.create_package(base / "missing")
            (missing / "MyBot.run.exe").unlink()
            with self.assertRaisesRegex(ValueError, "[Mm]issing"):
                installer.validate_package(missing)

            duplicate = self.create_package(base / "duplicate")
            manifest_path = duplicate / "release-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"].append(dict(manifest["files"][0]))
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate path"):
                installer.validate_package(duplicate)

            profiles = self.create_package(base / "profiles")
            manifest_path = profiles / "release-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"].append({"path": "Profiles/profile.ini", "bytes": 0, "sha256": "0" * 64})
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must exclude the mutable Profiles tree"):
                installer.validate_package(profiles)

    def test_validate_rejects_false_clean_string_and_unsafe_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mybot-python-installer-") as folder:
            package = self.create_package(Path(folder))
            manifest_path = package / "release-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_tree_clean"] = "true"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not a clean LocalRuntime"):
                installer.validate_package(package)

            manifest["source_tree_clean"] = True
            manifest["files"][0]["path"] = "../escape.bin"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsafe path"):
                installer.validate_package(package)

    @unittest.skipUnless(os.name == "nt", "Windows shortcuts and HKCU are Windows-only")
    def test_native_shortcut_round_trip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mybot-shortcut-") as folder:
            root = Path(folder)
            link = root / "My Bot 2.0.lnk"
            target = Path(os.environ["SystemRoot"]) / "System32" / "notepad.exe"
            installer.create_shortcut(link, target, root, '--fixture "one two"', "fixture", target)
            actual_target, actual_working, actual_arguments = installer.read_shortcut(link)
            self.assertEqual(actual_target.resolve(), target.resolve())
            self.assertEqual(actual_working.resolve(), root.resolve())
            self.assertEqual(actual_arguments, '--fixture "one two"')

    @unittest.skipUnless(os.name == "nt", "transaction test mutates only a GUID-scoped HKCU key")
    def test_registration_failure_restores_payload_shortcuts_and_registry(self) -> None:
        import winreg

        key_id = uuid.uuid4().hex
        key_path = rf"Software\MyBot2.0.Tests\{key_id}"
        try:
            with tempfile.TemporaryDirectory(prefix="mybot-python-rollback-") as folder:
                root = Path(folder)
                with self.isolated_environment(root, key_id) as (local, roaming):
                    install_root = local / "Programs" / "My Bot 2.0"
                    common = ["--install-directory", str(install_root), "--no-launch"]
                    old = self.create_package(root / "old", marker=b"-old")
                    self.assertEqual(installer.main(["--package-root", str(old), *common]), 0)
                    old_launcher = (install_root / "My Bot 2.0.exe").read_bytes()
                    start_menu = (
                        roaming
                        / "Microsoft"
                        / "Windows"
                        / "Start Menu"
                        / "Programs"
                        / "My Bot 2.0"
                    )
                    links = {
                        item: digest(item)
                        for item in (
                            start_menu / "My Bot 2.0.lnk",
                            start_menu / "Uninstall My Bot 2.0.lnk",
                        )
                    }
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
                    ) as key:
                        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Prior test registration")

                    new = self.create_package(root / "new", marker=b"-new")
                    with mock.patch.dict(
                        os.environ,
                        {"MYBOT_TEST_INSTALL_FAILURE_POINT": "after-registration"},
                        clear=False,
                    ):
                        self.assertEqual(installer.main(["--package-root", str(new), *common]), 1)

                    self.assertEqual((install_root / "My Bot 2.0.exe").read_bytes(), old_launcher)
                    for link, expected in links.items():
                        self.assertEqual(digest(link), expected)
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                        self.assertEqual(winreg.QueryValueEx(key, "DisplayName")[0], "Prior test registration")
                    programs = local / "Programs"
                    self.assertFalse((programs / ".My Bot 2.0.previous").exists())
                    self.assertFalse((programs / ".My Bot 2.0.repair-required.json").exists())
                    self.assertFalse(any(programs.glob(".My Bot 2.0.install-*")))
        finally:
            installer.delete_registry_tree(key_path)

    @unittest.skipUnless(os.name == "nt", "junction lifecycle is Windows-specific")
    def test_profiles_junction_survives_update_rollback_and_uninstall_without_target_loss(self) -> None:
        key_id = uuid.uuid4().hex
        key_path = rf"Software\MyBot2.0.Tests\{key_id}"
        try:
            with tempfile.TemporaryDirectory(prefix="mybot-python-junction-") as folder:
                root = Path(folder)
                with self.isolated_environment(root, key_id) as (local, _roaming):
                    install_root = local / "Programs" / "My Bot 2.0"
                    profiles = local / "My Bot 2.0" / "Profiles"
                    common = ["--install-directory", str(install_root), "--no-launch"]
                    old = self.create_package(root / "old", marker=b"-old")
                    self.assertEqual(installer.main(["--package-root", str(old), *common]), 0)
                    link = install_root / "Profiles"
                    self.assertTrue(installer.is_directory_junction(link))
                    installer.assert_profiles_junction(link, profiles)
                    sentinel = profiles / "MyVillage" / "persistent-sentinel.txt"
                    sentinel.write_text("keep", encoding="utf-8")

                    new = self.create_package(root / "new", marker=b"-new")
                    self.assertEqual(installer.main(["--package-root", str(new), *common]), 0)
                    installer.assert_profiles_junction(link, profiles)
                    self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
                    new_launcher = (install_root / "My Bot 2.0.exe").read_bytes()

                    failed = self.create_package(root / "failed", marker=b"-failed")
                    with mock.patch.dict(os.environ, {"MYBOT_TEST_INSTALL_FAILURE_POINT": "after-registration"}):
                        self.assertEqual(installer.main(["--package-root", str(failed), *common]), 1)
                    self.assertEqual((install_root / "My Bot 2.0.exe").read_bytes(), new_launcher)
                    installer.assert_profiles_junction(link, profiles)
                    self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

                    self.assertEqual(installer.main(["--uninstall", "--install-directory", str(install_root)]), 0)
                    self.assertFalse(install_root.exists())
                    self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        finally:
            installer.delete_registry_tree(key_path)

    @unittest.skipUnless(os.name == "nt", "mklink junction creation is Windows-specific")
    def test_junction_creation_rejects_cmd_metacharacters_before_process_creation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mybot-junction-command-safety-") as folder:
            root = Path(folder)
            profiles = root / "external profiles with spaces"
            profiles.mkdir()

            # A normal install directory containing spaces must remain supported.
            safe_install = root / "installed app with spaces"
            safe_install.mkdir()
            link = installer.create_profiles_junction(safe_install, profiles)
            installer.assert_profiles_junction(link, profiles)
            installer.detach_profiles_junction(safe_install, profiles)
            self.assertFalse(os.path.lexists(link))

            marker = root / "command-must-not-run.txt"
            hostile_parts = ("&", "|", "<", ">", "^", "%", "!", "(", ")", '"', "\r", "\n")
            for metacharacter in hostile_parts:
                with self.subTest(metacharacter=repr(metacharacter)):
                    hostile_install = root / f"hostile{metacharacter}install"
                    with mock.patch.object(
                        installer.subprocess,
                        "run",
                        side_effect=AssertionError("cmd.exe must not be started"),
                    ) as run:
                        with self.assertRaisesRegex(ValueError, "Unsafe cmd.exe character"):
                            installer.create_profiles_junction(hostile_install, profiles)
                        run.assert_not_called()
                    self.assertFalse(os.path.lexists(hostile_install / "Profiles"))
                    self.assertFalse(marker.exists())

            # Re-check after canonicalization: a safe-looking alias can resolve
            # to a target whose name contains cmd.exe syntax.
            path_type = type(profiles)
            original_resolve = path_type.resolve

            def resolve_to_hostile_target(path: Path, strict: bool = False) -> Path:
                if path == profiles:
                    return root / "canonical&target"
                return original_resolve(path, strict=strict)

            with mock.patch.object(path_type, "resolve", resolve_to_hostile_target):
                with mock.patch.object(
                    installer.subprocess,
                    "run",
                    side_effect=AssertionError("cmd.exe must not be started"),
                ) as run:
                    with self.assertRaisesRegex(ValueError, "resolved Profiles target"):
                        installer.create_profiles_junction(safe_install, profiles)
                    run.assert_not_called()
            self.assertFalse(os.path.lexists(safe_install / "Profiles"))
            self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == "nt", "junction verification is Windows-specific")
    def test_foreign_junction_fails_closed_and_legacy_real_profiles_are_preserved(self) -> None:
        key_id = uuid.uuid4().hex
        key_path = rf"Software\MyBot2.0.Tests\{key_id}"
        try:
            with tempfile.TemporaryDirectory(prefix="mybot-python-legacy-") as folder:
                root = Path(folder)
                with self.isolated_environment(root, key_id) as (local, _roaming):
                    install_root = local / "Programs" / "My Bot 2.0"
                    legacy = install_root / "Profiles"
                    (legacy / "LegacyVillage").mkdir(parents=True)
                    (legacy / "MyVillage").mkdir()
                    (legacy / "profile.ini").write_text(
                        "[general]\r\ndefaultprofile=LegacyVillage\r\n", encoding="utf-8"
                    )
                    (legacy / "MyVillage" / "legacy-only.txt").write_text("legacy", encoding="utf-8")
                    package = self.create_package(root / "package")
                    common = ["--install-directory", str(install_root), "--no-launch"]
                    self.assertEqual(installer.main(["--package-root", str(package), *common]), 0)
                    profiles = local / "My Bot 2.0" / "Profiles"
                    self.assertEqual((profiles / "MyVillage" / "legacy-only.txt").read_text(), "legacy")
                    preserved = list((local / "My Bot 2.0").glob("Profiles.local-preserved-*"))
                    self.assertEqual(len(preserved), 1)
                    self.assertIn("LegacyVillage", (preserved[0] / "profile.ini").read_text())

                    link = install_root / "Profiles"
                    installer.detach_profiles_junction(install_root, profiles)
                    foreign = root / "foreign"
                    foreign.mkdir()
                    foreign_sentinel = foreign / "do-not-delete.txt"
                    foreign_sentinel.write_text("safe", encoding="utf-8")
                    command = Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"
                    result = subprocess.run(
                        [str(command), "/d", "/c", "mklink", "/J", str(link), str(foreign)],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(installer.main(["--uninstall", "--install-directory", str(install_root)]), 1)
                    self.assertEqual(foreign_sentinel.read_text(), "safe")
                    self.assertTrue(install_root.exists())
                    link.rmdir()
                    shutil.rmtree(install_root)
        finally:
            installer.delete_registry_tree(key_path)

    def test_command_launchers_prefer_python_not_powershell(self) -> None:
        for name in ("Install My Bot 2.0.cmd", "Uninstall My Bot 2.0.cmd"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("install_local_runtime.py", source)
            self.assertIn("py.exe -3", source)
            self.assertIn("python.exe", source)
            self.assertNotIn("powershell.exe", source.casefold())

    def test_running_process_guard_includes_descendants_of_installed_executables(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("if parent in found and pid not in found", source)
        self.assertIn("found.update(descendants)", source)

    def test_stage_copy_and_cleanup_share_the_transaction_boundary(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        transaction = source[source.index("snapshot = save_registration") :]
        self.assertLess(transaction.index("try:"), transaction.index("copy_payload(package_root, stage)"))
        self.assertIn("if stage.exists():\n            shutil.rmtree(stage)", transaction)
        self.assertIn("or repair.exists()", source)


if __name__ == "__main__":
    unittest.main()
