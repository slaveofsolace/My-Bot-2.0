from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "MyBot.run.EngineProbe.au3"
CONFIG = ROOT / "MyBot.run.EngineProbe.exe.config"
PARENT = ROOT / "COCBot" / "functions" / "Other" / "MBRFunc.au3"


def function_body(source: str, name: str) -> str:
    start = source.index(f"Func {name}(")
    return source[start : source.index("EndFunc", start)]


class EngineProbeLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.helper = HELPER.read_text(encoding="utf-8-sig")
        cls.config = CONFIG.read_text(encoding="utf-8-sig")
        cls.parent = PARENT.read_text(encoding="utf-8-sig")

    def test_helper_publishes_versioned_success_before_process_teardown(self) -> None:
        self.assertNotIn("DllClose(", self.helper)
        call = self.helper.index("DllCall(")
        validated = self.helper.index("If $iProbeError Or Not IsArray($aProbe) Then Exit 4", call)
        published = self.helper.index(
            '_EngineProbePublish($sTokenPath, $ENGINE_PROBE_PROTOCOL & "|call-returned")',
            validated,
        )
        self.assertLess(call, validated)
        self.assertLess(validated, published)
        self.assertIn('Global Const $ENGINE_PROBE_PROTOCOL = "engine-probe/v1"', self.helper)

    def test_helper_phase_and_publish_contract_is_bounded(self) -> None:
        for phase in ("opened", "call-entered", "call-returned"):
            self.assertIn(f'$ENGINE_PROBE_PROTOCOL & "|{phase}"', self.helper)
        publish = function_body(self.helper, "_EngineProbePublish")
        offsets = [publish.index(name) for name in ("FileOpen(", "FileFlush(", "FileClose(", "FileMove(")]
        self.assertEqual(offsets, sorted(offsets))

    def test_parent_consumes_receipt_reaps_exact_pid_then_passes(self) -> None:
        probe = function_body(self.parent, "MBRFuncProbeEngine")
        read = probe.index("FileRead($sToken)")
        deleted = probe.index("FileDelete($sToken)", read)
        versioned = probe.index('$g_sMBRFuncEngineProbeProtocol & "|call-returned"', deleted)
        reaped = probe.index("MBRFuncEngineProbeEnsureHelperGone($iProbePid, 1)", versioned)
        cleaned = probe.index("MBRFuncEngineProbeCleanupArtifacts($sToken, $sPhasePath, $iProbePid)", reaped)
        gone = probe.index("If Not ProcessExists($iProbePid) Then", cleaned)
        offsets = [
            read,
            deleted,
            versioned,
            reaped,
            cleaned,
            gone,
            probe.index('$g_sMBRFuncEngineProbeState = "passed"', gone),
        ]
        self.assertEqual(offsets, sorted(offsets))

        reaper = function_body(self.parent, "MBRFuncEngineProbeEnsureHelperGone")
        self.assertIn("ProcessWaitClose($iProbePid, $iGraceSeconds)", reaper)
        self.assertIn("ProcessClose($iProbePid)", reaper)
        self.assertIn("ProcessWaitClose($iProbePid, 1)", reaper)
        self.assertIn("Return Not ProcessExists($iProbePid)", reaper)

    def test_prelaunch_receipts_are_uniquely_named_and_cleaned_before_run(self) -> None:
        probe = function_body(self.parent, "MBRFuncProbeEngine")
        nonce = probe.index("Random(100000, 999999, 1)")
        phase = probe.index('Local $sPhasePath = $sToken & ".phase"', nonce)
        cleanup = probe.index(
            "If Not MBRFuncEngineProbeCleanupArtifacts($sToken, $sPhasePath, 0) Then",
            phase,
        )
        launch = probe.index("Run('")
        self.assertEqual([nonce, phase, cleanup, launch], sorted((nonce, phase, cleanup, launch)))

    def test_invalid_and_unconsumable_receipts_verify_reap_and_cleanup(self) -> None:
        reject = function_body(self.parent, "MBRFuncEngineProbeRejectReceipt")
        reaped = reject.index("MBRFuncEngineProbeEnsureHelperGone($iProbePid)")
        cleaned = reject.index(
            "MBRFuncEngineProbeCleanupArtifacts($sToken, $sPhasePath, $iProbePid)",
            reaped,
        )
        reap_checked = reject.index("If Not $bHelperGone Then", cleaned)
        cleanup_checked = reject.index("ElseIf Not $bArtifactsCleared Then", reap_checked)
        returned = reject.index("Return False", cleanup_checked)
        self.assertEqual([reaped, cleaned, reap_checked, cleanup_checked, returned], sorted((reaped, cleaned, reap_checked, cleanup_checked, returned)))

        probe = function_body(self.parent, "MBRFuncProbeEngine")
        for reason in (
            "Managed engine probe success receipt could not be consumed",
            "Managed engine probe returned an invalid receipt",
        ):
            self.assertIn(f'Return MBRFuncEngineProbeRejectReceipt($sError, "{reason}"', probe)

    def test_stop_precedes_success_and_keeps_cancellation_text(self) -> None:
        probe = function_body(self.parent, "MBRFuncProbeEngine")
        cancel = probe.index("$g_iBotAction = $eBotStop Or $g_iBotAction = $eBotClose")
        read = probe.index("FileRead($sToken)")
        reaped = probe.index("MBRFuncEngineProbeEnsureHelperGone($iProbePid, 1)", read)
        cancel_after_reap = probe.index("$g_iBotAction = $eBotStop Or $g_iBotAction = $eBotClose", reaped)
        passed = probe.index('$g_sMBRFuncEngineProbeState = "passed"', cancel_after_reap)
        self.assertLess(cancel, read)
        self.assertIn('$sError = "Engine start was cancelled"', probe[cancel:read])
        self.assertLess(reaped, cancel_after_reap)
        self.assertLess(cancel_after_reap, passed)
        self.assertIn("$iTimeoutMs = 15000", probe)

    def test_failure_is_sticky_only_for_current_host(self) -> None:
        self.assertIn("Global $g_bMBRFuncEngineAvailable = True", self.parent)
        self.assertIn('Global $g_sMBRFuncEngineProbeState = "not-run"', self.parent)
        mark_unavailable = function_body(self.parent, "MBRFuncMarkUnavailable")
        self.assertIn("$g_bMBRFuncEngineAvailable = False", mark_unavailable)
        self.assertIn('$g_sMBRFuncEngineProbeState = "failed"', mark_unavailable)
        probe = function_body(self.parent, "MBRFuncProbeEngine")
        self.assertLess(probe.index("If Not $g_bMBRFuncEngineAvailable Then"), probe.index("Run('"))
        self.assertEqual(probe.count("Run('"), 1)

    def test_phase_output_is_allowlisted_and_private_data_free(self) -> None:
        suffix = function_body(self.parent, "MBRFuncEngineProbePhaseSuffix")
        self.assertIn('Case "opened", "call-entered", "call-returned"', suffix)
        self.assertIn('Return " (phase: " & $sPhase & ")"', suffix)
        self.assertNotIn("@ScriptDir", suffix)
        self.assertNotIn("$iProbePid", suffix)

    def test_config_keeps_clr4_and_lib_probe_without_legacy_v2_policy(self) -> None:
        self.assertNotIn("useLegacyV2RuntimeActivationPolicy", self.config)
        self.assertIn('supportedRuntime version="v4.0"', self.config)
        self.assertIn('<probing privatePath="lib" />', self.config)


if __name__ == "__main__":
    unittest.main()
