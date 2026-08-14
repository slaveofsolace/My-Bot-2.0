import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "build_release.py"
SPEC = importlib.util.spec_from_file_location("mybot_build_release", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release
SPEC.loader.exec_module(release)


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return result.stdout.strip()


def write(repo: Path, relative: str, data: bytes | str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8", newline="\n")
    else:
        path.write_bytes(data)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ReleaseFixture:
    def __init__(self, root: Path) -> None:
        self.repo = root / "repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "--initial-branch=main")
        run_git(self.repo, "config", "user.name", "Release Test")
        run_git(self.repo, "config", "user.email", "release@example.invalid")

        self.targets = release.DEFAULT_CONTRACT.compile_targets
        runtime_files = (
            "MyBot.run.version.au3",
            "config/binary-provenance.json",
            "tools/install_local_runtime.py",
            *(target.source for target in self.targets),
        )
        self.contract = replace(
            release.DEFAULT_CONTRACT,
            runtime_directories=("COCBot",),
            runtime_files=runtime_files,
            runtime_config_directories=(),
        )

        write(self.repo, "COCBot/engine.au3", "; engine\n")
        write(self.repo, "Languages/English.ini", "canonical english\n")
        write(self.repo, "MyBot.run.version.au3", 'Global Const $g_sProductVersion = "v2.0.0"\n')
        write(self.repo, "MyBot.run.txt", b"")
        write(self.repo, "tools/install_local_runtime.py", "# installer\n")
        write(self.repo, "tools/repo_audit.py", "raise SystemExit(0)\n")
        for target in self.targets:
            write(self.repo, target.source, f"; {target.source}\n")
            write(self.repo, target.output, f"OLD:{target.output}".encode())
        write(self.repo, "config/binary-provenance.json", self._provenance({}, "0" * 40))
        run_git(self.repo, "add", "--all")
        run_git(self.repo, "commit", "-m", "source")
        self.source_commit = run_git(self.repo, "rev-parse", "HEAD")

        self.candidate = root / "candidate"
        self.candidate.mkdir()
        self.candidate_bytes = {
            target.output: f"REVIEWED:{target.output}".encode() for target in self.targets
        }
        records = []
        for target in self.targets:
            data = self.candidate_bytes[target.output]
            write(self.candidate, target.output, data)
            records.append(
                {
                    "path": target.output,
                    "source": target.source,
                    "pragma_output": target.pragma_output,
                    "subsystem": target.subsystem,
                    "flags": list(target.flags),
                    "bytes": len(data),
                    "sha256": digest(data),
                }
            )
        self.candidate_manifest = {
            "schema_version": 1,
            "version": "2.0.0",
            "architecture": "x86",
            "compiler_version": self.contract.compiler_version,
            "compiler_sha256": self.contract.compiler_sha256,
            "compiler_signer": self.contract.compiler_signer,
            "source_commit": self.source_commit,
            "source_tree_clean": True,
            "signing_claim": "none",
            "binaries": records,
        }
        write(
            self.candidate,
            "candidate-hashes.json",
            release.deterministic_json(self.candidate_manifest),
        )

        for target in self.targets:
            write(self.repo, target.output, self.candidate_bytes[target.output])
        write(
            self.repo,
            "config/binary-provenance.json",
            self._provenance(self.candidate_bytes, self.source_commit),
        )
        run_git(self.repo, "add", "--all")
        run_git(self.repo, "commit", "-m", "promote reviewed binaries")
        self.package_commit = run_git(self.repo, "rev-parse", "HEAD")

    def _provenance(self, binaries: dict[str, bytes], source_commit: str) -> str:
        artifacts = []
        for target in self.targets:
            data = binaries.get(target.output, f"OLD:{target.output}".encode())
            artifacts.append(
                {
                    "path": target.output,
                    "sha256": digest(data),
                    "bytes": len(data),
                    "provenance": {
                        "kind": "local-build",
                        "source": target.source,
                        "pragma_output": target.pragma_output,
                        "toolchain": "AutoIt Aut2Exe",
                        "tool_version": self.contract.compiler_version,
                        "tool_signer": self.contract.provenance_tool_signer,
                        "source_commit": source_commit,
                        "compiler_sha256": self.contract.compiler_sha256,
                        "compile_flags": list(target.flags),
                        "built_at": "2026-08-13",
                    },
                }
            )
        return json.dumps(
            {"schema_version": 1, "reviewed_at": "2026-08-13", "artifacts": artifacts},
            indent=2,
        ) + "\n"


class PythonReleaseContractTests(unittest.TestCase):
    def test_default_compile_matrix_is_exact_and_mini_is_reviewed_gui_target(self) -> None:
        matrix = [
            (target.source, target.output, target.subsystem, target.pragma_output, list(target.flags))
            for target in release.DEFAULT_CONTRACT.compile_targets
        ]
        self.assertEqual(
            matrix,
            [
                ("My Bot 2.0.au3", "My Bot 2.0.exe", "/gui", "My Bot 2.0.exe", ["/x86", "/gui", "/nopack", "/comp", "2"]),
                ("MyBot.run.EngineProbe.au3", "MyBot.run.EngineProbe.exe", "/gui", "MyBot.run.EngineProbe.exe", ["/x86", "/gui", "/nopack", "/comp", "2"]),
                ("MyBot.run.au3", "MyBot.run.exe", "/gui", "MyBot.run.exe", ["/x86", "/gui", "/nopack", "/comp", "2"]),
                ("MyBot.run.MiniGui.au3", "MyBot.run.MiniGui.exe", "/gui", "MyBot.run.MiniGui.dev.exe", ["/x86", "/gui", "/nopack", "/comp", "2"]),
                ("MyBot.run.Watchdog.au3", "MyBot.run.Watchdog.exe", "/gui", "MyBot.run.Watchdog.exe", ["/x86", "/gui", "/nopack", "/comp", "2"]),
                ("MyBot.run.Wmi.au3", "MyBot.run.Wmi.exe", "/console", "MyBot.run.Wmi.exe", ["/x86", "/console", "/nopack", "/comp", "2"]),
            ],
        )
        mini = next(
            target
            for target in release.DEFAULT_CONTRACT.compile_targets
            if target.output == "MyBot.run.MiniGui.exe"
        )
        self.assertEqual(mini.flags, ("/x86", "/gui", "/nopack", "/comp", "2"))
        self.assertEqual(mini.pragma_output, "MyBot.run.MiniGui.dev.exe")

    def test_default_source_pragmas_match_release_contract(self) -> None:
        for target in release.DEFAULT_CONTRACT.compile_targets:
            with self.subTest(source=target.source):
                declared = release._declared_pragma_output(
                    ROOT,
                    ROOT / target.source,
                    target,
                )
                self.assertEqual(declared, ROOT / target.pragma_output)

    def test_path_filter_rejects_local_state_and_preserves_canonical_english_exception(self) -> None:
        for path in (
            "Profiles/MyVillage/profile.ini",
            "logs/bot.log",
            "artifacts/release.zip",
            "config/run-plan.local.json",
            "config/run-events.session.jsonl",
            "tools/__pycache__/release.pyc",
            "lib/debug.html",
            "tools/_temp.exe",
            "CLAUDE_HANDOFF_PROMPT.md",
            "Languages/English.ini",
        ):
            self.assertTrue(release.is_excluded_release_path(path), path)
        for unsafe in (
            "../escape",
            "/absolute",
            "C:/absolute",
            "safe/../escape",
            "./relative",
            "a//b",
            "a/./b",
            "a/",
            "a/b:stream",
            "nul\0path",
        ):
            with self.assertRaises(release.ReleaseError, msg=unsafe):
                release.normalize_relative_path(unsafe)

    def test_cli_refuses_public_distribution_without_touching_a_repository(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = release.main(
                [
                    "--action",
                    "package-reviewed",
                    "--version",
                    "2.0.0",
                    "--mode",
                    "PublicDistribution",
                    "--reviewed-binary-directory",
                    "missing",
                ]
            )
        self.assertEqual(code, 1)
        self.assertIn("PublicDistribution remains blocked", stderr.getvalue())

    @unittest.skipUnless(
        os.name == "nt" and Path(r"C:\Program Files (x86)\AutoIt3\Aut2Exe\Aut2Exe.exe").is_file(),
        "the pinned Windows AutoIt compiler is not installed",
    )
    def test_installed_compiler_matches_hash_version_trust_subject_and_thumbprint(self) -> None:
        compiler = release.find_and_validate_compiler(
            Path(r"C:\Program Files (x86)\AutoIt3"), release.DEFAULT_CONTRACT
        )
        self.assertEqual(release.sha256_file(compiler), release.DEFAULT_CONTRACT.compiler_sha256)
        wrong_identity = replace(release.DEFAULT_CONTRACT, compiler_thumbprint="0" * 40)
        with self.assertRaisesRegex(release.ReleaseError, "subject or thumbprint"):
            release.find_and_validate_compiler(Path(r"C:\Program Files (x86)\AutoIt3"), wrong_identity)

    def test_candidate_manifest_fails_closed_on_extra_file_record_flag_or_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = ReleaseFixture(Path(temp))
            release.read_candidate_manifest(fixture.candidate, "2.0.0", fixture.contract)

            write(fixture.candidate, "extra.exe", b"unexpected")
            with self.assertRaisesRegex(release.ReleaseError, "exact compile matrix"):
                release.read_candidate_manifest(fixture.candidate, "2.0.0", fixture.contract)
            (fixture.candidate / "extra.exe").unlink()

            manifest_path = fixture.candidate / "candidate-hashes.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            mini_index = next(
                index
                for index, target in enumerate(fixture.contract.compile_targets)
                if target.output == "MyBot.run.MiniGui.exe"
            )
            manifest["binaries"][mini_index]["pragma_output"] = "MyBot.run.MiniGui.exe"
            manifest_path.write_bytes(release.deterministic_json(manifest))
            with self.assertRaisesRegex(release.ReleaseError, "identity or flags mismatch"):
                release.read_candidate_manifest(fixture.candidate, "2.0.0", fixture.contract)

            manifest = json.loads(release.deterministic_json(fixture.candidate_manifest))
            manifest["binaries"][mini_index]["flags"][1] = "/console"
            manifest_path.write_bytes(release.deterministic_json(manifest))
            with self.assertRaisesRegex(release.ReleaseError, "flags mismatch"):
                release.read_candidate_manifest(fixture.candidate, "2.0.0", fixture.contract)

            manifest_path.write_bytes(release.deterministic_json(fixture.candidate_manifest))
            mini_output = fixture.contract.compile_targets[mini_index].output
            (fixture.candidate / mini_output).write_bytes(b"tampered")
            with self.assertRaisesRegex(release.ReleaseError, "do not match"):
                release.read_candidate_manifest(fixture.candidate, "2.0.0", fixture.contract)

    def test_candidate_root_reparse_point_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = ReleaseFixture(Path(temp))
            link = Path(temp) / "candidate-link"
            try:
                link.symlink_to(fixture.candidate, target_is_directory=True)
            except OSError:
                self.skipTest("directory links are unavailable to this Windows user")
            with self.assertRaisesRegex(release.ReleaseError, "reparse point"):
                release.read_candidate_manifest(link, "2.0.0", fixture.contract)

    def test_package_entry_point_rechecks_unresolved_candidate_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = ReleaseFixture(Path(temp))
            original = release._is_reparse_point

            def classify(path: Path) -> bool:
                if Path(path).absolute() == fixture.candidate.absolute():
                    return True
                return original(Path(path))

            with mock.patch.object(release, "_is_reparse_point", side_effect=classify):
                with self.assertRaisesRegex(release.ReleaseError, "reparse point"):
                    release.package_reviewed(
                        fixture.repo,
                        fixture.candidate,
                        "2.0.0",
                        Path(temp) / "reparse",
                        fixture.contract,
                    )

    def test_compile_one_restores_existing_pragma_binary_on_success_and_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stage = root / "candidate"
            stage.mkdir()
            target = release.CompileTarget("source.au3", "program.exe", "/gui", "program.dev.exe")
            write(root, target.source, "#pragma compile(Out, program.dev.exe)\n; source\n")
            original = b"ORIGINAL-BINARY"
            write(root, target.pragma_output, original)

            def successful_run(args, **_kwargs):
                self.assertEqual(
                    [os.fspath(value) for value in args[-5:]],
                    ["/x86", "/gui", "/nopack", "/comp", "2"],
                )
                write(root, target.pragma_output, b"NEW-CANDIDATE")
                return subprocess.CompletedProcess(args, 0, "", "")

            with mock.patch.object(release, "_run", side_effect=successful_run):
                candidate = release._compile_one(Path("compiler.exe"), root, stage, target)
            self.assertEqual(candidate.read_bytes(), b"NEW-CANDIDATE")
            self.assertEqual((root / target.pragma_output).read_bytes(), original)
            self.assertFalse((root / target.output).exists())

            def failed_run(args, **_kwargs):
                write(root, target.pragma_output, b"PARTIAL-CANDIDATE")
                return subprocess.CompletedProcess(args, 7, "", "compile failed")

            with mock.patch.object(release, "_run", side_effect=failed_run):
                with self.assertRaisesRegex(release.ReleaseError, "exit code 7"):
                    release._compile_one(Path("compiler.exe"), root, stage, target)
            self.assertEqual((root / target.pragma_output).read_bytes(), original)
            self.assertFalse((root / target.output).exists())

            write(root, target.source, "#pragma compile(Out, wrong.exe)\n; source\n")
            with mock.patch.object(release, "_run") as compiler_run:
                with self.assertRaisesRegex(release.ReleaseError, "output pragma does not match"):
                    release._compile_one(Path("compiler.exe"), root, stage, target)
            compiler_run.assert_not_called()
            self.assertEqual((root / target.pragma_output).read_bytes(), original)

    def test_zip_publish_cannot_overwrite_a_concurrent_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = root / "MyBot-2.0.0-win-x86"
            payload.mkdir()
            write(payload, "file.txt", b"payload")
            destination = root / "release.zip"

            real_link = os.link

            def competing_link(source, target):
                Path(target).write_bytes(b"COMPETING-RELEASE")
                return real_link(source, target)

            with mock.patch.object(release.os, "link", side_effect=competing_link):
                with self.assertRaisesRegex(release.ReleaseError, "already exists"):
                    release._write_deterministic_zip(payload, destination)
            self.assertEqual(destination.read_bytes(), b"COMPETING-RELEASE")

    def test_package_is_deterministic_rooted_clean_and_excludes_unselected_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = ReleaseFixture(Path(temp))
            output_a = Path(temp) / "out-a"
            output_b = Path(temp) / "out-b"
            zip_a = release.package_reviewed(
                fixture.repo, fixture.candidate, "2.0.0", output_a, fixture.contract
            )
            zip_b = release.package_reviewed(
                fixture.repo, fixture.candidate, "2.0.0", output_b, fixture.contract
            )
            self.assertEqual(zip_a.read_bytes(), zip_b.read_bytes())

            with zipfile.ZipFile(zip_a) as archive:
                names = archive.namelist()
                self.assertEqual(names, sorted(names, key=lambda item: (item.casefold(), item)))
                self.assertTrue(all(name.startswith("MyBot-2.0.0-win-x86/") for name in names))
                self.assertTrue(all(info.date_time == release.ZIP_TIMESTAMP for info in archive.infolist()))
                self.assertNotIn("MyBot-2.0.0-win-x86/CLAUDE_HANDOFF_PROMPT.md", names)
                self.assertNotIn("MyBot-2.0.0-win-x86/Profiles/profile.ini", names)
                self.assertEqual(
                    archive.read("MyBot-2.0.0-win-x86/Languages/English.ini"),
                    b"canonical english\n",
                )
                self.assertEqual(archive.read("MyBot-2.0.0-win-x86/MyBot.run.txt"), b"")
                manifest = json.loads(
                    archive.read("MyBot-2.0.0-win-x86/release-manifest.json")
                )
            self.assertEqual(manifest["source_commit"], fixture.package_commit)
            self.assertIs(manifest["source_tree_clean"], True)
            self.assertIs(manifest["binary_provenance_verified"], True)
            self.assertNotIn("pinned_mini_rebuilt", manifest)
            self.assertEqual(
                manifest["compiled_targets"],
                [
                    {
                        "path": target.output,
                        "source": target.source,
                        "pragma_output": target.pragma_output,
                        "subsystem": target.subsystem,
                        "flags": list(target.flags),
                    }
                    for target in fixture.contract.compile_targets
                ],
            )
            self.assertIs(manifest["code_signing_performed"], False)
            self.assertEqual(manifest["signing_claim"], "none")
            self.assertIs(manifest["imgloc_redistribution_permission_acknowledged"], False)
            self.assertNotIn("release-manifest.json", {record["path"] for record in manifest["files"]})

    def test_package_rejects_dirty_source_unreviewed_change_and_candidate_or_provenance_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = ReleaseFixture(Path(temp))
            write(fixture.repo, "untracked.txt", "dirty\n")
            with self.assertRaisesRegex(release.ReleaseError, "dirty"):
                release.package_reviewed(
                    fixture.repo, fixture.candidate, "2.0.0", Path(temp) / "dirty", fixture.contract
                )
            (fixture.repo / "untracked.txt").unlink()

            write(fixture.repo, "COCBot/engine.au3", "; post-build change\n")
            run_git(fixture.repo, "add", "COCBot/engine.au3")
            run_git(fixture.repo, "commit", "-m", "unreviewed source change")
            with self.assertRaisesRegex(release.ReleaseError, "changed after candidate compilation"):
                release.package_reviewed(
                    fixture.repo, fixture.candidate, "2.0.0", Path(temp) / "changed", fixture.contract
                )

        with tempfile.TemporaryDirectory() as temp:
            fixture = ReleaseFixture(Path(temp))
            mini = next(
                target
                for target in fixture.contract.compile_targets
                if target.output == "MyBot.run.MiniGui.exe"
            )
            write(fixture.repo, mini.output, b"different promoted bytes")
            run_git(fixture.repo, "add", mini.output)
            run_git(fixture.repo, "commit", "-m", "drift promoted Mini binary")
            with self.assertRaisesRegex(release.ReleaseError, "Promoted Git binary differs"):
                release.package_reviewed(
                    fixture.repo, fixture.candidate, "2.0.0", Path(temp) / "drift", fixture.contract
                )

        with tempfile.TemporaryDirectory() as temp:
            fixture = ReleaseFixture(Path(temp))
            provenance_path = fixture.repo / "config" / "binary-provenance.json"
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            provenance["artifacts"].append(
                {
                    "path": "extra-native.dll",
                    "sha256": digest(b"EXTRA"),
                    "bytes": len(b"EXTRA"),
                    "provenance": {
                        "kind": "inherited-repository",
                        "source_id": "test-upstream",
                        "introduced_commit": fixture.source_commit,
                    },
                }
            )
            provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
            run_git(fixture.repo, "add", "config/binary-provenance.json")
            run_git(fixture.repo, "commit", "-m", "add unshipped provenance")
            with self.assertRaisesRegex(release.ReleaseError, "file sets differ"):
                release.package_reviewed(
                    fixture.repo,
                    fixture.candidate,
                    "2.0.0",
                    Path(temp) / "extra-provenance",
                    fixture.contract,
                )


if __name__ == "__main__":
    unittest.main()
