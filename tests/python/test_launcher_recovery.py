import copy
import hashlib
import pathlib
import socket
import subprocess
import tempfile
import threading
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
LAUNCHER = (ROOT / "My Bot 2.0.au3").read_text(encoding="utf-8-sig")
PLANNER_CONTROL = (ROOT / "COCBot" / "GUI" / "MBR GUI Control Run Planner.au3").read_text(encoding="utf-8-sig")
PLANNER_UI = (ROOT / "tools" / "planner_ui.py").read_text(encoding="utf-8-sig")
AUTOIT = pathlib.Path(r"C:\Program Files (x86)\AutoIt3\AutoIt3.exe")


def autoit_function(source, name):
    start = source.index(f"Func {name}(")
    end = source.index(f"EndFunc   ;==>{name}", start)
    return source[start:end] + f"EndFunc   ;==>{name}\n"


def receipt_is_valid(receipt, health, service, backend):
    """Executable model of the launcher fail-closed ownership checks."""
    token = receipt.get("token", "")
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    service_matches = all((
        receipt.get("schema") == "my-bot-planner-owner-v1",
        len(token) == 64 and all(character in "0123456789abcdef" for character in token),
        receipt.get("health_token") == digest,
        receipt.get("service_pid") == service.get("pid"),
        receipt.get("service_created") == service.get("created"),
        receipt.get("backend_pid") == receipt.get("parent_pid") == service.get("parent_pid"),
        service.get("image", "").lower().endswith("\\pythonw.exe"),
        receipt.get("command_sha256") == hashlib.sha256(service.get("command", "").encode()).hexdigest(),
        'tools\\planner_ui.py"' in service.get("command", ""),
        f'--owner-token "{token}"' in service.get("command", ""),
        '--profiles-root "' in service.get("command", ""),
    ))
    if not service_matches:
        return False
    if not backend.get("exists", True):
        return True
    backend_matches = all((
        backend.get("pid") == receipt.get("backend_pid"),
        backend.get("created") == receipt.get("backend_created"),
        backend.get("image", "").lower().endswith("\\mybot.run.exe"),
    ))
    health_matches = all((
        health.get("available", True),
        health.get("owner_token_kind") == "sha256",
        health.get("owner_token") == digest,
        health.get("service_pid") == service.get("pid"),
    ))
    return backend_matches and (not health.get("available", True) or health_matches)


class LauncherRecoveryContractTests(unittest.TestCase):
    def test_recovery_is_explicit_and_runs_before_install_validation(self):
        recovery_gate = 'If _CommandLineHas("/recover") Or _CommandLineHas("/repair") Then'
        self.assertIn(recovery_gate, LAUNCHER)
        self.assertLess(LAUNCHER.index(recovery_gate), LAUNCHER.index("If Not _ValidateInstallation()"))

    def test_only_exact_checkout_process_paths_are_closed(self):
        self.assertIn('StringLower(_ProcessImagePath($iPid)) <> StringLower($sExpectedPath)', LAUNCHER)
        self.assertIn('_CloseExactPathProcesses("MyBot.run.MiniGui.exe", $g_sControllerPath)', LAUNCHER)
        self.assertIn('_CloseExactPathProcesses("MyBot.run.exe", $g_sHostPath)', LAUNCHER)
        self.assertIn('_CloseExactPathProcesses("My Bot 2.0.exe", @ScriptFullPath, @AutoItPID)', LAUNCHER)

    def test_owned_autoit_errors_are_logged_before_close(self):
        start = LAUNCHER.index("Func _CloseOwnedAutoItErrorDialogs()")
        end = LAUNCHER.index("EndFunc   ;==>_CloseOwnedAutoItErrorDialogs", start)
        body = LAUNCHER[start:end]
        self.assertIn('WinList("AutoIt Error")', body)
        self.assertIn("@ScriptDir", body)
        self.assertLess(body.index('_RecoveryLog("closing owned AutoIt error'), body.index("WinClose($hDialog)"))

    def test_recovery_never_targets_bluestacks(self):
        start = LAUNCHER.index("Func _RecoverBotStack()")
        end = LAUNCHER.index("EndFunc   ;==>_RecoverBotStack", start)
        body = LAUNCHER[start:end]
        self.assertNotIn("BlueStacks", body)
        self.assertNotIn("HD-Player", body)

    def test_recovery_closes_only_a_verified_checkout_planner_service(self):
        self.assertIn('Global Const $g_sPlannerServiceName = "my-bot-control-center"', LAUNCHER)
        start = LAUNCHER.index("Func _CloseOwnedPlannerService()")
        end = LAUNCHER.index("EndFunc   ;==>_CloseOwnedPlannerService", start)
        body = LAUNCHER[start:end]
        for proof in (
            "$g_sPlannerServiceName",
            '"repo_root"',
            '"build_sha256"',
            '"service_pid"',
            '"owner_token"',
            "_FileSha256($g_sPlannerScriptPath)",
            "_ReadPlannerOwnershipReceipt()",
            "_PlannerReceiptMatchesService(",
        ):
            self.assertIn(proof, body)
        service_proof = LAUNCHER[
            LAUNCHER.index("Func _PlannerReceiptMatchesService("):
            LAUNCHER.index("EndFunc   ;==>_PlannerReceiptMatchesService")
        ]
        self.assertIn("_ProcessImagePath($iServicePid)", service_proof)
        self.assertIn('"\\\\pythonw\\.exe$"', service_proof)
        self.assertLess(body.index("_PlannerReceiptMatchesService("), body.index("ProcessClose($iPid)"))
        recovery = LAUNCHER[LAUNCHER.index("Func _RecoverBotStack()"):LAUNCHER.index("EndFunc   ;==>_RecoverBotStack")]
        self.assertIn("Local $bPlannerClosed = _CloseOwnedPlannerService()", recovery)
        self.assertIn("And $bPlannerClosed", recovery)

    def test_planner_ownership_receipt_is_atomic_and_health_hides_raw_token(self):
        for field in (
            '"schema"', '"token"', '"health_token"', '"service_pid"', '"service_created"',
            '"backend_pid"', '"backend_created"', '"parent_pid"', '"python_image_token"',
            '"script_path_token"', '"profiles_root_token"', '"command_sha256"', '"build_sha256"',
        ):
            self.assertIn(field, PLANNER_CONTROL)
        writer = PLANNER_CONTROL[
            PLANNER_CONTROL.index("Func _RunPlannerWriteOwnershipReceipt"):
            PLANNER_CONTROL.index("EndFunc   ;==>_RunPlannerWriteOwnershipReceipt")
        ]
        self.assertLess(writer.index("FileWrite("), writer.index("FileMove("))
        self.assertIn('BCryptGenRandom', PLANNER_CONTROL)
        self.assertIn('"owner_token": hashlib.sha256(', PLANNER_UI)
        self.assertNotIn('"owner_token": SERVICE_OWNER_TOKEN', PLANNER_UI)

    def test_recovery_rejects_spoofed_health_foreign_pid_and_stale_receipt(self):
        token = "ab" * 32
        command = (
            '"C:\\Python313\\pythonw.exe" "C:\\My Bot 2.0\\tools\\planner_ui.py" '
            f'--no-browser --owner-token "{token}" --profiles-root "C:\\Profiles"'
        )
        service = {
            "pid": 200,
            "created": "01da000000000001",
            "parent_pid": 100,
            "image": "C:\\Python313\\pythonw.exe",
            "command": command,
        }
        backend = {"pid": 100, "created": "01da000000000002", "image": "C:\\My Bot 2.0\\MyBot.run.exe"}
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        receipt = {
            "schema": "my-bot-planner-owner-v1",
            "token": token,
            "health_token": digest,
            "service_pid": 200,
            "service_created": service["created"],
            "backend_pid": 100,
            "backend_created": backend["created"],
            "parent_pid": 100,
            "command_sha256": hashlib.sha256(command.encode()).hexdigest(),
        }
        health = {"service_pid": 200, "owner_token_kind": "sha256", "owner_token": digest}
        self.assertTrue(receipt_is_valid(receipt, health, service, backend), "valid owner must remain recoverable")

        spoofed_health = copy.deepcopy(health)
        spoofed_health["owner_token"] = "0" * 64
        self.assertFalse(receipt_is_valid(receipt, spoofed_health, service, backend))

        hung_health = {"available": False}
        self.assertTrue(receipt_is_valid(receipt, hung_health, service, backend), "hung exact owner must be recoverable")

        dead_backend = copy.deepcopy(backend)
        dead_backend["exists"] = False
        self.assertTrue(receipt_is_valid(receipt, health, service, dead_backend), "exact orphan must be recoverable")

        foreign_service = copy.deepcopy(service)
        foreign_service["image"] = "C:\\Windows\\System32\\not-pythonw.exe"
        self.assertFalse(receipt_is_valid(receipt, health, foreign_service, backend))

        reused_pid = copy.deepcopy(service)
        reused_pid["created"] = "01da000000000099"
        self.assertFalse(receipt_is_valid(receipt, health, reused_pid, backend))

        stale_backend = copy.deepcopy(backend)
        stale_backend["created"] = "01da000000000099"
        self.assertFalse(receipt_is_valid(receipt, health, service, stale_backend))

    def test_launcher_rechecks_receipt_and_pid_identity_immediately_before_close(self):
        start = LAUNCHER.index("Func _CloseOwnedPlannerService()")
        end = LAUNCHER.index("EndFunc   ;==>_CloseOwnedPlannerService", start)
        body = LAUNCHER[start:end]
        close_at = body.index("ProcessClose($iPid)")
        self.assertGreater(body[:close_at].count("_PlannerReceiptMatchesService("), 1)
        self.assertIn("_ReadPlannerOwnershipReceipt() <> $sReceipt", body[:close_at])
        self.assertIn("_ProcessCreationId", LAUNCHER)
        self.assertIn("_ProcessParentPid", LAUNCHER)
        self.assertIn("_ProcessCommandLine", LAUNCHER)
        self.assertIn("_PlannerReceiptMatchesLiveBackend", body)
        self.assertIn("recovering unresponsive planner with exact live-owner receipt", body)
        self.assertIn("recovering orphaned planner with exact service receipt", body)
        self.assertIn("_PlannerReceiptPathSafe(True)", body)
        recovery = LAUNCHER[LAUNCHER.index("Func _RecoverBotStack()"):LAUNCHER.index("EndFunc   ;==>_RecoverBotStack")]
        self.assertLess(recovery.index("_CloseOwnedPlannerService()"), recovery.index('_CloseExactPathProcesses("MyBot.run.exe"'))

    def test_orphan_close_reports_foreign_listener_as_unresolved(self):
        start = LAUNCHER.index("Func _CloseOwnedPlannerService()")
        end = LAUNCHER.index("EndFunc   ;==>_CloseOwnedPlannerService", start)
        body = LAUNCHER[start:end]
        close_at = body.index("ProcessClose($iPid)")
        post_close = body[close_at:]
        self.assertIn("$bObservedForeignHealth", body[:close_at])
        self.assertIn("_ReadPlannerHealthBounded($sRemainingHealth)", post_close)
        self.assertIn("foreign planner listener still answers", post_close)
        self.assertIn("Return False", post_close)
        self.assertNotIn("ProcessClose", post_close[post_close.index("$sRemainingHealth"):])

    def test_every_recovery_health_read_has_explicit_winhttp_timeouts(self):
        helper = autoit_function(LAUNCHER, "_ReadPlannerHealthBounded")
        for proof in (
            'ObjEvent("AutoIt.Error", "_PlannerHealthComError")',
            'ObjCreate("WinHttp.WinHttpRequest.5.1")',
            "$oRequest.SetProxy(1)",
            "$oRequest.SetTimeouts(",
            '$oRequest.Open("GET", $sUrl, True)',
            "$oRequest.WaitForResponse(1)",
            "$oRequest.Abort()",
        ):
            self.assertIn(proof, helper)
        start = LAUNCHER.index("Func _CloseOwnedPlannerService()")
        end = LAUNCHER.index("EndFunc   ;==>_CloseOwnedPlannerService", start)
        body = LAUNCHER[start:end]
        self.assertNotIn("InetRead(", body)
        self.assertEqual(body.count("_ReadPlannerHealthBounded("), 3)

    @unittest.skipUnless(AUTOIT.is_file(), "AutoIt runtime is required for the hostile-listener test")
    def test_hostile_listener_that_never_replies_is_bounded(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        accepted = threading.Event()
        release = threading.Event()

        def hold_connection():
            connection = None
            try:
                connection, _ = listener.accept()
                accepted.set()
                connection.recv(4096)
                release.wait(4)
            finally:
                if connection is not None:
                    connection.close()
                listener.close()

        server = threading.Thread(target=hold_connection, daemon=True)
        server.start()
        declarations = "\n".join((
            'Global Const $g_sControlCenterUrl = "http://127.0.0.1:8765/"',
            'Global Const $g_iPlannerHealthResolveTimeoutMs = 200',
            'Global Const $g_iPlannerHealthConnectTimeoutMs = 300',
            'Global Const $g_iPlannerHealthSendTimeoutMs = 300',
            'Global Const $g_iPlannerHealthReceiveTimeoutMs = 500',
            'Global $g_bPlannerHealthComError = False',
        ))
        harness = "\n".join((
            'Opt("MustDeclareVars", 1)',
            declarations,
            autoit_function(LAUNCHER, "_PlannerHealthComError"),
            autoit_function(LAUNCHER, "_ReadPlannerHealthBounded"),
            'Local $sHealth = ""',
            'Local $hTimer = TimerInit()',
            'Local $bHealthy = _ReadPlannerHealthBounded($sHealth, $CmdLine[1])',
            'Local $iElapsed = Int(TimerDiff($hTimer))',
            'ConsoleWrite($iElapsed & @CRLF)',
            'Exit ($bHealthy ? 2 : 0)',
        ))
        try:
            with tempfile.TemporaryDirectory() as folder:
                script = pathlib.Path(folder) / "bounded-health.au3"
                script.write_text(harness, encoding="utf-8-sig")
                started = time.monotonic()
                result = subprocess.run(
                    [str(AUTOIT), str(script), f"http://127.0.0.1:{port}/api/health"],
                    capture_output=True,
                    text=True,
                    timeout=4,
                    check=False,
                )
                wall_ms = int((time.monotonic() - started) * 1000)
            self.assertTrue(accepted.wait(1), "hostile listener did not receive the request")
            self.assertEqual(result.returncode, 0, result.stderr)
            helper_ms = int(result.stdout.strip())
            self.assertLess(helper_ms, 2000, result.stdout)
            self.assertLess(wall_ms, 3000, f"wall clock was {wall_ms} ms")
        finally:
            release.set()
            server.join(timeout=1)

    def test_native_start_never_reuses_generic_healthy_service(self):
        start = PLANNER_CONTROL[
            PLANNER_CONTROL.index("Func _RunPlannerStartService"):
            PLANNER_CONTROL.index("EndFunc   ;==>_RunPlannerStartService")
        ]
        adopter = PLANNER_CONTROL[
            PLANNER_CONTROL.index("Func _RunPlannerAdoptOwnedHealthyService"):
            PLANNER_CONTROL.index("EndFunc   ;==>_RunPlannerAdoptOwnedHealthyService")
        ]
        self.assertNotIn("If _RunPlannerServiceHealthy() Then Return True", start)
        self.assertIn("If _RunPlannerAdoptOwnedHealthyService() Then Return True", start)
        self.assertGreaterEqual(start.count("Planner service ownership could not be verified"), 2)
        for proof in (
            "_RunPlannerReadOwnershipReceipt()",
            '_RunPlannerReceiptString($sReceipt, "token")',
            "_RunPlannerHashText($sOwnerToken)",
            "_RunPlannerReceiptMatchesLiveService(",
            "$g_iRunPlannerOwnedServicePid = $iPid",
            "$g_sRunPlannerOwnedServiceToken = $sOwnerToken",
        ):
            self.assertIn(proof, adopter)

    def test_launcher_errors_are_logged_and_bounded_without_topmost_focus(self):
        start = LAUNCHER.index("Func _ShowError($sMessage)")
        end = LAUNCHER.index("EndFunc   ;==>_ShowError", start)
        body = LAUNCHER[start:end]
        self.assertIn('launcher error; pid=', body)
        self.assertIn("@ScriptFullPath", body)
        self.assertNotIn("$MB_TOPMOST", body)
        self.assertIn("$g_iLauncherErrorTimeoutSec", body)
        self.assertLess(body.index('_RecoveryLog("launcher error;'), body.index("MsgBox("))

    def test_launcher_owns_a_visible_control_center_strip(self):
        self.assertIn('GUICreate("My Bot 2.0 Control"', LAUNCHER)
        self.assertIn('GUICtrlCreateButton("OPEN CONTROL CENTER"', LAUNCHER)
        self.assertIn('GUICtrlSetOnEvent($g_idOpenControlCenter, "_OpenControlCenter")', LAUNCHER)
        self.assertNotIn("$WS_EX_TOPMOST", LAUNCHER)
        self.assertLess(LAUNCHER.index("_ShowControlStrip($hController)"), LAUNCHER.index("_DockWhenReady($hController"))


if __name__ == "__main__":
    unittest.main()
