; #FUNCTION# ====================================================================================================================
; Name ..........: Run event log
; Description ...: Writes the JSONL stream the control centre's Activity panel reads.
; Remarks .......: RunEvent.au3 defines the event contract and can append one; until this file existed the only caller was a
;                  test, so the Activity panel was wired to a file nothing ever wrote and was permanently empty.
;
;                  Everything here is best-effort. A run must never fail because its diagnostics could not be written, so every
;                  function returns a boolean nobody is obliged to check and no caller is given a reason to stop.
;                  This file is part of My Bot, distributed under the GNU GPL.
; ===============================================================================================================================
#include-once
#include "RunEvent.au3"
#include "RunVerification.au3"

; Read by tools/planner_ui.py. check_plan_bridge.py asserts the two agree on this path.
Global Const $RUN_EVENT_LOG_NAME = "logs\run-events.jsonl"

Global $g_iRunEventSequence = 0
Global $g_sRunEventSessionId = ""
Global $g_bRunEventSessionBound = False
Global $g_iRunEventBattleIndex = 0
Global $g_sRunEventSurfaceId = ""
Global $g_sRunEventRoute = ""
Global $g_sRunEventVerificationState = $RUN_VERIFICATION_DIAGNOSTIC
Global $g_hRunEventClock = TimerInit()

Func RunEventLogPath()
	Return @ScriptDir & "\" & $RUN_EVENT_LOG_NAME
EndFunc   ;==>RunEventLogPath

; Planned runs bind this logger to RunExecution's canonical session id. Events outside a planned run
; retain a process-local id so diagnostics still remain grouped without inventing a run session.
Func RunEventLogSessionId()
	If $g_sRunEventSessionId = "" Then
		$g_sRunEventSessionId = @YEAR & @MON & @MDAY & "-" & @HOUR & @MIN & @SEC & "-" & @AutoItPID
	EndIf
	Return $g_sRunEventSessionId
EndFunc   ;==>RunEventLogSessionId

Func RunEventLogBindSession($sSessionId)
	$sSessionId = StringStripWS(String($sSessionId), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sSessionId = "" Then Return SetError(1, 0, False)
	$g_sRunEventSessionId = $sSessionId
	$g_bRunEventSessionBound = True
	$g_iRunEventSequence = 0
	$g_iRunEventBattleIndex = 0
	$g_sRunEventSurfaceId = ""
	$g_sRunEventRoute = ""
	$g_sRunEventVerificationState = $RUN_VERIFICATION_DIAGNOSTIC
	$g_hRunEventClock = TimerInit()
	Return True
EndFunc   ;==>RunEventLogBindSession

Func RunEventLogReleaseSession($sExpectedSessionId = "")
	If $sExpectedSessionId <> "" And StringCompare($g_sRunEventSessionId, $sExpectedSessionId, 0) <> 0 Then Return False
	$g_sRunEventSessionId = ""
	$g_bRunEventSessionBound = False
	$g_iRunEventSequence = 0
	$g_iRunEventBattleIndex = 0
	$g_sRunEventSurfaceId = ""
	$g_sRunEventRoute = ""
	$g_sRunEventVerificationState = $RUN_VERIFICATION_DIAGNOSTIC
	$g_hRunEventClock = TimerInit()
	Return True
EndFunc   ;==>RunEventLogReleaseSession

Func _RunEventLogRouteForSurface($sSurfaceId)
	Switch StringLower(StringStripWS(String($sSurfaceId), $STR_STRIPALL))
		Case "regular", "revenge"
			Return "regular"
		Case "ranked"
			Return "ranked"
		Case "builder"
			Return "builder"
		Case Else
			If StringLeft(StringLower(String($sSurfaceId)), 7) = "legend-" Then Return "legend"
	EndSwitch
	Return ""
EndFunc   ;==>_RunEventLogRouteForSurface

Func _RunEventLogSetRunContext($sSurfaceId, $sVerificationState)
	If Not $g_bRunEventSessionBound Then Return False
	$g_sRunEventSurfaceId = StringLower(StringStripWS(String($sSurfaceId), $STR_STRIPALL))
	$g_sRunEventRoute = _RunEventLogRouteForSurface($g_sRunEventSurfaceId)
	If RunVerificationIsState($sVerificationState) Then
		$g_sRunEventVerificationState = $sVerificationState
	Else
		$g_sRunEventVerificationState = $RUN_VERIFICATION_DIAGNOSTIC
	EndIf
	Return True
EndFunc   ;==>_RunEventLogSetRunContext

; Milliseconds since the current session was bound (or the last release for unbound diagnostics).
; The clock is reset with the sequence so every planned run gets an independent monotonic timeline.
Func _RunEventLogNowMs()
	Return Int(TimerDiff($g_hRunEventClock))
EndFunc   ;==>_RunEventLogNowMs

Func RunEventLogWrite($sType, $sSeverity, $sMessage, $sSurfaceId = "", $sVerificationState = $RUN_VERIFICATION_VERIFIED)
	$g_iRunEventSequence += 1
	Local $oEvent = RunEventCreate($sType, $g_iRunEventSequence, _RunEventLogNowMs(), RunEventLogSessionId(), _
			$sSeverity, $sMessage, "", "", 0, 0, 0, 0, 0, $sVerificationState, $sSurfaceId)
	If Not IsObj($oEvent) Then Return False

	Local $sPath = RunEventLogPath()
	Return RunEventAppendJsonLine($sPath, $oEvent) <> 0
EndFunc   ;==>RunEventLogWrite

; The moments worth recording, named so a reader of the Activity panel can follow what happened without
; knowing the code.
Func RunEventLogPlanApplied($sSurfaceId, $sVerificationState, $sDescription)
	If $sVerificationState = $RUN_VERIFICATION_DIAGNOSTIC Then _
			Return RunEventLogWrite("route.diagnostic", "warning", $sDescription, $sSurfaceId, $sVerificationState)
	Return RunEventLogWrite("route.ready", "info", $sDescription, $sSurfaceId, $sVerificationState)
EndFunc   ;==>RunEventLogPlanApplied

Func RunEventLogPlanBlocked($sSurfaceId, $sReason)
	Return RunEventLogWrite("route.blocked", "warning", $sReason, $sSurfaceId, $RUN_VERIFICATION_DIAGNOSTIC)
EndFunc   ;==>RunEventLogPlanBlocked

Func RunEventLogPlanFileLoaded($sSummary)
	Return RunEventLogWrite("plan.loaded", "info", $sSummary)
EndFunc   ;==>RunEventLogPlanFileLoaded

; A prepared session may open/recover the selected emulator, prove Home, and normalize camera zoom
; before it is allowed to become running. Record that bounded preflight without calling it started.
Func RunEventLogPreflightStarted($sSurfaceId, $sVerificationState, $sDescription)
	_RunEventLogSetRunContext($sSurfaceId, $sVerificationState)
	Return RunEventLogWrite("session.preparing", "info", "Preflight started: " & $sDescription, $sSurfaceId, $sVerificationState)
EndFunc   ;==>RunEventLogPreflightStarted

Func RunEventLogRestStarted($iMinutes)
	Return RunEventLogWrite("pacing.rest.started", "info", "Resting " & $iMinutes & " minutes")
EndFunc   ;==>RunEventLogRestStarted

Func RunEventLogRestEnded()
	Return RunEventLogWrite("pacing.rest.ended", "info", "Resumed after a scheduled rest")
EndFunc   ;==>RunEventLogRestEnded

Func RunEventLogRunStarted($sSurfaceId, $sVerificationState, $sDescription)
	_RunEventLogSetRunContext($sSurfaceId, $sVerificationState)
	Return RunEventLogWrite("session.started", "info", $sDescription, $sSurfaceId, $sVerificationState)
EndFunc   ;==>RunEventLogRunStarted

; AttackReport calls this only after it has read and committed one complete attack result. The explicit
; bound-session guard prevents legacy/manual attacks from being represented as planner-run evidence.
Func RunEventLogBattleCompleted($iStars, $iDestructionPercent, $iGold, $iElixir, $iDarkElixir, $iTrophyDelta, $iSearchCount)
	If Not $g_bRunEventSessionBound Or $g_sRunEventSessionId = "" Then Return True

	Local $iBattleIndex = $g_iRunEventBattleIndex + 1
	Local $sMessage = "Battle " & $iBattleIndex & " completed: " & Int($iStars) & " stars, " & Int($iDestructionPercent) & _
			"% destruction, loot " & Int($iGold) & "/" & Int($iElixir) & "/" & Int($iDarkElixir) & _
			", trophy delta " & Int($iTrophyDelta) & ", searches " & Int($iSearchCount)
	Local $oEvent = RunEventCreate("battle.completed", $g_iRunEventSequence + 1, _RunEventLogNowMs(), $g_sRunEventSessionId, _
			"info", $sMessage, "", $g_sRunEventRoute, $iBattleIndex, $iGold, $iElixir, $iDarkElixir, 0, _
			$g_sRunEventVerificationState, $g_sRunEventSurfaceId, $iStars, $iDestructionPercent, $iTrophyDelta, $iSearchCount)
	If Not IsObj($oEvent) Then Return False

	$g_iRunEventSequence += 1
	$g_iRunEventBattleIndex = $iBattleIndex
	Return RunEventAppendJsonLine(RunEventLogPath(), $oEvent) <> 0
EndFunc   ;==>RunEventLogBattleCompleted

Func RunEventLogCombatDecision($sMessage)
	If Not $g_bRunEventSessionBound Then Return True
	Return RunEventLogWrite("combat.decision", "info", $sMessage, $g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogCombatDecision

Func RunEventLogCombatZoomVerified($iRedlinePoints)
	If Not $g_bRunEventSessionBound Then Return True
	Return RunEventLogWrite("combat.zoom-verified", "info", "Enemy zoom-out verified with " & _
			Int($iRedlinePoints) & " deployable red-line points", $g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogCombatZoomVerified

Func RunEventLogCombatDeploymentVerified($iBefore, $iAfter)
	If Not $g_bRunEventSessionBound Then Return True
	Return RunEventLogWrite("combat.deployment-verified", "info", "Deployment verified: " & Int($iBefore) & _
			" deployable troops reduced to " & Int($iAfter), $g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogCombatDeploymentVerified

Func RunEventLogHeroAbility($sHeroName, $sReason, $sSeverity = "info")
	If Not $g_bRunEventSessionBound Then Return True
	Local $sAction = " ability command issued: "
	If StringLower(String($sSeverity)) = "warning" Or StringLower(String($sSeverity)) = "error" Then _
		$sAction = " ability not issued: "
	Return RunEventLogWrite("combat.hero-ability", $sSeverity, $sHeroName & $sAction & $sReason, _
			$g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogHeroAbility

Func RunEventLogSpellCast($sSpellName, $iX, $iY, $sReason)
	If Not $g_bRunEventSessionBound Then Return True
	Return RunEventLogWrite("combat.spell-cast", "info", $sSpellName & " cast at " & Int($iX) & "," & Int($iY) & _
			" (" & $sReason & ")", $g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogSpellCast

Func RunEventLogSpellCommand($sSpellName, $iX, $iY, $sReason, $iBefore)
	If Not $g_bRunEventSessionBound Then Return True
	Return RunEventLogWrite("combat.spell-command", "info", $sSpellName & " command issued at " & Int($iX) & "," & _
			Int($iY) & " (" & $sReason & "; quantity before " & Int($iBefore) & ")", _
			$g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogSpellCommand

Func RunEventLogSpellUnconfirmed($sSpellName, $sReason)
	If Not $g_bRunEventSessionBound Then Return True
	Return RunEventLogWrite("combat.spell-unconfirmed", "warning", $sSpellName & " command unconfirmed: " & $sReason, _
			$g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogSpellUnconfirmed

Func RunEventLogSpellRetained($sSpellName, $sReason)
	If Not $g_bRunEventSessionBound Then Return True
	Return RunEventLogWrite("combat.spell-retained", "warning", $sSpellName & " retained: " & $sReason, _
			$g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogSpellRetained

Func RunEventLogMaintenanceCollectorsStarted()
	If Not $g_bRunEventSessionBound Then Return False
	Return RunEventLogWrite("maintenance.collectors.started", "info", _
			"Collectors-only Home Village pass started", $g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogMaintenanceCollectorsStarted

Func RunEventLogMaintenanceHomeVerified($iCollectorClicks)
	If Not $g_bRunEventSessionBound Then Return False
	Return RunEventLogWrite("maintenance.home-verified", "info", _
			"Home Village main screen re-proven; collector_clicks=" & Int($iCollectorClicks), _
			$g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogMaintenanceHomeVerified

Func RunEventLogMaintenanceCollectorsCompleted($iCollectorClicks)
	If Not $g_bRunEventSessionBound Then Return False
	If Int($iCollectorClicks) < 1 Then Return False
	Return RunEventLogWrite("maintenance.collectors.completed", "info", _
			"Collector clicks completed; collector_clicks=" & Int($iCollectorClicks), _
			$g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogMaintenanceCollectorsCompleted

Func RunEventLogMaintenanceCollectorsNoneActionable()
	If Not $g_bRunEventSessionBound Then Return False
	Return RunEventLogWrite("maintenance.collectors.none-actionable", "warning", _
			"No collector click was issued; recognition returned none or storage/threshold guards skipped every match; collector_clicks=0", _
			$g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogMaintenanceCollectorsNoneActionable

Func RunEventLogClanRequestStarted()
	If Not $g_bRunEventSessionBound Then Return False
	Return RunEventLogWrite("maintenance.clan-request.started", "info", _
			"Request-only Home Village pass started", $g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogClanRequestStarted

Func RunEventLogClanRequestUnavailable($sBeforeState)
	If Not $g_bRunEventSessionBound Then Return False
	Return RunEventLogWrite("maintenance.clan-request.unavailable", "warning", _
			"No Send issued; fresh request state=" & $sBeforeState, $g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogClanRequestUnavailable

Func RunEventLogClanRequestUnconfirmed($bSendIssued, $sDetail)
	If Not $g_bRunEventSessionBound Then Return False
	Return RunEventLogWrite("maintenance.clan-request.unconfirmed", "error", _
			"send_issued=" & ($bSendIssued ? "true" : "false") & "; " & $sDetail, _
			$g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogClanRequestUnconfirmed

Func RunEventLogClanRequestCommitted()
	If Not $g_bRunEventSessionBound Then Return False
	Return RunEventLogWrite("maintenance.clan-request.committed", "info", _
			"One Send committed; fresh state changed Available -> AlreadyMade", _
			$g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogClanRequestCommitted

Func RunEventLogClanRequestHomeVerified($sOutcome)
	If Not $g_bRunEventSessionBound Then Return False
	Return RunEventLogWrite("maintenance.clan-request.home-verified", "info", _
			"Home Village main screen re-proven after request outcome=" & $sOutcome, _
			$g_sRunEventSurfaceId, $g_sRunEventVerificationState)
EndFunc   ;==>RunEventLogClanRequestHomeVerified

Func RunEventLogRunStopping($sSurfaceId, $sVerificationState, $sReason)
	Return RunEventLogWrite("session.stopping", "info", "Stop condition: " & $sReason, $sSurfaceId, $sVerificationState)
EndFunc   ;==>RunEventLogRunStopping

Func RunEventLogRunCompleted($sSurfaceId, $sVerificationState, $sReason)
	Return RunEventLogWrite("session.completed", "info", "Run ended: " & $sReason, $sSurfaceId, $sVerificationState)
EndFunc   ;==>RunEventLogRunCompleted

Func RunEventLogRunFailed($sSurfaceId, $sVerificationState, $sReason)
	Return RunEventLogWrite("session.failed", "error", $sReason, $sSurfaceId, $sVerificationState)
EndFunc   ;==>RunEventLogRunFailed

Func RunEventLogEngineCheckStarted()
	Return RunEventLogWrite("engine.check.started", "info", _
			"Managed engine check started in the real backend; emulator and game actions remain disabled", "", $RUN_VERIFICATION_DIAGNOSTIC)
EndFunc   ;==>RunEventLogEngineCheckStarted

Func RunEventLogEngineCheckPassed()
	Return RunEventLogWrite("engine.check.passed", "info", _
			"Managed engine initialized without emulator or game input", "", $RUN_VERIFICATION_DIAGNOSTIC)
EndFunc   ;==>RunEventLogEngineCheckPassed

Func RunEventLogEngineCheckCancelled($sReason)
	Return RunEventLogWrite("engine.check.cancelled", "warning", "Managed engine check cancelled: " & $sReason, "", $RUN_VERIFICATION_DIAGNOSTIC)
EndFunc   ;==>RunEventLogEngineCheckCancelled

Func RunEventLogEngineCheckFailed($sReason)
	Return RunEventLogWrite("engine.check.failed", "error", "Managed engine check failed: " & $sReason, "", $RUN_VERIFICATION_DIAGNOSTIC)
EndFunc   ;==>RunEventLogEngineCheckFailed

Func RunEventLogEngineUnavailable($sReason)
	Return RunEventLogWrite("error", "error", "Managed engine unavailable: " & $sReason, "", $RUN_VERIFICATION_DIAGNOSTIC)
EndFunc   ;==>RunEventLogEngineUnavailable
