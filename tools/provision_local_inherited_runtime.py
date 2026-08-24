#!/usr/bin/env python3
"""Provision the exact pinned inherited runtime into an owner-local island.

The public package never contains this island.  The provisioner reads only an
already-present local Git object, exports that exact commit, verifies the full
runtime tuple, and writes an owner-local attestation.  It never fetches, builds,
patches, signs, or rewrites the inherited executables.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
from typing import Mapping
import uuid


PINNED_COMMIT = "8ad6e5a552347acc2fcb8048d30262e2735a0c33"
PINNED_TREE = "3e621065821be85d5932bd7e1f69ef7f22bc5b3d"
ATTESTATION_SCHEMA = "my-bot-local-inherited-runtime-v1"
ISLAND_DIRECTORY_NAME = f"pinned-{PINNED_COMMIT}"
ATTESTATION_FILE_NAME = "local-inherited-runtime.local.json"
EXPECTED_TREE_FILE_COUNT = 2_506
EXPECTED_TREE_MANIFEST_SHA256 = "0a807845216b84fe2f703f9c5a4f6a2f9a7c5547bb27875bfd886e7df0f77757"

# All executable parts of the pinned upstream release are attested even though
# the product launches only the full GUI host.  This prevents a partial or mixed
# upstream release from being mistaken for the reviewed local runtime.
RUNTIME_TUPLE: Mapping[str, tuple[int, str]] = {
    "MyBot.run.exe": (
        2_957_312,
        "06eaa33280b7cfbba6efdbbf89a7796e2996b706e0a1dd1cb53b8e4c07353eb2",
    ),
    "MyBot.run.MiniGui.exe": (
        1_634_304,
        "ae26c098ceb3c74e3d7f567834d9135257e094172e32140f4a5b615eaf90ceda",
    ),
    "MyBot.run.Watchdog.exe": (
        1_159_168,
        "d4fa5bce748de1fd6f85ef85207c51433cb29af6204ae369145821a664f6612e",
    ),
    "MyBot.run.Wmi.exe": (
        1_154_048,
        "4beb637917e5303a92d59fcdfef176e8e568cfb450635a0941268e6336a35207",
    ),
    "lib/MyBot.run.dll": (
        2_761_728,
        "347b204a15fd56800130740aff639c7608621206482f07298c595a363e328699",
    ),
    "MyBot.run.txt": (
        0,
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    ),
}


class ProvisionError(RuntimeError):
    """A local runtime source, island, or attestation failed closed."""


def fixed_island_root(environment: Mapping[str, str] | None = None) -> Path:
    values = os.environ if environment is None else environment
    local_app_data = values.get("LOCALAPPDATA", "").strip()
    if not local_app_data:
        raise ProvisionError("LOCALAPPDATA is unavailable; the fixed local runtime island cannot be resolved")
    return (
        Path(local_app_data)
        / "My Bot 2.0"
        / "LocalInheritedRuntime"
        / ISLAND_DIRECTORY_NAME
    ).absolute()


def _git(repository: Path, *arguments: str, binary: bool = False) -> str | bytes:
    command = ["git", "-C", str(repository), *arguments]
    result = subprocess.run(
        command,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=not binary,
        timeout=30,
    )
    if result.returncode != 0:
        stderr = result.stderr if isinstance(result.stderr, str) else result.stderr.decode("utf-8", "replace")
        raise ProvisionError(f"Local Git verification failed: {stderr.strip() or 'unknown Git error'}")
    return result.stdout


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def runtime_tree_manifest(root: Path) -> tuple[int, str]:
    """Hash the exact extracted file set, excluding only the local attestation."""
    is_junction = getattr(os.path, "isjunction", lambda _value: False)
    if root.is_symlink() or is_junction(root):
        raise ProvisionError(f"The local runtime tree is redirected: {root}")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ProvisionError(f"The local runtime tree is not a regular directory: {root}")
    paths: list[Path] = []
    for directory, names, files in os.walk(root, topdown=True, followlinks=False):
        directory_path = Path(directory)
        for name in names:
            child = directory_path / name
            if child.is_symlink() or is_junction(child):
                raise ProvisionError(f"Inherited runtime tree contains a redirected directory: {child.relative_to(root)}")
        for name in files:
            child = directory_path / name
            relative = child.relative_to(root).as_posix()
            if relative == ATTESTATION_FILE_NAME:
                continue
            if child.is_symlink() or not child.is_file():
                raise ProvisionError(f"Inherited runtime tree contains a redirected or non-file entry: {relative}")
            if "\\" in relative or any(ord(character) < 32 for character in relative):
                raise ProvisionError(f"Inherited runtime tree contains an unsafe file name: {relative!r}")
            paths.append(child)
    paths.sort(key=lambda value: value.relative_to(root).as_posix().casefold().encode("utf-8"))
    digest = hashlib.sha256()
    for path in paths:
        relative = path.relative_to(root).as_posix().casefold()
        size = path.stat().st_size
        digest.update(f"{relative}\t{size}\t{_sha256_file(path)}\n".encode("utf-8"))
    return len(paths), digest.hexdigest()


def verify_runtime_tree(root: Path) -> dict[str, object]:
    file_count, manifest_hash = runtime_tree_manifest(root)
    if file_count != EXPECTED_TREE_FILE_COUNT or manifest_hash != EXPECTED_TREE_MANIFEST_SHA256:
        raise ProvisionError(
            "Complete inherited runtime tree mismatch: expected "
            f"{EXPECTED_TREE_FILE_COUNT}/{EXPECTED_TREE_MANIFEST_SHA256}, found {file_count}/{manifest_hash}"
        )
    return {"file_count": file_count, "manifest_sha256": manifest_hash}


def verify_local_git_source(repository: Path) -> dict[str, object]:
    repository = repository.resolve(strict=True)
    if not repository.is_dir():
        raise ProvisionError(f"The local Git source is not a directory: {repository}")
    object_type = str(_git(repository, "cat-file", "-t", PINNED_COMMIT)).strip()
    if object_type != "commit":
        raise ProvisionError(f"Pinned source object is not a commit: {PINNED_COMMIT}")
    tree = str(_git(repository, "rev-parse", f"{PINNED_COMMIT}^{{tree}}")).strip().lower()
    if tree != PINNED_TREE:
        raise ProvisionError(f"Pinned source tree mismatch: expected {PINNED_TREE}, found {tree}")

    records: list[dict[str, object]] = []
    for relative, (expected_size, expected_hash) in RUNTIME_TUPLE.items():
        blob = _git(repository, "cat-file", "blob", f"{PINNED_COMMIT}:{relative}", binary=True)
        assert isinstance(blob, bytes)
        actual_hash = _sha256_bytes(blob)
        if len(blob) != expected_size or actual_hash != expected_hash:
            raise ProvisionError(
                f"Pinned Git blob mismatch for {relative}: expected {expected_size}/{expected_hash}, "
                f"found {len(blob)}/{actual_hash}"
            )
        records.append({"path": relative, "size": expected_size, "sha256": expected_hash})
    return {
        "commit": PINNED_COMMIT,
        "tree": tree,
        "runtime_tuple": records,
        "tree_file_count": EXPECTED_TREE_FILE_COUNT,
        "tree_manifest_sha256": EXPECTED_TREE_MANIFEST_SHA256,
    }


def verify_runtime_tuple(root: Path) -> list[dict[str, object]]:
    is_junction = getattr(os.path, "isjunction", lambda _value: False)
    if root.is_symlink() or is_junction(root):
        raise ProvisionError(f"The local runtime island is redirected: {root}")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ProvisionError(f"The local runtime island is not a regular directory: {root}")
    records: list[dict[str, object]] = []
    for relative, (expected_size, expected_hash) in RUNTIME_TUPLE.items():
        path = root / Path(PurePosixPath(relative))
        if not path.is_file() or path.is_symlink():
            raise ProvisionError(f"Required inherited runtime file is missing or redirected: {relative}")
        actual_size = path.stat().st_size
        actual_hash = _sha256_file(path)
        if actual_size != expected_size or actual_hash != expected_hash:
            raise ProvisionError(
                f"Inherited runtime mismatch for {relative}: expected {expected_size}/{expected_hash}, "
                f"found {actual_size}/{actual_hash}"
            )
        records.append({"path": relative, "size": expected_size, "sha256": expected_hash})
    return records


def _attestation_document(records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "anti_copycat_bypass": False,
        "local_only": True,
        "marker_semantics": "exact-zero-byte-upstream-marker",
        "runtime_tuple": records,
        "schema": ATTESTATION_SCHEMA,
        "source_commit": PINNED_COMMIT,
        "source_kind": "owner-supplied-local-git-object",
        "source_tree": PINNED_TREE,
        "tree_file_count": EXPECTED_TREE_FILE_COUNT,
        "tree_manifest_sha256": EXPECTED_TREE_MANIFEST_SHA256,
    }


def validate_attestation(root: Path) -> dict[str, object]:
    is_junction = getattr(os.path, "isjunction", lambda _value: False)
    if root.is_symlink() or is_junction(root):
        raise ProvisionError(f"Owner-local inherited runtime island is redirected: {root}")
    root = root.resolve(strict=True)
    attestation_path = root / ATTESTATION_FILE_NAME
    if not attestation_path.is_file() or attestation_path.is_symlink():
        raise ProvisionError(f"Owner-local inherited runtime attestation is missing: {attestation_path}")
    if attestation_path.stat().st_size > 64 * 1024:
        raise ProvisionError("Owner-local inherited runtime attestation is unexpectedly large")
    try:
        document = json.loads(attestation_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProvisionError(f"Owner-local inherited runtime attestation is unreadable: {error}") from error
    verify_runtime_tree(root)
    records = verify_runtime_tuple(root)
    expected = _attestation_document(records)
    if document != expected:
        raise ProvisionError("Owner-local inherited runtime attestation does not match the exact pinned tuple")
    return document


def _safe_extract(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive_path, "r:") as archive:
        members = archive.getmembers()
        for member in members:
            name = member.name
            path = PurePosixPath(name)
            if (
                not name
                or "\\" in name
                or path.is_absolute()
                or ".." in path.parts
                or ":" in path.parts[0]
                or member.issym()
                or member.islnk()
                or member.isdev()
            ):
                raise ProvisionError(f"Pinned Git archive contains an unsafe path or link: {name!r}")
        archive.extractall(destination)


def provision(repository: Path, destination: Path) -> dict[str, object]:
    """Provision into *destination*; the CLI always supplies the fixed island path."""
    source = verify_local_git_source(repository)
    destination = destination.absolute()
    if destination.exists():
        return validate_attestation(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)
    is_junction = getattr(os.path, "isjunction", lambda _value: False)
    if destination.parent.is_symlink() or is_junction(destination.parent):
        raise ProvisionError("The fixed local runtime island parent is redirected")
    stage = destination.parent / f".{destination.name}.stage-{uuid.uuid4().hex}"
    if stage.exists():
        raise ProvisionError(f"Unexpected task staging path already exists: {stage}")
    stage.mkdir(parents=False)
    archive_path = stage / "pinned-source.tar"
    payload = stage / "payload"
    try:
        _git(
            repository.resolve(strict=True),
            "archive",
            "--format=tar",
            f"--output={archive_path}",
            PINNED_COMMIT,
        )
        _safe_extract(archive_path, payload)
        verify_runtime_tree(payload)
        records = verify_runtime_tuple(payload)
        document = _attestation_document(records)
        (payload / ATTESTATION_FILE_NAME).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        validate_attestation(payload)
        try:
            payload.replace(destination)
        except FileExistsError:
            # Another exact provisioner won the race. Never merge or overwrite islands.
            return validate_attestation(destination)
        return validate_attestation(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("check-source", "provision", "validate-island"),
        help="Read-only source check, fixed-path provisioning, or read-only island validation.",
    )
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Owner-supplied local Git repository containing the pinned object; no fetch is attempted.",
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        if arguments.action == "check-source":
            result = verify_local_git_source(arguments.repository)
        elif arguments.action == "provision":
            result = provision(arguments.repository, fixed_island_root())
        else:
            result = validate_attestation(fixed_island_root())
    except (OSError, subprocess.SubprocessError, ProvisionError) as error:
        print(f"FAIL: {error}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
