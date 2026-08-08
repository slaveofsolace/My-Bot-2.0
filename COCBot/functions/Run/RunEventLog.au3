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

Func RunEventLogPath()
	Return @ScriptDir & "\" & $RUN_EVENT_LOG_NAME
EndFunc   ;==>RunEventLogPath

; One id per bot launch, so a reader can tell one session's events from the next without a clock.
Func RunEventLogSessionId()
	If $g_sRunEventSessionId = "" Then
		$g_sRunEventSessionId = @YEAR & @MON & @MDAY & "-" & @HOUR & @MIN & @SEC & "-" & @AutoItPID
	EndIf
	Return $g_sRunEventSessionId
EndFunc   ;==>RunEventLogSessionId

; Milliseconds since launch. The event contract wants a number, and a monotonic one beats a wall clock
; that can step backwards mid-run.
Func _RunEventLogNowMs()
	Local Static $hClock = TimerInit()
	Return Int(TimerDiff($hClock))
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
	Return RunEventLogWrite("plan.applied", "info", $sDescription, $sSurfaceId, $sVerificationState)
EndFunc   ;==>RunEventLogPlanApplied

Func RunEventLogPlanBlocked($sSurfaceId, $sReason)
	Return RunEventLogWrite("plan.blocked", "warning", $sReason, $sSurfaceId, $RUN_VERIFICATION_DIAGNOSTIC)
EndFunc   ;==>RunEventLogPlanBlocked

Func RunEventLogPlanFileLoaded($sSummary)
	Return RunEventLogWrite("plan.loaded", "info", $sSummary)
EndFunc   ;==>RunEventLogPlanFileLoaded

Func RunEventLogRestStarted($iMinutes)
	Return RunEventLogWrite("pacing.rest.started", "info", "Resting " & $iMinutes & " minutes")
EndFunc   ;==>RunEventLogRestStarted

Func RunEventLogRestEnded()
	Return RunEventLogWrite("pacing.rest.ended", "info", "Resumed after a scheduled rest")
EndFunc   ;==>RunEventLogRestEnded
