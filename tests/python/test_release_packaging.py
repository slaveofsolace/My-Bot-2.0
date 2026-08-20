from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "Build-Release.ps1"
AUTOIT_RUNNER = ROOT / "tools" / "Test-AutoIt.ps1"


class ReleasePackagingStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_exact_local_compile_matrix_includes_reviewed_mini_gui(self) -> None:
        expected = {
            "My Bot 2.0.au3": ("My Bot 2.0.exe", "My Bot 2.0.exe"),
            "MyBot.run.EngineProbe.au3": ("MyBot.run.EngineProbe.exe", "MyBot.run.EngineProbe.exe"),
            "MyBot.run.au3": ("MyBot.run.exe", "MyBot.run.exe"),
            "MyBot.run.MiniGui.au3": ("MyBot.run.MiniGui.exe", "MyBot.run.MiniGui.dev.exe"),
            "MyBot.run.Watchdog.au3": ("MyBot.run.Watchdog.exe", "MyBot.run.Watchdog.exe"),
            "MyBot.run.Wmi.au3": ("MyBot.run.Wmi.exe", "MyBot.run.Wmi.exe"),
        }
        matrix = {
            source: (output, pragma_output)
            for source, output, pragma_output in re.findall(
                r'\{ Source = "([^"]+)"; Output = "([^"]+)"; Subsystem = "/(?:gui|console)"; PragmaOutput = "([^"]+)" \}',
                self.source,
            )
        }
        self.assertEqual(expected, matrix)
        self.assertIn(
            'Source = "MyBot.run.MiniGui.au3"; Output = "MyBot.run.MiniGui.exe"; Subsystem = "/gui"; PragmaOutput = "MyBot.run.MiniGui.dev.exe"',
            self.source,
        )

    def test_compile_flags_are_explicit_and_x86(self) -> None:
        compile_body = self.source.split("function Invoke-ReleaseCompile", 1)[1].split(
            "function Get-ProvenanceRecord", 1
        )[0]
        for flag in ('"/x86"', '"/nopack"', '"/comp", "2"'):
            self.assertIn(flag, compile_body)
        self.assertIn('Subsystem = "/gui"', self.source)
        self.assertIn('Subsystem = "/console"', self.source)
        self.assertIn('Source = "MyBot.run.Watchdog.au3"; Output = "MyBot.run.Watchdog.exe"; Subsystem = "/gui"', self.source)
        self.assertIn('Source = "MyBot.run.Wmi.au3"; Output = "MyBot.run.Wmi.exe"; Subsystem = "/console"', self.source)
        self.assertNotIn('"/x64"', compile_body)
        self.assertGreaterEqual(self.source.count("VersionInfo.FileVersionRaw.ToString()"), 2)
        self.assertNotIn("VersionInfo.FileVersion\n", self.source)
        self.assertIn("Get-AuthenticodeSignature", self.source)
        self.assertIn("$signature.SignerCertificate.Subject -ceq $expectedCompilerSigner", self.source)
        self.assertIn("$signature.SignerCertificate.Thumbprint -ceq $expectedCompilerThumbprint", self.source)
        self.assertIn("$compilerHashValid", self.source)

    def test_pragma_output_is_isolated_and_original_binary_is_restored(self) -> None:
        compile_body = self.source.split("function Invoke-ReleaseCompile", 1)[1].split(
            "function Get-ProvenanceRecord", 1
        )[0]
        self.assertIn("$pragmaOutput = Join-Path $repositoryRoot $target.PragmaOutput", compile_body)
        self.assertIn("Compile source must declare exactly one output pragma", compile_body)
        self.assertIn("Compile source output pragma does not match the release contract", compile_body)
        self.assertIn("$hadOriginalOutput", compile_body)
        self.assertIn("Move-Item -LiteralPath $pragmaOutput -Destination $output", compile_body)
        self.assertIn("Aut2Exe returned success but produced no output", compile_body)
        self.assertIn("[datetime]::UtcNow.AddSeconds(30)", compile_body)
        self.assertIn("Start-Sleep -Milliseconds 100", compile_body)
        self.assertIn("$stableSamples -ge 2", compile_body)
        self.assertIn("Aut2Exe output did not become stable", compile_body)
        self.assertIn("Move-Item -LiteralPath $originalOutput -Destination $pragmaOutput", compile_body)
        self.assertIn("finally", compile_body)
        self.assertNotRegex(compile_body, r"(?m)^\s*;\s*[A-Za-z]")

    def test_mini_gui_uses_reviewed_candidate_and_provenance_flow(self) -> None:
        self.assertNotIn("$pinnedMini", self.source)
        self.assertNotIn("pinned_mini_rebuilt", self.source)
        self.assertIn("foreach ($target in $compileTargets)", self.source)
        self.assertIn("Assert-CompiledSourceIdentity -Provenance $provenance", self.source)
        self.assertIn("Provenance pragma output mismatch", self.source)

    def test_local_state_and_protected_noise_are_excluded(self) -> None:
        for token in (
            "Profiles",
            "logs",
            "artifacts",
            "__pycache__",
            ".pytest_cache",
            "Languages/English.ini",
            "_HANDOFF_PROMPT\\.md",
            "lib/[^/]+\\.html",
            "tools/_[^/]*",
            "run-plan",
            "control-status",
            "control-command",
            "run-events",
        ):
            self.assertIn(token, self.source)
        self.assertNotIn('"Profiles",\n', self.source.split("$runtimeDirectories", 1)[1].split(")", 1)[0])
        self.assertNotIn('"data",\n', self.source.split("$runtimeDirectories", 1)[1].split(")", 1)[0])
        self.assertIn('"docs\\INSTALL.md"', self.source)
        self.assertIn('"packaging\\README.md"', self.source)
        self.assertIn("Release input is not tracked by Git", self.source)

    def test_canonical_english_language_file_comes_from_reviewed_commit(self) -> None:
        self.assertIn("function Export-TrackedFileAtCommit", self.source)
        self.assertIn("StandardOutput.BaseStream.CopyTo", self.source)
        self.assertIn(
            'Export-TrackedFileAtCommit -Commit $sourceCommit -RelativePath "Languages\\English.ini"',
            self.source,
        )
        export_position = self.source.index("Export-TrackedFileAtCommit -Commit $sourceCommit")
        package_position = self.source.index("New-DeterministicZip -PayloadRoot")
        self.assertLess(export_position, package_position)
        self.assertIn("function Test-IsForbiddenPayloadPath", self.source)
        self.assertIn('if ($normalized -ieq "Languages/English.ini") { return $false }', self.source)
        self.assertIn("Test-IsForbiddenPayloadPath -RelativePath", self.source)
        self.assertNotIn("Replace('\\\\', '/')", self.source)

    def test_zero_byte_marker_is_required_in_source_and_payload(self) -> None:
        self.assertIn('(Get-Item -LiteralPath $sourceMarker).Length -ne 0', self.source)
        self.assertIn("[System.IO.File]::WriteAllBytes", self.source)
        self.assertIn('Join-Path $payloadRoot "MyBot.run.txt"', self.source)

    def test_every_packaged_native_binary_is_provenance_checked_before_zip(self) -> None:
        verify_position = self.source.index("Assert-BinaryMatchesProvenance -Provenance")
        verified_position = self.source.index("$provenanceVerified = $true", verify_position)
        zip_position = self.source.index("New-DeterministicZip -PayloadRoot", verified_position)
        self.assertLess(verify_position, verified_position)
        self.assertLess(verified_position, zip_position)
        self.assertIn('@(".exe", ".dll", ".sys")', self.source)
        self.assertIn("Assert-ProvenanceDocument -Provenance $provenance", self.source)
        self.assertIn("Assert-CompiledSourceIdentity", self.source)

    def test_provenance_document_rejects_duplicates_traversal_and_bad_hashes(self) -> None:
        self.assertIn("Binary provenance contains a duplicate path", self.source)
        self.assertIn("Binary provenance contains an unsafe path", self.source)
        self.assertIn("^[0-9a-fA-F]{64}$", self.source)
        self.assertIn("Binary provenance contains an invalid byte count", self.source)
        self.assertIn("[datetime]::TryParseExact", self.source)
        self.assertIn('provenance.toolchain -ine "AutoIt Aut2Exe"', self.source)
        self.assertIn("provenance.tool_version -ine $ExpectedAutoItVersion", self.source)
        self.assertIn('Join-Path $payloadRoot "config\\binary-provenance.json"', self.source)

    def test_public_distribution_requires_exact_rights_acknowledgement(self) -> None:
        self.assertIn(
            'WRITTEN_PERMISSION_CONFIRMED_OR_LICENSED_REPLACEMENT_VALIDATED', self.source
        )
        self.assertIn('$Mode -eq "PublicDistribution"', self.source)
        self.assertIn("PublicDistribution is blocked", self.source)
        self.assertIn("PublicDistribution cannot be created from a dirty source tree", self.source)
        self.assertIn("tools\\validate_redistribution_rights.py", self.source)
        self.assertIn("--require-public", self.source)
        self.assertIn("PublicDistribution rights record failed validation", self.source)

    def test_public_distribution_requires_full_completion_proof(self) -> None:
        for validator in (
            "validate_current_client_fixtures.py",
            "evaluate_support_readiness.py",
            "validate_actuator_registry.py",
            "validate_neutral_branding.py",
        ):
            self.assertIn(validator, self.source)
        self.assertIn('Arguments = @("--require-complete")', self.source)
        self.assertIn('Arguments = @("--require-all-current")', self.source)
        self.assertIn("PublicDistribution completion validator is missing", self.source)
        self.assertIn("PublicDistribution $($completionCheck.Name) gate failed", self.source)
        self.assertIn('$rightsRelativePath = "config/redistribution-rights.json"', self.source)
        self.assertIn("redistribution_rights_record = $redistributionRightsRecord", self.source)
        self.assertIn("sha256 = Get-Sha256Lower -Path $rightsPath", self.source)

    def test_zip_metadata_is_normalized_and_signing_is_not_claimed(self) -> None:
        self.assertIn("1980, 1, 1, 0, 0, 0", self.source)
        self.assertIn("$entry.LastWriteTime = $deterministicZipTimestamp", self.source)
        self.assertIn("code_signing_performed = $false", self.source)
        self.assertIn('signing_claim = "none"', self.source)
        self.assertNotRegex(self.source, r"(?i)signtool|set-authenticodesignature")

    def test_reviewed_binary_action_supports_non_reproducible_compiler_output(self) -> None:
        for action in ("BuildAndPackage", "CompileForReview", "PackageReviewed"):
            self.assertIn(action, self.source)
        self.assertIn("ReviewedBinaryDirectory is required for PackageReviewed", self.source)
        self.assertIn("candidate-hashes.json", self.source)
        self.assertIn("function Read-ReviewedCandidateManifest", self.source)
        self.assertIn("merge-base --is-ancestor", self.source)
        self.assertIn("Package source changed after candidate compilation", self.source)
        self.assertIn("Reviewed candidate bytes do not match candidate-hashes.json", self.source)
        self.assertIn("AllowDirtySource is restricted to isolated CompileForReview candidates", self.source)
        self.assertIn("compiler_sha256", self.source)
        self.assertIn("compiler_signer", self.source)
        self.assertIn("source_tree_clean = ($gitStatus.Count -eq 0)", self.source)
        self.assertIn("$manifest.source_tree_clean -is [bool]", self.source)
        self.assertIn("$manifest.source_tree_clean -eq $true", self.source)
        self.assertNotIn("[bool]$manifest.source_tree_clean", self.source)
        self.assertIn('[string]$manifest.signing_claim -ceq "none"', self.source)
        self.assertIn("Reviewed candidate compile flags mismatch", self.source)
        self.assertIn("pragma_output = $target.PragmaOutput.Replace", self.source)
        self.assertIn("compiled_targets = $compiledTargetRecords", self.source)
        self.assertIn("921e51d0d9f94c05c5ed10d2d2a80620c8ed930cc48d71e2ce0a5bab4a4f8158", self.source)
        self.assertIn("CN=AutoIt Consulting Ltd, O=AutoIt Consulting Ltd, L=Birmingham, C=GB", self.source)

    def test_release_version_must_match_source_contract(self) -> None:
        self.assertIn('Global Const \\$g_sProductVersion', self.source)
        self.assertIn("does not match MyBot.run.version.au3", self.source)

    def test_autoit_runner_waits_for_gui_process_exit_codes(self) -> None:
        runner = AUTOIT_RUNNER.read_text(encoding="utf-8-sig")
        self.assertIn("function Invoke-NativeProcess", runner)
        self.assertIn("Start-Process", runner)
        self.assertIn("-Wait", runner)
        self.assertIn("-PassThru", runner)
        self.assertIn("-RedirectStandardOutput", runner)
        self.assertIn("-RedirectStandardError", runner)
        self.assertIn("$process.ExitCode", runner)
        self.assertNotIn("$LASTEXITCODE", runner)


if __name__ == "__main__":
    unittest.main()
