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
MBRFUNC = (ROOT / "COCBot" / "functions" / "Other" / "MBRFunc.au3").read_text(encoding="utf-8-sig")
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


ENGINE_PHASES = (
    "prepared", "pool-entered", "pool-returned", "max-entered", "max-returned",
    "android-entered", "android-returned", "gui-entered", "initialized", "failed",
)


def engine_receipt_is_valid(receipt, owner):
    """Executable model of the launcher's exact in-host initialization owner proof."""
    return all((
        receipt.get("schema") == "engine-init-supervisor-v1",
        receipt.get("token") == owner.get("token"),
        len(receipt.get("token", "")) == 64,
        all(character in "0123456789abcdef" for character in receipt.get("token", "")),
        receipt.get("launcher_pid") == owner.get("launcher_pid"),
        receipt.get("launcher_created") == owner.get("launcher_created"),
        owner.get("launcher_live_created") == owner.get("launcher_created"),
        receipt.get("controller_pid") == owner.get("controller_pid"),
        receipt.get("controller_created") == owner.get("controller_created"),
        owner.get("controller_live_created") == owner.get("controller_created"),
        owner.get("controller_parent_pid") == owner.get("launcher_pid"),
        owner.get("controller_image", "").lower() == owner.get("expected_controller_image", "").lower(),
        receipt.get("backend_pid") == owner.get("backend_pid"),
        receipt.get("backend_created") == owner.get("backend_created"),
        owner.get("backend_live_created") == owner.get("backend_created"),
        receipt.get("parent_pid") == owner.get("controller_pid") == owner.get("backend_parent_pid"),
        owner.get("backend_image", "").lower() == owner.get("expected_backend_image", "").lower(),
        receipt.get("phase") in ENGINE_PHASES,
        isinstance(receipt.get("sequence"), int) and receipt.get("sequence") >= 0,
    ))


def engine_cancel_matches(receipt, cancel):
    start_request_id = receipt.get("start_request_id", "")
    return all((
        start_request_id != "",
        cancel.get("schema") == "engine-init-cancel-v1",
        cancel.get("token") == receipt.get("token"),
        cancel.get("expected_start_request_id") == start_request_id,
    ))


def engine_generation_key(receipt):
    """PID reuse is a new generation only when the exact creation identity also changes."""
    return receipt.get("backend_pid"), receipt.get("backend_created")


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

    def test_recovery_closes_only_identity_bound_backend_adb_children(self):
        recovery = LAUNCHER[LAUNCHER.index("Func _RecoverBotStack()"):LAUNCHER.index("EndFunc   ;==>_RecoverBotStack")]
        snapshot = LAUNCHER[LAUNCHER.index("Func _SnapshotOwnedAdbChildren("):LAUNCHER.index("EndFunc   ;==>_SnapshotOwnedAdbChildren")]
        close = LAUNCHER[LAUNCHER.index("Func _CloseVerifiedAdbChildren("):LAUNCHER.index("EndFunc   ;==>_CloseVerifiedAdbChildren")]
        self.assertLess(recovery.index("_SnapshotOwnedAdbChildren()"), recovery.index('_CloseExactPathProcesses("MyBot.run.MiniGui.exe"'))
        self.assertLess(recovery.index('_CloseExactPathProcesses("MyBot.run.exe"'), recovery.index("_CloseVerifiedAdbChildren("))
        self.assertIn('StringLower(_ProcessImagePath($iBackendPid)) <> StringLower($g_sHostPath)', snapshot)
        self.assertIn('Local $aAdbNames[2] = ["HD-Adb.exe", "adb.exe"]', snapshot)
        self.assertIn("_ProcessParentPid($iPid) <> $iBackendPid", snapshot)
        self.assertIn("_ProcessCreationId($iPid)", snapshot)
        self.assertIn("_ProcessCreationId($iPid) <> $sCreated", close)
        self.assertIn("_ProcessParentPid($iPid) <> $iBackendPid", close)
        self.assertIn("Not _ProcessNameMatches($iPid, $sName)", close)
        self.assertIn("ProcessClose($iPid)", close)
        self.assertIn("ProcessWaitClose($iPid, 2)", close)
        self.assertIn("And $bAdbChildrenClosed", recovery)
        self.assertNotIn("kill-server", recovery + snapshot + close)
        self.assertNotIn("HD-Player", recovery + snapshot + close)

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

    def test_recovery_closes_only_receipt_bound_launch_only_bluestacks(self):
        recovery = autoit_function(LAUNCHER, "_RecoverBotStack")
        controller_exit = autoit_function(LAUNCHER, "_RecoverExitedOwnedControllerStack")
        close = autoit_function(LAUNCHER, "_CloseOwnedLaunchOnlyEmulator")
        finder = autoit_function(LAUNCHER, "_FindLaunchOnlyBlueStacksWindow")

        self.assertIn('Global Const $g_sLaunchOnlyEmulatorOwnershipSchema = "my-bot-launch-only-emulator-owner-v1"', LAUNCHER)
        self.assertIn("_CloseOwnedLaunchOnlyEmulator(False)", recovery)
        self.assertIn("_CloseOwnedLaunchOnlyEmulator(True)", controller_exit)
        self.assertLess(recovery.index("_CloseVerifiedAdbChildren"), recovery.index("_CloseOwnedLaunchOnlyEmulator(False)"))
        self.assertLess(controller_exit.index("_CloseVerifiedAdbChildren"), controller_exit.index("_CloseOwnedLaunchOnlyEmulator(True)"))

        for required in (
            '_PlannerReceiptString($sReceipt, "schema")',
            '_PlannerReceiptInt($sReceipt, "player_pid")',
            '_PlannerReceiptString($sReceipt, "player_created")',
            '_LauncherReceiptIdentifier($sReceipt, "instance")',
            "_ProcessCreationId($iPlayerPid) <> $sPlayerCreated",
            'StringRegExp(StringLower(_ProcessImagePath($iPlayerPid)), "\\\\hd-player\\.exe$")',
            "_ProcessCommandLine($iPlayerPid)",
            'StringInStr($sCommand, "--instance")',
            "_FindLaunchOnlyBlueStacksWindow($iPlayerPid, $sInstance)",
            "_ReadLaunchOnlyEmulatorOwnershipReceipt() <> $sReceipt",
            "taskkill.exe",
            '" -f -t -pid " & $iPlayerPid',
            "FileDelete($g_sLaunchOnlyEmulatorOwnershipReceipt)",
        ):
            self.assertIn(required, close)
        for forbidden in (
            '_CloseExactPathProcesses("HD-Player.exe"',
            'ProcessList("HD-Player.exe")',
            "ProcessClose($iPlayerPid)",
            "kill-server",
        ):
            self.assertNotIn(forbidden, close)
        for required in (
            'Local $sTitle = "BlueStacks5-" & $sInstance',
            "WinList($sTitle)",
            "WinGetProcess($hWindow) <> $iPlayerPid",
            'StringRegExp(_WindowClassName($hWindow), "^Qt[0-9]+QWindowIcon$")',
            'StringRegExp(StringLower(_ProcessImagePath($iPlayerPid)), "\\\\hd-player\\.exe$")',
        ):
            self.assertIn(required, finder)

    def test_recovery_closes_only_a_verified_checkout_planner_service(self):
        self.assertIn('Global Const $g_sPlannerServiceName = "my-bot-control-center"', LAUNCHER)
        start = LAUNCHER.index("Func _CloseOwnedPlannerService(")
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
        start = LAUNCHER.index("Func _CloseOwnedPlannerService(")
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
        start = LAUNCHER.index("Func _CloseOwnedPlannerService(")
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
        start = LAUNCHER.index("Func _CloseOwnedPlannerService(")
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

    def test_native_start_publishes_trusted_local_appdata_before_python_child(self):
        start = PLANNER_CONTROL[
            PLANNER_CONTROL.index("Func _RunPlannerStartService"):
            PLANNER_CONTROL.index("EndFunc   ;==>_RunPlannerStartService")
        ]
        publish = 'EnvSet("LOCALAPPDATA", $g_sMBRFuncRuntimeLocalAppData)'
        self.assertIn(publish, start)
        self.assertLess(start.index(publish), start.index("Local $iPid = Run("))
        self.assertIn("Trusted Local AppData could not be published", start)

    def test_launcher_errors_are_logged_and_bounded_without_topmost_focus(self):
        start = LAUNCHER.index("Func _ShowError($sMessage)")
        end = LAUNCHER.index("EndFunc   ;==>_ShowError", start)
        body = LAUNCHER[start:end]
        self.assertIn('launcher error; pid=', body)
        self.assertIn("@ScriptFullPath", body)
        self.assertNotIn("$MB_TOPMOST", body)
        self.assertIn("$g_iLauncherErrorTimeoutSec", body)
        self.assertLess(body.index('_RecoveryLog("launcher error;'), body.index("MsgBox("))

    def test_launcher_recovery_log_uses_created_per_user_parent(self):
        self.assertIn('Global Const $g_sRecoveryLogPath = $g_sUserDataRoot & "\\launcher-recovery.log"', LAUNCHER)
        body = autoit_function(LAUNCHER, "_RecoveryLog")
        self.assertIn("DirCreate($g_sUserDataRoot)", body)
        self.assertLess(body.index("DirCreate($g_sUserDataRoot)"), body.index("FileWriteLine($g_sRecoveryLogPath"))

    def test_launcher_accepts_only_the_reviewed_current_mini_title(self):
        self.assertIn(
            'Global Const $g_sControllerTitlePattern = "^My Bot 2\\.0 Mini v2\\.0\\.0(?: \\([A-Za-z0-9_. -]{1,64}\\))?$"',
            LAUNCHER,
        )
        self.assertNotIn('^My Bot Mini v8\\.2\\.0', LAUNCHER)
        instance = autoit_function(LAUNCHER, "_ControllerBlueStacksTitle")
        self.assertIn('"^My Bot 2\\.0 Mini v2\\.0\\.0 \\(([A-Za-z0-9_. -]{1,64})\\)$"', instance)

    def test_launcher_owns_a_visible_control_center_strip(self):
        self.assertIn('GUICreate("My Bot 2.0 Control"', LAUNCHER)
        self.assertIn('GUICtrlCreateButton("OPEN CONTROL CENTER"', LAUNCHER)
        self.assertIn('GUICtrlSetOnEvent($g_idOpenControlCenter, "_OpenControlCenter")', LAUNCHER)
        self.assertNotIn("$WS_EX_TOPMOST", LAUNCHER)
        self.assertLess(LAUNCHER.index("_ShowControlStrip($hController)"), LAUNCHER.index("_DockWhenReady($hController"))

    def test_new_controller_inherits_one_time_engine_supervisor_environment(self):
        for name in (
            "MYBOT_ENGINE_INIT_TOKEN",
            "MYBOT_ENGINE_INIT_LAUNCHER_PID",
            "MYBOT_ENGINE_INIT_LAUNCHER_CREATED",
        ):
            self.assertIn(name, LAUNCHER)
        self.assertIn('BCryptGenRandom', autoit_function(LAUNCHER, "_EngineSupervisorNewToken"))
        launch = LAUNCHER[LAUNCHER.index("Local $sEngineSupervisorError"):LAUNCHER.index("$hController = _WaitForControllerWindow")]
        self.assertLess(launch.index("_EngineSupervisorPrepareLaunch"), launch.index("Local $iControllerPid = Run("))
        self.assertLess(launch.index("Local $iControllerPid = Run("), launch.index("_EngineSupervisorClearLaunchEnvironment()"))
        self.assertNotIn("ShellExecute($g_sControllerPath", launch)
        existing = LAUNCHER[LAUNCHER.index("If $hController Then"):LAUNCHER.index("; A keeper that won the startup race")]
        self.assertIn("engine init supervision not armed: existing controller", existing)
        self.assertNotIn("_EngineSupervisorPrepareLaunch", existing)

    def test_launcher_timeout_preserves_the_descendant_stack_for_exact_recovery(self):
        timeout = LAUNCHER[LAUNCHER.index("$hController = _WaitForControllerWindow($iControllerPid, 60000)"):LAUNCHER.index("; The invisible launcher remains")]
        self.assertIn("controller stack left intact for recovery", timeout)
        self.assertIn("process stack was left intact for exact-ownership recovery", timeout)
        self.assertIn("Do not press Start. Run My Bot 2.0 Recovery", timeout)
        self.assertNotIn("ProcessClose(", timeout)
        self.assertNotIn("_CloseOwnedControllerAfterStartupTimeout", LAUNCHER)

    def test_engine_supervisor_receipt_binds_complete_process_chain(self):
        validator = autoit_function(LAUNCHER, "_EngineSupervisorReceiptMatches")
        for proof in (
            "$g_sEngineInitOwnershipSchema",
            '"token"',
            '"launcher_pid"',
            '"launcher_created"',
            '"controller_pid"',
            '"controller_created"',
            '"backend_pid"',
            '"backend_created"',
            '"parent_pid"',
            "_EngineSupervisorSequence($sReceipt)",
            '_ProcessCreationId(@AutoItPID)',
            '_ProcessCreationId($g_iEngineSupervisorControllerPid)',
            '_ProcessCreationId($iBackendPid)',
            '_ProcessParentPid($g_iEngineSupervisorControllerPid) <> @AutoItPID',
            '_ProcessParentPid($iBackendPid) <> $g_iEngineSupervisorControllerPid',
            'StringLower($g_sControllerPath)',
            'StringLower($g_sHostPath)',
            'If $sStartRequestId = "" Then Return False',
            '$iSequence <> $iPhaseRank + 1',
        ):
            self.assertIn(proof, validator)
        reader = autoit_function(LAUNCHER, "_EngineSupervisorReadReceipt")
        self.assertIn("_EngineSupervisorPathSafe($g_sEngineInitOwnershipReceipt, True)", reader)
        self.assertIn("StringLen($sReceipt) > 4096", reader)

    def test_native_engine_receipt_contract_matches_launcher(self):
        for shared in (
            '"engine-init-supervisor-v1"',
            '"MYBOT_ENGINE_INIT_TOKEN"',
            '"MYBOT_ENGINE_INIT_LAUNCHER_PID"',
            '"MYBOT_ENGINE_INIT_LAUNCHER_CREATED"',
            "engine-init-owner-v1.json",
        ):
            self.assertIn(shared, LAUNCHER)
            self.assertIn(shared, MBRFUNC)
        writer = autoit_function(MBRFUNC, "_MBRFuncPublishEngineReceipt")
        for field in (
            '"schema"', '"token"', '"launcher_pid"', '"launcher_created"',
            '"controller_pid"', '"controller_created"', '"backend_pid"',
            '"backend_created"', '"parent_pid"', '"phase"', '"start_request_id"',
            '"sequence"',
        ):
            self.assertIn(field, writer)
        self.assertIn("$g_iMBRFuncEngineReceiptSequence += 1", writer)
        self.assertLess(writer.index("FileFlush("), writer.index("FileMove("))
        self.assertIn("$g_sMBRFuncEngineReceiptStartRequestId", writer)
        self.assertNotIn("_MBRFuncCurrentStartRequestId()", writer)

    def test_engine_supervisor_rejects_forged_foreign_and_reused_processes(self):
        token = "cd" * 32
        receipt = {
            "schema": "engine-init-supervisor-v1",
            "token": token,
            "launcher_pid": 10,
            "launcher_created": "01da000000000010",
            "controller_pid": 20,
            "controller_created": "01da000000000020",
            "backend_pid": 30,
            "backend_created": "01da000000000030",
            "parent_pid": 20,
            "phase": "pool-entered",
            "sequence": 1,
            "start_request_id": "start.abc-123",
        }
        owner = {
            "token": token,
            "launcher_pid": 10,
            "launcher_created": receipt["launcher_created"],
            "launcher_live_created": receipt["launcher_created"],
            "controller_pid": 20,
            "controller_created": receipt["controller_created"],
            "controller_live_created": receipt["controller_created"],
            "controller_parent_pid": 10,
            "controller_image": r"C:\My Bot 2.0\MyBot.run.MiniGui.exe",
            "expected_controller_image": r"C:\My Bot 2.0\MyBot.run.MiniGui.exe",
            "backend_pid": 30,
            "backend_created": receipt["backend_created"],
            "backend_live_created": receipt["backend_created"],
            "backend_parent_pid": 20,
            "backend_image": r"C:\My Bot 2.0\MyBot.run.exe",
            "expected_backend_image": r"C:\My Bot 2.0\MyBot.run.exe",
        }
        self.assertTrue(engine_receipt_is_valid(receipt, owner))
        for key, value in (
            ("token", "ef" * 32),
            ("launcher_live_created", "01da000000000099"),
            ("controller_live_created", "01da000000000099"),
            ("controller_parent_pid", 999),
            ("controller_image", r"C:\Foreign\MyBot.run.MiniGui.exe"),
            ("backend_live_created", "01da000000000099"),
            ("backend_parent_pid", 999),
            ("backend_image", r"C:\Foreign\MyBot.run.exe"),
        ):
            forged = copy.deepcopy(owner)
            forged[key] = value
            self.assertFalse(engine_receipt_is_valid(receipt, forged), key)
        rolled = copy.deepcopy(receipt)
        rolled["phase"] = "unknown"
        self.assertFalse(engine_receipt_is_valid(rolled, owner))

    def test_engine_supervisor_deadlines_cancel_precedence_and_phase_order(self):
        poll = autoit_function(LAUNCHER, "_EngineSupervisorPoll")
        constants = {
            "$g_iEngineInitEnterTimeoutMs": "10000",
            "$g_iEngineInitPoolStallTimeoutMs": "90000",
            "$g_iEngineInitPostReturnTimeoutMs": "15000",
            "$g_iEngineInitAbsoluteTimeoutMs": "120000",
        }
        for name, value in constants.items():
            self.assertIn(f"Global Const {name} = {value}", LAUNCHER)
        self.assertIn('$sPhase = "prepared"', poll)
        self.assertIn('$sPhase = "pool-entered"', poll)
        self.assertIn('$iPhaseRank >= 2 And $iPhaseRank < 8', poll)
        self.assertIn("initialization exceeded the 120 second absolute cap", poll)
        self.assertLess(poll.index("_EngineSupervisorCancelMatches"), poll.index('$sPhase = "failed"'))
        self.assertLess(poll.index("_EngineSupervisorCancelMatches"), poll.index('$sPhase = "initialized"'))
        ranker = autoit_function(LAUNCHER, "_EngineSupervisorReceiptPhaseRank")
        positions = [ranker.index(f'Case "{phase}"') for phase in ENGINE_PHASES]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("$iPhaseRank < $g_iEngineSupervisorLastPhaseRank", poll)

    def test_engine_cancel_requires_nonce_and_exact_start_request(self):
        token = "ab" * 32
        receipt = {"token": token, "start_request_id": "start.1-abc"}
        cancel = {
            "schema": "engine-init-cancel-v1",
            "token": token,
            "expected_start_request_id": receipt["start_request_id"],
        }
        self.assertTrue(engine_cancel_matches(receipt, cancel))
        for key, value in (
            ("schema", "foreign"),
            ("token", "00" * 32),
            ("expected_start_request_id", "start.2-def"),
        ):
            forged = copy.deepcopy(cancel)
            forged[key] = value
            self.assertFalse(engine_cancel_matches(receipt, forged), key)
        no_start = copy.deepcopy(receipt)
        no_start["start_request_id"] = ""
        self.assertFalse(engine_cancel_matches(no_start, cancel))
        helper = autoit_function(LAUNCHER, "_EngineSupervisorCancelMatches")
        self.assertIn("$g_bEngineSupervisorPrepared", helper)
        self.assertIn('"expected_start_request_id"', helper)
        self.assertIn("$sExpected <> \"\" And $sExpected = $sReceiptStartRequestId", helper)

    def test_engine_supervisor_revalidates_before_exact_backend_close_and_never_retries(self):
        abort = autoit_function(LAUNCHER, "_EngineSupervisorAbort")
        close_at = abort.index("ProcessClose($iBackendPid)")
        latch_at = abort.index("$g_bEngineSupervisorAbortAttempted = True")
        self.assertLess(latch_at, close_at)
        self.assertEqual(abort.count("ProcessClose($iBackendPid)"), 1)
        self.assertIn("If $g_bEngineSupervisorAbortAttempted Then Return False", abort)
        self.assertIn("_EngineSupervisorReadReceipt", abort[:close_at])
        self.assertIn("$sCurrent <> $sReceipt", abort[:close_at])
        self.assertIn("$iCurrentBackend <> $iBackendPid", abort[:close_at])
        self.assertIn("_CloseOwnedPlannerService()", abort[close_at:])
        self.assertIn("backend_gone=true", abort)
        self.assertNotIn("Run(", abort)
        self.assertNotIn("ShellExecute", abort)
        self.assertNotIn("BlueStacks", abort)
        failure = autoit_function(LAUNCHER, "_EngineSupervisorRecordFailure")
        self.assertIn("$g_bEngineSupervisorFailureLatched = True", failure)
        self.assertIn("$g_sEngineSupervisorFailure = $sReason", failure)
        self.assertIn("_RecoveryLog", failure)

    def test_engine_supervisor_keeps_controller_binding_across_backend_generations(self):
        token = "7a" * 32
        first = {
            "schema": "engine-init-supervisor-v1", "token": token,
            "launcher_pid": 10, "launcher_created": "01da000000000010",
            "controller_pid": 20, "controller_created": "01da000000000020",
            "backend_pid": 30, "backend_created": "01da000000000030",
            "parent_pid": 20, "phase": "initialized", "sequence": 8,
            "start_request_id": "start.first",
        }
        second = copy.deepcopy(first)
        second.update({
            "backend_pid": 31, "backend_created": "01da000000000031",
            "phase": "prepared", "sequence": 0, "start_request_id": "",
        })
        owner = {
            "token": token, "launcher_pid": 10,
            "launcher_created": first["launcher_created"],
            "launcher_live_created": first["launcher_created"],
            "controller_pid": 20, "controller_created": first["controller_created"],
            "controller_live_created": first["controller_created"],
            "controller_parent_pid": 10,
            "controller_image": r"C:\My Bot 2.0\MyBot.run.MiniGui.exe",
            "expected_controller_image": r"C:\My Bot 2.0\MyBot.run.MiniGui.exe",
            "backend_pid": 30, "backend_created": first["backend_created"],
            "backend_live_created": first["backend_created"], "backend_parent_pid": 20,
            "backend_image": r"C:\My Bot 2.0\MyBot.run.exe",
            "expected_backend_image": r"C:\My Bot 2.0\MyBot.run.exe",
        }
        self.assertTrue(engine_receipt_is_valid(first, owner))
        next_owner = copy.deepcopy(owner)
        next_owner.update({
            "backend_pid": 31, "backend_created": second["backend_created"],
            "backend_live_created": second["backend_created"],
        })
        self.assertTrue(engine_receipt_is_valid(second, next_owner))
        self.assertNotEqual(engine_generation_key(first), engine_generation_key(second))
        self.assertEqual(first["token"], second["token"])
        self.assertEqual(first["controller_created"], second["controller_created"])
        self.assertLess(second["sequence"], first["sequence"])

        begin = autoit_function(LAUNCHER, "_EngineSupervisorBeginGeneration")
        reset = autoit_function(LAUNCHER, "_EngineSupervisorResetGeneration")
        poll = autoit_function(LAUNCHER, "_EngineSupervisorPoll")
        self.assertIn("$g_iEngineSupervisorBackendPid", begin)
        self.assertIn("$g_sEngineSupervisorBackendCreated", begin)
        self.assertLess(poll.index("_EngineSupervisorBeginGeneration"), poll.index("sequence rollback"))
        self.assertIn("$g_iEngineSupervisorLastSequence = -1", reset)
        self.assertNotIn("$g_sEngineSupervisorToken =", reset)
        self.assertNotIn("$g_iEngineSupervisorControllerPid =", reset)

        finalize = autoit_function(LAUNCHER, "_EngineSupervisorFinalize")
        abort = autoit_function(LAUNCHER, "_EngineSupervisorAbort")
        self.assertNotIn("_EngineSupervisorDisarm", finalize)
        self.assertNotIn("_EngineSupervisorDisarm", abort)
        for body in (begin, reset, finalize, abort, poll):
            self.assertNotIn("Run(", body)
            self.assertNotIn("ShellExecute", body)

    def test_engine_supervisor_polls_without_increasing_dock_frequency(self):
        wait = autoit_function(LAUNCHER, "_WaitForControllerWindow")
        dock_wait = autoit_function(LAUNCHER, "_DockWhenReady")
        keeper = autoit_function(LAUNCHER, "_KeepDocked")
        self.assertIn("_EngineSupervisorPoll()", wait)
        self.assertIn("_EngineSupervisorPoll()", dock_wait)
        self.assertIn("_EngineSupervisorPoll()", keeper)
        self.assertIn("Sleep(200)", wait)
        self.assertIn("Sleep(_EngineSupervisorPollDelay(500))", dock_wait)
        self.assertIn("Sleep(_EngineSupervisorPollDelay(_AdaptiveDockPollDelay", keeper)
        adaptive = autoit_function(LAUNCHER, "_AdaptiveDockPollDelay")
        self.assertIn("$g_iDockTransitionPollMs", adaptive)
        self.assertIn("$g_iDockStablePollMs", adaptive)
        self.assertIn("Global Const $g_iEngineInitActivePollMs = 250", LAUNCHER)
        active = autoit_function(LAUNCHER, "_EngineSupervisorNeedsFastPoll")
        delay = autoit_function(LAUNCHER, "_EngineSupervisorPollDelay")
        self.assertIn("$g_bEngineSupervisorPrepared", active)
        self.assertIn("$g_sEngineInitCancelPath", active)
        self.assertIn("$g_sEngineInitOwnershipReceipt", active)
        self.assertIn("$g_iEngineInitActivePollMs", delay)
        self.assertIn("Return $iDefaultDelayMs", delay)

    def test_controller_exit_runs_exact_recovery_before_launcher_exit(self):
        keeper = LAUNCHER.index("_KeepDocked($hController, $iControllerPid)")
        recover = LAUNCHER.index("_RecoverExitedOwnedControllerStack($iControllerPid", keeper)
        disarm = LAUNCHER.index('_EngineSupervisorDisarm("owned controller exited")', recover)
        terminal = LAUNCHER.index("Exit 0", disarm)
        self.assertLess(keeper, recover)
        self.assertLess(recover, disarm)
        self.assertLess(disarm, terminal)
        recovery = autoit_function(LAUNCHER, "_RecoverExitedOwnedControllerStack")
        self.assertIn("_CloseVerifiedLauncherBackend($iControllerPid, $iBackendPid, $sBackendCreated)", recovery)
        self.assertIn("_CloseOwnedPlannerService($iBackendPid, $sBackendCreated)", recovery)
        self.assertNotIn("_CloseExactPathProcesses", recovery)

    def test_automatic_cleanup_never_adopts_post_exit_adb_by_reused_parent_pid(self):
        recovery = autoit_function(LAUNCHER, "_RecoverExitedOwnedControllerStack")
        detector = autoit_function(LAUNCHER, "_HasUncapturedAdbChildForRecordedBackend")
        self.assertNotIn("_SnapshotAdbChildrenForRecordedBackend", LAUNCHER)
        self.assertIn("_HasUncapturedAdbChildForRecordedBackend($iBackendPid)", recovery)
        self.assertNotIn("_RememberLauncherOwnedAdbChildren", detector)
        self.assertNotIn("ProcessClose", detector)
        self.assertIn("refused uncaptured ADB child after backend exit", detector)
        self.assertIn("And Not $bUncapturedAdbChild", recovery)

    def test_live_backend_final_child_is_checked_again_after_backend_exit(self):
        recovery = autoit_function(LAUNCHER, "_RecoverExitedOwnedControllerStack")
        close_backend = recovery.index(
            "_CloseVerifiedLauncherBackend($iControllerPid, $iBackendPid, $sBackendCreated)"
        )
        post_close_guard = recovery.index("If $bBackendClosed And Not ProcessExists($iBackendPid)", close_backend)
        post_close_detector = recovery.index(
            "_HasUncapturedAdbChildForRecordedBackend($iBackendPid)", post_close_guard
        )
        close_children = recovery.index("_CloseVerifiedAdbChildren($aOwnedAdbChildren)", post_close_detector)
        self.assertEqual(
            [close_backend, post_close_guard, post_close_detector, close_children],
            sorted((close_backend, post_close_guard, post_close_detector, close_children)),
        )
        self.assertIn("Then $bUncapturedAdbChild = True", recovery[post_close_detector:close_children])

    def test_automatic_adb_identity_tracking_is_pruned_and_bounded(self):
        remember = autoit_function(LAUNCHER, "_RememberLauncherOwnedAdbChildren")
        prune = autoit_function(LAUNCHER, "_PruneLauncherOwnedAdbChildren")
        recovery = autoit_function(LAUNCHER, "_RecoverExitedOwnedControllerStack")
        self.assertIn("Global Const $g_iLauncherOwnedAdbChildLimit = 64", LAUNCHER)
        self.assertIn("_PruneLauncherOwnedAdbChildren()", remember)
        self.assertIn("$iNext > $g_iLauncherOwnedAdbChildLimit", remember)
        self.assertIn("$g_bLauncherOwnedAdbTrackingIncomplete = True", remember)
        self.assertIn("If $g_bLauncherOwnedAdbTrackingIncomplete Then Return False", recovery)
        self.assertIn("Not ProcessExists($iPid) Then ContinueLoop", prune)
        self.assertIn("_ProcessCreationId($iPid) <> $sCreated", prune)


if __name__ == "__main__":
    unittest.main()
