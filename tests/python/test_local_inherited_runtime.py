from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


def load_tool(module_name: str, relative: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


provisioner = load_tool("mybot_local_inherited_runtime_provisioner", "tools/provision_local_inherited_runtime.py")
proof_profiles = load_tool("mybot_local_inherited_proof_profile", "tools/prepare_local_inherited_proof_profile.py")


class LocalInheritedRuntimeProvisionerTests(unittest.TestCase):
    def test_fixed_island_and_exact_pinned_source_tuple(self) -> None:
        root = provisioner.fixed_island_root({"LOCALAPPDATA": r"C:\Owner\AppData\Local"})
        self.assertEqual(
            root,
            Path(
                r"C:\Owner\AppData\Local\My Bot 2.0\LocalInheritedRuntime\pinned-"
                + provisioner.PINNED_COMMIT
            ).resolve(strict=False),
        )
        source = provisioner.verify_local_git_source(ROOT)
        self.assertEqual("8ad6e5a552347acc2fcb8048d30262e2735a0c33", source["commit"])
        self.assertEqual("3e621065821be85d5932bd7e1f69ef7f22bc5b3d", source["tree"])
        self.assertEqual(2_506, source["tree_file_count"])
        self.assertEqual("0a807845216b84fe2f703f9c5a4f6a2f9a7c5547bb27875bfd886e7df0f77757", source["tree_manifest_sha256"])
        self.assertEqual(set(provisioner.RUNTIME_TUPLE), {record["path"] for record in source["runtime_tuple"]})

    def test_attestation_is_deterministic_and_preserves_marker_semantics(self) -> None:
        records = [
            {"path": path, "size": size, "sha256": digest}
            for path, (size, digest) in provisioner.RUNTIME_TUPLE.items()
        ]
        document = provisioner._attestation_document(records)
        encoded = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
        self.assertEqual(1_404, len(encoded))
        self.assertEqual("5bb1f1c99260a431b19611d2f647b0e9dec243a6255e5c33d0f868016b9b72af", hashlib.sha256(encoded).hexdigest())
        self.assertIs(document["anti_copycat_bypass"], False)
        self.assertEqual("exact-zero-byte-upstream-marker", document["marker_semantics"])
        self.assertEqual(0, provisioner.RUNTIME_TUPLE["MyBot.run.txt"][0])

    def test_complete_tree_digest_rejects_tamper_extra_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Dir").mkdir()
            (root / "a.bin").write_bytes(b"alpha")
            (root / "Dir" / "b.bin").write_bytes(b"beta")
            (root / provisioner.ATTESTATION_FILE_NAME).write_text("local receipt\n", encoding="utf-8")
            baseline = provisioner.runtime_tree_manifest(root)
            self.assertEqual(2, baseline[0])

            (root / "a.bin").write_bytes(b"changed")
            tampered = provisioner.runtime_tree_manifest(root)
            self.assertEqual(baseline[0], tampered[0])
            self.assertNotEqual(baseline[1], tampered[1])

            (root / "a.bin").write_bytes(b"alpha")
            (root / "extra.bin").write_bytes(b"extra")
            extra = provisioner.runtime_tree_manifest(root)
            self.assertEqual(baseline[0] + 1, extra[0])
            self.assertNotEqual(baseline[1], extra[1])

            (root / "extra.bin").unlink()
            (root / "Dir" / "b.bin").unlink()
            missing = provisioner.runtime_tree_manifest(root)
            self.assertEqual(baseline[0] - 1, missing[0])
            self.assertNotEqual(baseline[1], missing[1])

    def test_complete_tree_digest_rejects_redirected_root_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            actual = parent / "actual"
            actual.mkdir()
            (actual / "file.bin").write_bytes(b"bytes")
            redirected = parent / "redirected"
            try:
                redirected.symlink_to(actual, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"Directory symlink creation is unavailable: {error}")
            with self.assertRaisesRegex(provisioner.ProvisionError, "redirected"):
                provisioner.runtime_tree_manifest(redirected)

    def test_public_rights_gate_remains_blocked(self) -> None:
        rights = json.loads((ROOT / "config" / "redistribution-rights.json").read_text(encoding="utf-8"))
        self.assertEqual("inherited-imgloc", rights["component_id"])
        self.assertEqual("pending", rights["status"])
        self.assertIs(rights["release_allowed"], False)


class LocalInheritedProofProfileTests(unittest.TestCase):
    def make_source(
        self,
        root: Path,
        config: str | None = None,
        *,
        root_name: str = "OwnerProfiles",
        profile_name: str = "Village",
    ) -> tuple[Path, str]:
        source_root = root / root_name
        profile = source_root / profile_name
        profile.mkdir(parents=True)
        (profile / "config.ini").write_text(
            config
            or "[general]\nAutoStart=1\nRestarted=1\nChkVersion=1\n"
            "[android]\nemulator=BlueStacks5\ninstance=OwnerVillage\nshared_prefs.update=1\n"
            "[notify]\nTGEnabled=1\nTGToken=owner-secret-token\nPBRemote=1\nOrigin=OwnerVillage\n"
            "[ProfileSCID]\nOnlySCIDAccounts=1\nWhatSCIDAccount2Use=7\n",
            encoding="utf-8",
            newline="\n",
        )
        (profile / "notes.dat").write_bytes(b"owner profile bytes")
        for relative, payload in (
            ("shared_prefs/storage.xml", b"account material"),
            ("Logs/run.log", b"owner log"),
            ("Donate/capture.png", b"donate capture"),
            ("Temp/cache.bin", b"cache"),
        ):
            target = profile / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        return source_root, profile_name

    def test_safety_contract_includes_all_unlaunched_static_boundaries(self) -> None:
        requirements, digest = proof_profiles.load_safety_contract()
        self.assertEqual(
            [
                ("general", "AutoStart", "0"),
                ("general", "Restarted", "0"),
                ("general", "ChkVersion", "0"),
                ("general", "AutoStartDelay", "0"),
                ("general", "DisposeWindows", "0"),
                ("other", "ChkSellRewards", "0"),
                ("other", "ChkAutoResume", "0"),
                ("other", "ChkDisableNotifications", "1"),
                ("SuperTroopsBoost", "SuperTroopsEnable", "0"),
                ("android", "shared_prefs.update", "0"),
                ("android", "emulator", ""),
                ("android", "instance", ""),
                ("notify", "TGEnabled", "0"),
                ("notify", "TGToken", ""),
                ("notify", "PBRemote", "0"),
                ("notify", "Origin", ""),
                ("ProfileSCID", "OnlySCIDAccounts", "0"),
                ("ProfileSCID", "WhatSCIDAccount2Use", "0"),
            ],
            requirements,
        )
        self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_preparation_is_zero_copy_minimal_and_revalidated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, profile_name = self.make_source(root)
            source_before = proof_profiles.directory_digest(source_root / profile_name)
            destination_parent = root / "ProofProfiles"
            proof_root, receipt = proof_profiles.prepare(source_root, profile_name, destination_parent)
            self.assertEqual(source_before, proof_profiles.directory_digest(source_root / profile_name))
            self.assertEqual(proof_root, destination_parent / proof_root.name)
            self.assertEqual(receipt, proof_profiles.validate_proof_root(proof_root, expected_parent=destination_parent))
            config = (proof_root / "Profiles" / "Proof" / "config.ini").read_text(encoding="utf-8")
            for expected in (
                "AutoStart=0", "Restarted=0", "ChkVersion=0", "TGEnabled=0", "TGToken=", "PBRemote=0",
                "shared_prefs.update=0", "emulator=", "instance=", "OnlySCIDAccounts=0",
            ):
                self.assertIn(expected, config)
            self.assertNotIn("owner-secret-token", config)
            self.assertEqual(
                proof_profiles.PROOF_CONFIG_SHA256,
                hashlib.sha256((proof_root / "Profiles" / "Proof" / "config.ini").read_bytes()).hexdigest(),
            )
            self.assertEqual(
                proof_profiles.PROFILE_SELECTOR_SHA256,
                hashlib.sha256((proof_root / "Profiles" / "profile.ini").read_bytes()).hexdigest(),
            )
            self.assertEqual(0, receipt["source_files_copied"])
            self.assertEqual("hash-source-copy-zero-files", receipt["source_data_policy"])
            self.assertEqual("unlaunched-static-only", receipt["proof_mode"])
            self.assertEqual(
                {"Profiles/profile.ini", "Profiles/Proof/config.ini", proof_profiles.RECEIPT_NAME},
                {path.relative_to(proof_root).as_posix() for path in proof_root.rglob("*") if path.is_file()},
            )

    def test_source_drift_after_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, profile_name = self.make_source(root)
            destination_parent = root / "ProofProfiles"
            proof_root, _ = proof_profiles.prepare(source_root, profile_name, destination_parent)
            (source_root / profile_name / "notes.dat").write_bytes(b"owner changed")
            with self.assertRaisesRegex(proof_profiles.ProofProfileError, "source profile changed"):
                proof_profiles.validate_proof_root(proof_root, expected_parent=destination_parent)

    def test_identical_content_from_distinct_source_and_profile_does_not_reuse_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_a, profile_a = self.make_source(root, root_name="VillageA", profile_name="One")
            source_b, profile_b = self.make_source(root, root_name="VillageB", profile_name="Two")
            source_a_identity = proof_profiles.directory_digest(source_a / profile_a)
            source_b_identity = proof_profiles.directory_digest(source_b / profile_b)
            self.assertEqual(source_a_identity, source_b_identity)
            destination_parent = root / "ProofProfiles"

            proof_a, receipt_a = proof_profiles.prepare(source_a, profile_a, destination_parent)
            proof_b, receipt_b = proof_profiles.prepare(source_b, profile_b, destination_parent)
            proof_a_reused, receipt_a_reused = proof_profiles.prepare(source_a, profile_a, destination_parent)

            self.assertNotEqual(proof_a, proof_b)
            self.assertEqual(proof_a, proof_a_reused)
            self.assertEqual(receipt_a, receipt_a_reused)
            self.assertEqual(str(source_a.resolve()), receipt_a["source_profile_root"])
            self.assertEqual(profile_a, receipt_a["source_profile_name"])
            self.assertEqual(str(source_b.resolve()), receipt_b["source_profile_root"])
            self.assertEqual(profile_b, receipt_b["source_profile_name"])
            with self.assertRaisesRegex(proof_profiles.ProofProfileError, "different canonical source/profile identity"):
                proof_profiles.validate_proof_root(
                    proof_a,
                    expected_parent=destination_parent,
                    expected_source_root=source_b,
                    expected_profile_name=profile_b,
                    expected_source_count=source_b_identity[0],
                    expected_source_digest=source_b_identity[1],
                )

    def test_proof_tamper_extra_and_missing_are_rejected(self) -> None:
        mutations = {
            "tamper": lambda proof: (proof / "Profiles" / "Proof" / "config.ini").write_text("tampered\n", encoding="utf-8"),
            "extra": lambda proof: (proof / "Profiles" / "Proof" / "extra.dat").write_bytes(b"extra"),
            "missing": lambda proof: (proof / "Profiles" / "Proof" / "config.ini").unlink(),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source_root, profile_name = self.make_source(root)
                destination_parent = root / "ProofProfiles"
                proof_root, _ = proof_profiles.prepare(source_root, profile_name, destination_parent)
                mutate(proof_root)
                with self.assertRaisesRegex(proof_profiles.ProofProfileError, "extra, missing, or modified"):
                    proof_profiles.validate_proof_root(proof_root, expected_parent=destination_parent)

    def test_minimal_config_is_generated_without_reading_owner_settings(self) -> None:
        requirements, _ = proof_profiles.load_safety_contract()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "Proof" / "config.ini"
            proof_profiles.write_minimal_config(path, requirements)
            proof_profiles.verify_config_requirements(path, requirements)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("token", text.casefold().replace("tgtoken", ""))
            self.assertNotIn("BlueStacks", text)
            self.assertNotIn("OwnerVillage", text)

    def test_proof_digest_rejects_redirected_root_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            actual = parent / "actual"
            actual.mkdir()
            (actual / "config.ini").write_text("[general]\n", encoding="utf-8")
            redirected = parent / "redirected"
            try:
                redirected.symlink_to(actual, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"Directory symlink creation is unavailable: {error}")
            with self.assertRaisesRegex(proof_profiles.ProofProfileError, "redirected"):
                proof_profiles.directory_digest(redirected)


class LocalInheritedRuntimeStaticBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = (ROOT / "COCBot" / "functions" / "Run" / "LocalInheritedRuntime.au3").read_text(encoding="utf-8")
        cls.main = (ROOT / "MyBot.run.au3").read_text(encoding="utf-8")

    def test_automation_commands_are_explicitly_unavailable_and_unwired(self) -> None:
        self.assertIn("Func LocalInheritedRuntimeAutomationAvailable()\n\tReturn False", self.adapter)
        for command in ("Start", "Pause", "Resume", "Stop", "Close"):
            body = self.adapter.split(f"Func LocalInheritedRuntime{command}(", 1)[1].split("EndFunc", 1)[0]
            self.assertIn("$LOCAL_INHERITED_RUNTIME_AUTOMATION_ERROR", body)
            self.assertIn("Return False", body)
        self.assertNotIn("WM_MYBOT", self.adapter)
        self.assertNotIn("SendMessageW", self.adapter)
        self.assertNotIn("_WinAPI_PostMessage", self.adapter)
        self.assertNotIn("ProcessClose", self.adapter)
        self.assertNotIn("$LOCAL_INHERITED_RUNTIME_EXE", self.adapter)
        self.assertIn("Func LocalInheritedRuntimeExecutableLaunchAvailable()\n\tReturn False", self.adapter)
        launch = self.adapter.split("Func LocalInheritedRuntimeLaunchPassiveReference(", 1)[1].split("EndFunc", 1)[0]
        self.assertIn("$LOCAL_INHERITED_RUNTIME_LAUNCH_ERROR", launch)
        self.assertIn("Return False", launch)
        occurrences = 0
        for path in ROOT.rglob("*.au3"):
            occurrences += path.read_text(encoding="utf-8", errors="ignore").count("LocalInheritedRuntimeLaunchPassiveReference(")
        self.assertEqual(1, occurrences)

    def test_static_reference_requires_zero_copy_receipt_and_never_launches(self) -> None:
        for token in (
            "LOCAL_INHERITED_RUNTIME_PROOF_PARENT",
            "proof-profile.local.json",
            "unlaunched-static-only",
            "hash-source-copy-zero-files",
            "source_files_copied",
            "source_profile_sha256",
            "source_verified_unchanged",
            "LocalInheritedRuntimeValidateUnlaunchedReference",
            "inherited code was not executed",
        ):
            self.assertIn(token, self.adapter)
        self.assertNotRegex(self.adapter, r"(?m)\bRun\s*\(")
        self.assertIn('#include "COCBot\\functions\\Run\\LocalInheritedRuntime.au3"', self.main)

    def test_static_reference_fails_closed_when_durable_receipt_write_fails(self) -> None:
        writer = self.adapter.split("Func _LocalInheritedRuntimeWriteStaticReceipt(", 1)[1].split("EndFunc", 1)[0]
        validator = self.adapter.split("Func LocalInheritedRuntimeValidateUnlaunchedReference(", 1)[1].split("EndFunc", 1)[0]
        self.assertIn("Local $bFlushed = FileFlush($hFile)", writer)
        self.assertIn("Not $bWritten Or Not $bFlushed Or Not FileMove", writer)
        self.assertIn('If Not _LocalInheritedRuntimeWriteStaticReceipt("validated-unlaunched"', validator)
        failure = validator.split('If Not _LocalInheritedRuntimeWriteStaticReceipt("validated-unlaunched"', 1)[1]
        self.assertIn('$g_sLocalInheritedRuntimeState = "static-reference-receipt-failed"', failure)
        self.assertIn("Return False", failure)

    def test_warning_html_and_complete_tree_are_fail_closed(self) -> None:
        self.assertIn("LOCAL_INHERITED_RUNTIME_TREE_FILE_COUNT = 2506", self.adapter)
        self.assertIn("0a807845216b84fe2f703f9c5a4f6a2f9a7c5547bb27875bfd886e7df0f77757", self.adapter)
        self.assertIn("unauthorized-use HTML", self.adapter)
        self.assertIn("*.html", self.adapter)

    def test_local_reference_tools_are_developer_only_and_excluded_from_runtime_package(self) -> None:
        python_release = (ROOT / "tools" / "build_release.py").read_text(encoding="utf-8")
        powershell_release = (ROOT / "tools" / "Build-Release.ps1").read_text(encoding="utf-8")
        for forward, backward in (
            ("tools/prepare_local_inherited_proof_profile.py", r"tools\prepare_local_inherited_proof_profile.py"),
            ("tools/provision_local_inherited_runtime.py", r"tools\provision_local_inherited_runtime.py"),
            ("config/local-inherited-runtime-safety.json", r"config\local-inherited-runtime-safety.json"),
        ):
            self.assertNotIn(f'"{forward}"', python_release)
            self.assertNotIn(f'"{backward}"', powershell_release)
        self.assertNotIn(provisioner.PINNED_COMMIT, python_release)
        self.assertNotIn(provisioner.PINNED_COMMIT, powershell_release)
        documentation = (ROOT / "docs" / "development" / "LOCAL_INHERITED_RUNTIME.md").read_text(encoding="utf-8")
        self.assertIn("intentionally excluded from LocalRuntime packages and installed products", documentation)
        self.assertIn("execution-safety decision is independent of redistribution permission", documentation)
        self.assertIn("Public distribution is a separate gate", documentation)


if __name__ == "__main__":
    unittest.main()
