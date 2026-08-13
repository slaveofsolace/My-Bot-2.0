#!/usr/bin/env python3
"""Validate, install, or remove a reviewed My Bot 2.0 LocalRuntime package.

This is the non-CLR companion to Install-LocalRuntime.ps1.  It deliberately
uses only Python's standard library and native Win32 APIs so package recovery
does not depend on a healthy Windows PowerShell/.NET installation.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


PRODUCT_NAME = "My Bot 2.0"
PRODUCT_VERSION = "2.0.0"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\MyBot2.0"
TEST_KEY_RE = re.compile(r"^Software\\MyBot2\.0\.Tests\\[A-Fa-f0-9-]{32,36}$")
SAFE_PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
REQUIRED_PACKAGE_FILES = {
    "release-manifest.json",
    "config/binary-provenance.json",
    "My Bot 2.0.exe",
    "MyBot.run.exe",
    "MyBot.run.EngineProbe.exe",
    "MyBot.run.EngineProbe.exe.config",
    "MyBot.run.MiniGui.exe",
    "MyBot.run.txt",
    "tools/install_local_runtime.py",
}
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_relative(value: object) -> str:
    text = str(value).replace("\\", "/")
    pure = PurePosixPath(text)
    if (
        not text
        or text.startswith("/")
        or re.match(r"^[A-Za-z]:", text)
        or any(part in ("", ".", "..") for part in pure.parts)
    ):
        raise ValueError(f"The package manifest contains an unsafe path: {text}")
    return pure.as_posix()


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid JSON file {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def validate_package(package_root: Path) -> dict:
    package_root = package_root.resolve(strict=True)
    for relative in sorted(REQUIRED_PACKAGE_FILES):
        if not (package_root / Path(relative)).is_file():
            raise ValueError(
                "This installer must be run from an extracted reviewed "
                f"LocalRuntime package. Missing: {relative}"
            )
    if (package_root / "MyBot.run.txt").stat().st_size != 0:
        raise ValueError("MyBot.run.txt must remain exactly zero bytes.")

    manifest = load_json(package_root / "release-manifest.json")
    if manifest.get("mode") != "LocalRuntime" or manifest.get("source_tree_clean") is not True:
        raise ValueError("The package manifest is not a clean LocalRuntime release.")
    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise ValueError("The package manifest contains no file records.")

    expected: dict[str, tuple[str, int, str]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("The package manifest contains a non-object file record.")
        relative = normalized_relative(record.get("path", ""))
        if relative.casefold() == "profiles" or relative.casefold().startswith("profiles/"):
            raise ValueError("The LocalRuntime package manifest must exclude the mutable Profiles tree.")
        key = relative.casefold()
        if key in expected:
            raise ValueError(f"The package manifest contains a duplicate path: {relative}")
        byte_count = record.get("bytes")
        digest = record.get("sha256")
        if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0:
            raise ValueError(f"The package manifest contains an invalid byte count: {relative}")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None:
            raise ValueError(f"The package manifest contains an invalid SHA-256: {relative}")
        expected[key] = (relative, byte_count, digest.lower())

    packaged_profiles = package_root / "Profiles"
    if os.path.lexists(packaged_profiles):
        raise ValueError("The LocalRuntime package must not contain a Profiles entry.")

    actual: dict[str, Path] = {}
    for path in sorted(package_root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_symlink() or (getattr(path.lstat(), "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError(f"The package contains a reparse point: {path}")
        if not path.is_file() or path == package_root / "release-manifest.json":
            continue
        relative = path.relative_to(package_root).as_posix()
        key = relative.casefold()
        if key in actual:
            raise ValueError(f"The package contains a duplicate path: {relative}")
        actual[key] = path

    for key, (relative, byte_count, digest) in expected.items():
        path = actual.get(key)
        if path is None:
            raise ValueError(f"A package file recorded by the manifest is missing: {relative}")
        if path.stat().st_size != byte_count:
            raise ValueError(f"Package file byte count mismatch: {relative}")
        if sha256(path) != digest:
            raise ValueError(f"Package file SHA-256 mismatch: {relative}")
    extra = sorted(set(actual) - set(expected))
    if extra:
        relative = actual[extra[0]].relative_to(package_root).as_posix()
        raise ValueError(f"The package contains a file not recorded by the manifest: {relative}")

    provenance = load_json(package_root / "config" / "binary-provenance.json")
    artifacts = provenance.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("Binary provenance has no artifact records.")
    launcher_record = next(
        (
            item
            for item in artifacts
            if isinstance(item, dict)
            and str(item.get("path", "")).replace("\\", "/").casefold() == "my bot 2.0.exe"
        ),
        None,
    )
    if launcher_record is None:
        raise ValueError("Binary provenance does not contain My Bot 2.0.exe.")
    launcher = package_root / "My Bot 2.0.exe"
    if (
        launcher_record.get("bytes") != launcher.stat().st_size
        or str(launcher_record.get("sha256", "")).lower() != sha256(launcher)
    ):
        raise ValueError("My Bot 2.0.exe does not match binary provenance.")
    return manifest


def default_profile_name(ini_path: Path) -> str | None:
    section = ""
    for raw in ini_path.read_text(encoding="utf-8-sig", errors="strict").splitlines():
        line = raw.strip()
        match = re.fullmatch(r"\[([^]]+)]", line)
        if match:
            section = match.group(1)
            continue
        if section.casefold() == "general":
            match = re.match(r"defaultprofile\s*=(.*)$", line, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return None


def validate_profiles(root: Path) -> str:
    if not root.is_dir():
        raise ValueError(f"Profiles directory does not exist: {root}")
    ini_path = root / "profile.ini"
    if not ini_path.is_file():
        raise ValueError(f"Profiles directory is missing profile.ini: {root}")
    profile = default_profile_name(ini_path)
    if profile is None or SAFE_PROFILE_RE.fullmatch(profile) is None:
        raise ValueError(
            "profile.ini must select a simple defaultprofile using only letters, "
            "numbers, dot, underscore, or hyphen."
        )
    if not (root / profile).is_dir():
        raise ValueError(f"profile.ini selects '{profile}', but that profile directory is missing.")
    return profile


def initialize_profiles(user_data_root: Path, source: Path | None) -> Path:
    profiles_root = user_data_root / "Profiles"
    user_data_root.mkdir(parents=True, exist_ok=True)
    if source is not None:
        source = source.resolve(strict=True)
        validate_profiles(source)
        if source == profiles_root.resolve(strict=False):
            raise ValueError("ProfileSourceDirectory already points to the installed profiles directory.")
        if profiles_root.exists() and any(profiles_root.iterdir()):
            raise ValueError(f"Profile migration will not overwrite existing per-user data at {profiles_root}")
        stage = user_data_root / f".Profiles.migration-{uuid.uuid4().hex}"
        try:
            shutil.copytree(source, stage, symlinks=False)
            validate_profiles(stage)
            if profiles_root.exists():
                profiles_root.rmdir()
            stage.replace(profiles_root)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    else:
        profiles_root.mkdir(parents=True, exist_ok=True)
        if not any(profiles_root.iterdir()):
            (profiles_root / "MyVillage").mkdir()
            (profiles_root / "profile.ini").write_text(
                "[general]\r\ndefaultprofile=MyVillage\r\n", encoding="utf-8", newline=""
            )
    validate_profiles(profiles_root)
    return profiles_root


def is_reparse_point(path: Path) -> bool:
    try:
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return False


def is_directory_junction(path: Path) -> bool:
    if not os.path.lexists(path) or not is_reparse_point(path):
        return False
    checker = getattr(os.path, "isjunction", None)
    if checker is not None:
        return bool(checker(path))
    return getattr(path.lstat(), "st_reparse_tag", 0) == 0xA0000003


def assert_profiles_junction(link: Path, profiles_root: Path) -> None:
    if not is_directory_junction(link):
        raise ValueError(f"Installed Profiles is not a directory junction: {link}")
    expected = profiles_root.resolve(strict=True)
    try:
        actual = link.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"Installed Profiles junction has no valid target: {link}") from error
    if os.path.normcase(str(actual)) != os.path.normcase(str(expected)):
        raise ValueError(f"Installed Profiles junction targets {actual}, expected {expected}")


def create_profiles_junction(install_root: Path, profiles_root: Path) -> Path:
    link = install_root / "Profiles"
    if os.path.lexists(link):
        raise ValueError(f"Refusing to replace an existing installed Profiles entry: {link}")
    target = profiles_root.resolve(strict=True)
    command = Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"
    result = subprocess.run(
        [str(command), "/d", "/c", "mklink", "/J", str(link), str(target)],
        cwd=install_root,
        capture_output=True,
        text=True,
        timeout=15,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        raise ValueError(f"Could not create the installed Profiles junction: {detail}")
    assert_profiles_junction(link, target)
    return link


def detach_profiles_junction(install_root: Path, profiles_root: Path) -> bool:
    link = install_root / "Profiles"
    if not os.path.lexists(link):
        return False
    assert_profiles_junction(link, profiles_root)
    link.rmdir()
    if os.path.lexists(link):
        raise ValueError(f"Installed Profiles junction could not be detached: {link}")
    return True


def assert_no_reparse_tree(root: Path) -> None:
    if is_reparse_point(root):
        raise ValueError(f"Legacy Profiles contains a reparse point: {root}")
    for path in root.rglob("*"):
        if path.is_symlink() or is_reparse_point(path):
            raise ValueError(f"Legacy Profiles contains a reparse point: {path}")


def migrate_legacy_installed_profiles(
    install_root: Path, profiles_root: Path, user_data_root: Path
) -> Path | None:
    """Copy missing legacy data without overwrite and preserve the source on any collision."""
    legacy = install_root / "Profiles"
    if not os.path.lexists(legacy):
        return None
    if is_directory_junction(legacy):
        assert_profiles_junction(legacy, profiles_root)
        return None
    if not legacy.is_dir() or is_reparse_point(legacy):
        raise ValueError(f"Installed Profiles is neither the expected junction nor a real directory: {legacy}")
    assert_no_reparse_tree(legacy)

    conflicts = False
    for source in sorted(legacy.rglob("*"), key=lambda item: item.as_posix().casefold()):
        relative = source.relative_to(legacy)
        target = profiles_root / relative
        if not os.path.lexists(target):
            continue
        if source.is_dir() != target.is_dir():
            conflicts = True
        elif source.is_file() and (source.stat().st_size != target.stat().st_size or sha256(source) != sha256(target)):
            conflicts = True

    preserved: Path | None = None
    if conflicts:
        preserved = user_data_root / f"Profiles.local-preserved-{uuid.uuid4().hex}"
        shutil.copytree(legacy, preserved, symlinks=False)
        assert_no_reparse_tree(preserved)

    for source in sorted(legacy.rglob("*"), key=lambda item: (len(item.parts), item.as_posix().casefold())):
        relative = source.relative_to(legacy)
        target = profiles_root / relative
        if os.path.lexists(target):
            continue
        if source.is_dir():
            target.mkdir()
        elif target.parent.is_dir():
            shutil.copy2(source, target)
    validate_profiles(profiles_root)
    return preserved


def remove_install_payload(install_root: Path, profiles_root: Path, *, allow_legacy: bool) -> None:
    if not install_root.is_dir():
        return
    link = install_root / "Profiles"
    if os.path.lexists(link):
        if is_directory_junction(link):
            detach_profiles_junction(install_root, profiles_root)
        elif allow_legacy and link.is_dir() and not is_reparse_point(link):
            assert_no_reparse_tree(link)
            shutil.rmtree(link)
        else:
            raise ValueError(f"Refusing to remove an unverified installed Profiles entry: {link}")
    shutil.rmtree(install_root)


if os.name == "nt":
    import winreg

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

        @classmethod
        def parse(cls, value: str) -> "GUID":
            parsed = uuid.UUID(value)
            raw = parsed.bytes_le
            return cls.from_buffer_copy(raw)


    CLSCTX_INPROC_SERVER = 1
    COINIT_APARTMENTTHREADED = 2
    STGM_READ = 0
    SLGP_RAWPATH = 4
    SW_SHOWNORMAL = 1
    CLSID_SHELL_LINK = GUID.parse("00021401-0000-0000-C000-000000000046")
    IID_ISHELL_LINK_W = GUID.parse("000214F9-0000-0000-C000-000000000046")
    IID_IPERSIST_FILE = GUID.parse("0000010b-0000-0000-C000-000000000046")


    def _check_hresult(value: int, label: str) -> None:
        if value < 0:
            raise OSError(f"{label} failed with HRESULT 0x{value & 0xFFFFFFFF:08x}")


    def _method(pointer: ctypes.c_void_p, index: int, restype, *argtypes):
        vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
        return prototype(vtable[index])


    def _release(pointer: ctypes.c_void_p) -> None:
        if pointer:
            _method(pointer, 2, wintypes.ULONG)(pointer)


    def _shell_link() -> ctypes.c_void_p:
        pointer = ctypes.c_void_p()
        result = ctypes.windll.ole32.CoCreateInstance(
            ctypes.byref(CLSID_SHELL_LINK),
            None,
            CLSCTX_INPROC_SERVER,
            ctypes.byref(IID_ISHELL_LINK_W),
            ctypes.byref(pointer),
        )
        _check_hresult(result, "CoCreateInstance(IShellLinkW)")
        return pointer


    def _persist_file(shell_link: ctypes.c_void_p) -> ctypes.c_void_p:
        pointer = ctypes.c_void_p()
        result = _method(
            shell_link, 0, ctypes.c_long, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)
        )(shell_link, ctypes.byref(IID_IPERSIST_FILE), ctypes.byref(pointer))
        _check_hresult(result, "QueryInterface(IPersistFile)")
        return pointer


    def create_shortcut(
        path: Path,
        target: Path,
        working_directory: Path,
        arguments: str,
        description: str,
        icon: Path,
    ) -> None:
        ctypes.windll.ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
        shell = _shell_link()
        persist = ctypes.c_void_p()
        try:
            for index, value, label in (
                (20, str(target), "IShellLinkW.SetPath"),
                (9, str(working_directory), "IShellLinkW.SetWorkingDirectory"),
                (11, arguments, "IShellLinkW.SetArguments"),
                (7, description, "IShellLinkW.SetDescription"),
            ):
                result = _method(shell, index, ctypes.c_long, wintypes.LPCWSTR)(shell, value)
                _check_hresult(result, label)
            result = _method(shell, 17, ctypes.c_long, wintypes.LPCWSTR, ctypes.c_int)(
                shell, str(icon), 0
            )
            _check_hresult(result, "IShellLinkW.SetIconLocation")
            result = _method(shell, 15, ctypes.c_long, ctypes.c_int)(shell, SW_SHOWNORMAL)
            _check_hresult(result, "IShellLinkW.SetShowCmd")
            persist = _persist_file(shell)
            path.parent.mkdir(parents=True, exist_ok=True)
            result = _method(persist, 6, ctypes.c_long, wintypes.LPCWSTR, wintypes.BOOL)(
                persist, str(path), True
            )
            _check_hresult(result, "IPersistFile.Save")
        finally:
            _release(persist)
            _release(shell)
            ctypes.windll.ole32.CoUninitialize()


    def read_shortcut(path: Path) -> tuple[Path, Path, str]:
        ctypes.windll.ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
        shell = _shell_link()
        persist = ctypes.c_void_p()
        try:
            persist = _persist_file(shell)
            result = _method(persist, 5, ctypes.c_long, wintypes.LPCWSTR, wintypes.DWORD)(
                persist, str(path), STGM_READ
            )
            _check_hresult(result, "IPersistFile.Load")
            target = ctypes.create_unicode_buffer(32768)
            working = ctypes.create_unicode_buffer(32768)
            arguments = ctypes.create_unicode_buffer(32768)
            _check_hresult(
                _method(shell, 3, ctypes.c_long, wintypes.LPWSTR, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)(
                    shell, target, len(target), None, SLGP_RAWPATH
                ),
                "IShellLinkW.GetPath",
            )
            _check_hresult(
                _method(shell, 8, ctypes.c_long, wintypes.LPWSTR, ctypes.c_int)(
                    shell, working, len(working)
                ),
                "IShellLinkW.GetWorkingDirectory",
            )
            _check_hresult(
                _method(shell, 10, ctypes.c_long, wintypes.LPWSTR, ctypes.c_int)(
                    shell, arguments, len(arguments)
                ),
                "IShellLinkW.GetArguments",
            )
            return Path(target.value), Path(working.value), arguments.value
        finally:
            _release(persist)
            _release(shell)
            ctypes.windll.ole32.CoUninitialize()


    @dataclass
    class RegistrationSnapshot:
        launch_shortcut: bytes | None
        uninstall_shortcut: bytes | None
        registry_values: dict[str, tuple[object, int]] | None


    def registry_values(key_path: str) -> dict[str, tuple[object, int]] | None:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
        except FileNotFoundError:
            return None
        values: dict[str, tuple[object, int]] = {}
        with key:
            index = 0
            while True:
                try:
                    name, value, kind = winreg.EnumValue(key, index)
                except OSError:
                    break
                values[name] = (value, kind)
                index += 1
        return values


    def delete_registry_tree(key_path: str) -> None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
                while True:
                    try:
                        child = winreg.EnumKey(key, 0)
                    except OSError:
                        break
                    delete_registry_tree(key_path + "\\" + child)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        except FileNotFoundError:
            return


    def save_registration(shortcut: Path, uninstall_shortcut: Path, key_path: str) -> RegistrationSnapshot:
        return RegistrationSnapshot(
            shortcut.read_bytes() if shortcut.is_file() else None,
            uninstall_shortcut.read_bytes() if uninstall_shortcut.is_file() else None,
            registry_values(key_path),
        )


    def remove_registration(shortcut: Path, uninstall_shortcut: Path, key_path: str) -> None:
        shortcut.unlink(missing_ok=True)
        uninstall_shortcut.unlink(missing_ok=True)
        delete_registry_tree(key_path)
        try:
            shortcut.parent.rmdir()
        except OSError:
            pass


    def restore_registration(
        snapshot: RegistrationSnapshot,
        shortcut: Path,
        uninstall_shortcut: Path,
        key_path: str,
    ) -> None:
        remove_registration(shortcut, uninstall_shortcut, key_path)
        if snapshot.launch_shortcut is not None or snapshot.uninstall_shortcut is not None:
            shortcut.parent.mkdir(parents=True, exist_ok=True)
        if snapshot.launch_shortcut is not None:
            shortcut.write_bytes(snapshot.launch_shortcut)
        if snapshot.uninstall_shortcut is not None:
            uninstall_shortcut.write_bytes(snapshot.uninstall_shortcut)
        if snapshot.registry_values is not None:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
                for name, (value, kind) in snapshot.registry_values.items():
                    winreg.SetValueEx(key, name, 0, kind, value)


    def install_registration(
        install_root: Path,
        shortcut: Path,
        uninstall_shortcut: Path,
        key_path: str,
    ) -> None:
        launcher = install_root / "My Bot 2.0.exe"
        installer = install_root / "tools" / "install_local_runtime.py"
        python = Path(sys.executable).resolve()
        uninstall_arguments = f'"{installer}" --uninstall --install-directory "{install_root}"'
        create_shortcut(shortcut, launcher, install_root, "", "Launch My Bot 2.0", launcher)
        create_shortcut(
            uninstall_shortcut,
            python,
            install_root,
            uninstall_arguments,
            "Remove My Bot 2.0 for this Windows user",
            launcher,
        )
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
            values = {
                "DisplayName": (PRODUCT_NAME, winreg.REG_SZ),
                "DisplayVersion": (PRODUCT_VERSION, winreg.REG_SZ),
                "Publisher": ("My Bot 2.0 contributors", winreg.REG_SZ),
                "InstallLocation": (str(install_root), winreg.REG_SZ),
                "DisplayIcon": (f"{launcher},0", winreg.REG_SZ),
                "UninstallString": (f'"{python}" {uninstall_arguments}', winreg.REG_SZ),
                "NoModify": (1, winreg.REG_DWORD),
                "NoRepair": (1, winreg.REG_DWORD),
            }
            for name, (value, kind) in values.items():
                winreg.SetValueEx(key, name, 0, kind, value)


    def assert_registration(
        install_root: Path,
        shortcut: Path,
        uninstall_shortcut: Path,
        key_path: str,
    ) -> None:
        launcher = (install_root / "My Bot 2.0.exe").resolve()
        installer = (install_root / "tools" / "install_local_runtime.py").resolve()
        python = Path(sys.executable).resolve()
        launch_target, launch_working, launch_args = read_shortcut(shortcut)
        if launch_target.resolve() != launcher or launch_working.resolve() != install_root.resolve() or launch_args:
            raise ValueError("The Start Menu shortcut target, working directory, or arguments are incorrect.")
        uninstall_target, uninstall_working, uninstall_args = read_shortcut(uninstall_shortcut)
        expected_args = f'"{installer}" --uninstall --install-directory "{install_root}"'
        if (
            uninstall_target.resolve() != python
            or uninstall_working.resolve() != install_root.resolve()
            or uninstall_args != expected_args
        ):
            raise ValueError("The uninstall shortcut target, working directory, or arguments are incorrect.")
        values = registry_values(key_path)
        if values is None:
            raise ValueError("The per-user uninstall registration was not created.")
        expected_command = f'"{python}" {expected_args}'
        if values.get("DisplayName", (None,))[0] != PRODUCT_NAME:
            raise ValueError("The uninstall registration DisplayName is incorrect.")
        if Path(str(values.get("InstallLocation", ("",))[0])).resolve() != install_root.resolve():
            raise ValueError("The uninstall registration InstallLocation is incorrect.")
        if values.get("UninstallString", (None,))[0] != expected_command:
            raise ValueError("The uninstall registration command is incorrect.")


    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]


    def owned_processes(install_root: Path) -> list[int]:
        prefix = str(install_root.resolve()).rstrip("\\/") + os.sep
        prefix = prefix.casefold()
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        kernel32.Process32FirstW.restype = wintypes.BOOL
        kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        kernel32.Process32NextW.restype = wintypes.BOOL
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == INVALID_HANDLE_VALUE:
            raise ctypes.WinError()
        processes: dict[int, tuple[int, str | None]] = {}
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            success = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while success:
                process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, entry.th32ProcessID)
                if process:
                    try:
                        size = wintypes.DWORD(32768)
                        buffer = ctypes.create_unicode_buffer(size.value)
                        if kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
                            candidate = os.path.abspath(buffer.value).casefold()
                            processes[int(entry.th32ProcessID)] = (
                                int(entry.th32ParentProcessID),
                                candidate,
                            )
                    finally:
                        kernel32.CloseHandle(process)
                else:
                    processes[int(entry.th32ProcessID)] = (int(entry.th32ParentProcessID), None)
                success = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(snapshot)
        found = {
            pid for pid, (_parent, image) in processes.items() if image is not None and image.startswith(prefix)
        }
        while True:
            descendants = {
                pid for pid, (parent, _image) in processes.items() if parent in found and pid not in found
            }
            if not descendants:
                break
            found.update(descendants)
        return sorted(found)


else:  # pragma: no cover - the product is Windows-only
    RegistrationSnapshot = object  # type: ignore[misc,assignment]

    def owned_processes(_install_root: Path) -> list[int]:
        return []


def safe_install_context(args: argparse.Namespace) -> tuple[Path, Path, Path, Path, str]:
    if os.name != "nt":
        raise RuntimeError("My Bot 2.0 LocalRuntime installation is supported only on Windows.")
    local_app_data = Path(os.environ["LOCALAPPDATA"]).resolve()
    app_data = Path(os.environ["APPDATA"]).resolve()
    programs_root = (local_app_data / "Programs").resolve()
    install_root = Path(args.install_directory).resolve() if args.install_directory else programs_root / PRODUCT_NAME
    try:
        install_root.relative_to(programs_root)
    except ValueError as error:
        raise ValueError(f"InstallDirectory must be below {programs_root}") from error
    if install_root == programs_root:
        raise ValueError(f"InstallDirectory must be below {programs_root}")
    user_data_root = local_app_data / PRODUCT_NAME
    start_menu = app_data / "Microsoft" / "Windows" / "Start Menu" / "Programs" / PRODUCT_NAME
    key_path = UNINSTALL_KEY

    test_key = os.environ.get("MYBOT_TEST_UNINSTALL_REGISTRY_PATH", "")
    failure_point = os.environ.get("MYBOT_TEST_INSTALL_FAILURE_POINT", "")
    if test_key or failure_point:
        if os.environ.get("MYBOT_RUN_PYTHON_INTEGRATION") != "1":
            raise ValueError("Installer test overrides require MYBOT_RUN_PYTHON_INTEGRATION=1.")
        test_root_text = os.environ.get("MYBOT_INSTALL_TEST_ROOT", "")
        if not test_root_text:
            raise ValueError("Installer mutation tests require an isolated MYBOT_INSTALL_TEST_ROOT.")
        test_root = Path(test_root_text).resolve()
        for value in (local_app_data, app_data):
            try:
                value.relative_to(test_root)
            except ValueError as error:
                raise ValueError(
                    "Installer mutation tests require APPDATA and LOCALAPPDATA below MYBOT_INSTALL_TEST_ROOT."
                ) from error
        if not TEST_KEY_RE.fullmatch(test_key):
            raise ValueError("Installer mutation tests require a GUID-scoped HKCU test key.")
        if failure_point not in ("", "after-registration"):
            raise ValueError(f"Unknown installer integration failure point: {failure_point}")
        key_path = test_key
    return install_root, user_data_root, start_menu / f"{PRODUCT_NAME}.lnk", start_menu / f"Uninstall {PRODUCT_NAME}.lnk", key_path


def copy_payload(package_root: Path, stage: Path) -> None:
    def reject_links(path: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            candidate = Path(path) / name
            if candidate.is_symlink() or (
                getattr(candidate.lstat(), "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise ValueError(f"The package contains a reparse point: {candidate}")
        return ignored

    shutil.copytree(package_root, stage, symlinks=False, ignore=reject_links)


def install(args: argparse.Namespace) -> None:
    package_root = Path(args.package_root).resolve() if args.package_root else Path(__file__).resolve().parents[1]
    install_root, user_data_root, shortcut, uninstall_shortcut, key_path = safe_install_context(args)
    if args.uninstall:
        running = owned_processes(install_root)
        if running:
            raise ValueError(f"Close My Bot 2.0 before uninstalling. Running PID(s): {', '.join(map(str, running))}")
        profiles_root = initialize_profiles(user_data_root, None)
        preserved = migrate_legacy_installed_profiles(install_root, profiles_root, user_data_root)
        remove_registration(shortcut, uninstall_shortcut, key_path)
        if install_root.is_dir():
            remove_install_payload(install_root, profiles_root, allow_legacy=True)
        print(f"{PRODUCT_NAME} was removed for the current Windows user.")
        print(f"Profiles were retained at {profiles_root}")
        if preserved is not None:
            print(f"Conflicting legacy profile data was preserved at {preserved}")
        return

    validate_package(package_root)
    if args.validate_only:
        print("LocalRuntime package integrity verified.")
        return
    running = owned_processes(install_root)
    if running:
        raise ValueError(
            "Close the installed My Bot 2.0 before updating it. "
            f"Running PID(s): {', '.join(map(str, running))}"
        )
    source = Path(args.profile_source_directory) if args.profile_source_directory else None
    profiles_root = initialize_profiles(user_data_root, source)
    legacy_preserved = migrate_legacy_installed_profiles(install_root, profiles_root, user_data_root)

    parent = install_root.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage = parent / f".{PRODUCT_NAME}.install-{uuid.uuid4().hex}"
    backup = parent / f".{PRODUCT_NAME}.previous"
    repair = parent / f".{PRODUCT_NAME}.repair-required.json"
    if stage.exists() or backup.exists() or repair.exists():
        raise ValueError("A previous installation transaction needs repair before continuing.")
    snapshot = save_registration(shortcut, uninstall_shortcut, key_path)
    prior_moved = False
    new_installed = False
    try:
        copy_payload(package_root, stage)
        if install_root.exists():
            install_root.replace(backup)
            prior_moved = True
        stage.replace(install_root)
        new_installed = True
        create_profiles_junction(install_root, profiles_root)
        assert_profiles_junction(install_root / "Profiles", profiles_root)
        install_registration(install_root, shortcut, uninstall_shortcut, key_path)
        if os.environ.get("MYBOT_TEST_INSTALL_FAILURE_POINT") == "after-registration":
            raise RuntimeError("Injected installer integration failure after registration mutation.")
        assert_registration(install_root, shortcut, uninstall_shortcut, key_path)
        if backup.exists():
            remove_install_payload(backup, profiles_root, allow_legacy=True)
        repair.unlink(missing_ok=True)
    except Exception as install_error:
        rollback_errors: list[str] = []
        try:
            restore_registration(snapshot, shortcut, uninstall_shortcut, key_path)
        except Exception as error:  # pragma: no cover - exercised only on system failure
            rollback_errors.append(f"Registration rollback failed: {error}")
        if new_installed and install_root.exists():
            try:
                remove_install_payload(install_root, profiles_root, allow_legacy=False)
            except Exception as error:  # pragma: no cover
                rollback_errors.append(f"New payload rollback failed: {error}")
        if prior_moved and backup.exists():
            try:
                backup.replace(install_root)
            except Exception as error:  # pragma: no cover
                rollback_errors.append(f"Prior payload restore failed: {error}")
        if rollback_errors:
            repair.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "product": PRODUCT_NAME,
                        "install_root": str(install_root),
                        "preserved_payload_backup": str(backup),
                        "original_error": str(install_error),
                        "rollback_errors": rollback_errors,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            raise RuntimeError(
                f"Installation failed and rollback needs repair. Recovery state: {repair}. "
                + " ".join(rollback_errors)
            ) from install_error
        repair.unlink(missing_ok=True)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)

    print(f"{PRODUCT_NAME} {PRODUCT_VERSION} installed at {install_root}")
    print(f"Profiles: {profiles_root}")
    if legacy_preserved is not None:
        print(f"Conflicting legacy profile data was preserved at {legacy_preserved}")
    print("Open Start and type: My Bot 2.0")
    if not args.no_launch:
        subprocess.Popen(
            [str(install_root / "My Bot 2.0.exe")],
            cwd=install_root,
            close_fds=True,
            creationflags=CREATE_NO_WINDOW,
        )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--install-directory", "-InstallDirectory")
    result.add_argument("--profile-source-directory", "-ProfileSourceDirectory")
    result.add_argument("--package-root")
    result.add_argument("--uninstall", "-Uninstall", action="store_true")
    result.add_argument("--validate-only", "-ValidateOnly", action="store_true")
    result.add_argument("--no-launch", "-NoLaunch", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    try:
        install(parser().parse_args(argv))
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
