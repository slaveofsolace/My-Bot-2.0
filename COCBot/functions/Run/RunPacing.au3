; #FUNCTION# ====================================================================================================================
; Name ..........: Run pacing
; Description ...: How hard a run drives the emulator: gaps between actions, how long to let a screen settle, how many times to
;                  repeat an action that produced nothing, and when to rest.
; Remarks .......: These are reliability controls. An emulator redraws slower than the bot can tap, and reading a frame that is
;                  still moving is where wrong decisions come from; every value here buys accuracy with time.
;                  The clock is passed in rather than read here, so the whole module is decidable from its arguments and the
;                  contract tests can check the arithmetic without waiting for real milliseconds to pass.
;                  This file is part of My Bot, distributed under the GNU GPL.
; ===============================================================================================================================
#include-once

Global Const $RUN_PACING_MAX_ACTION_DELAY_MS = 5000
Global Const $RUN_PACING_MAX_SETTLE_MS = 10000
Global Const $RUN_PACING_MAX_RETRY_ATTEMPTS = 10
Global Const $RUN_PACING_MAX_BREAK_EVERY_MINUTES = 1440
Global Const $RUN_PACING_MAX_BREAK_MINUTES = 240

; These bounds are the same ones the planner controls offer. tools/check_plan_bridge.py compares the two on every push, so
; widening a control without widening the engine fails there rather than as a refused Apply in front of the operator.
Func RunPacingCreateDefault()
	Local $oPacing = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oPacing) Then Return SetError(1, 0, 0)
	$oPacing.CompareMode = 1
	$oPacing.Add("schema_version", 1)
	$oPacing.Add("action_delay_ms", 120)
	$oPacing.Add("settle_ms", 400)
	$oPacing.Add("retry_attempts", 2)
	$oPacing.Add("break_every_minutes", 0)
	$oPacing.Add("break_minutes", 5)
	; -1 means nothing has happened yet, which is distinct from having happened at time zero.
	$oPacing.Add("last_action_at_ms", -1)
	$oPacing.Add("last_break_at_ms", -1)
	Return $oPacing
EndFunc   ;==>RunPacingCreateDefault

Func RunPacingValidate(ByRef $oPacing, ByRef $sError)
	$sError = ""
	If Not IsObj($oPacing) Then
		$sError = "Run pacing is not an object"
		Return SetError(1, 0, False)
	EndIf

	Local $aRequired = ["schema_version", "action_delay_ms", "settle_ms", "retry_attempts", "break_every_minutes", "break_minutes", "last_action_at_ms", "last_break_at_ms"]
	For $i = 0 To UBound($aRequired) - 1
		If Not $oPacing.Exists($aRequired[$i]) Then
			$sError = "Missing run pacing field: " & $aRequired[$i]
			Return SetError(2, $i, False)
		EndIf
	Next

	Local $aBounded[5][3] = [ _
			["action_delay_ms", 0, $RUN_PACING_MAX_ACTION_DELAY_MS], _
			["settle_ms", 0, $RUN_PACING_MAX_SETTLE_MS], _
			["retry_attempts", 0, $RUN_PACING_MAX_RETRY_ATTEMPTS], _
			["break_every_minutes", 0, $RUN_PACING_MAX_BREAK_EVERY_MINUTES], _
			["break_minutes", 1, $RUN_PACING_MAX_BREAK_MINUTES]]
	For $i = 0 To UBound($aBounded, 1) - 1
		Local $iValue = Int($oPacing.Item($aBounded[$i][0]))
		If $iValue < $aBounded[$i][1] Or $iValue > $aBounded[$i][2] Then
			$sError = $aBounded[$i][0] & " must be between " & $aBounded[$i][1] & " and " & $aBounded[$i][2]
			Return SetError(3, $i, False)
		EndIf
	Next

	Return True
EndFunc   ;==>RunPacingValidate

Func RunPacingSet(ByRef $oPacing, $iActionDelayMs, $iSettleMs, $iRetryAttempts, $iBreakEveryMinutes, $iBreakMinutes, ByRef $sError)
	$sError = ""
	If Not RunPacingValidate($oPacing, $sError) Then Return SetError(1, 0, False)

	; Written into a copy of the values first so a rejected set leaves the object exactly as it was.
	Local $oCandidate = RunPacingCreateDefault()
	If Not IsObj($oCandidate) Then
		$sError = "Unable to create run pacing"
		Return SetError(2, 0, False)
	EndIf
	$oCandidate.Item("action_delay_ms") = Int($iActionDelayMs)
	$oCandidate.Item("settle_ms") = Int($iSettleMs)
	$oCandidate.Item("retry_attempts") = Int($iRetryAttempts)
	$oCandidate.Item("break_every_minutes") = Int($iBreakEveryMinutes)
	$oCandidate.Item("break_minutes") = Int($iBreakMinutes)
	If Not RunPacingValidate($oCandidate, $sError) Then Return SetError(3, 0, False)

	$oPacing.Item("action_delay_ms") = Int($iActionDelayMs)
	$oPacing.Item("settle_ms") = Int($iSettleMs)
	$oPacing.Item("retry_attempts") = Int($iRetryAttempts)
	$oPacing.Item("break_every_minutes") = Int($iBreakEveryMinutes)
	$oPacing.Item("break_minutes") = Int($iBreakMinutes)
	Return True
EndFunc   ;==>RunPacingSet

; How long to hold off before the next action, in milliseconds. Zero means go now. The caller does the sleeping, so a run
; that has been asked to stop can check that first instead of being stuck inside a wait.
Func RunPacingWaitBeforeAction(ByRef $oPacing, $iNowMs)
	Local $sError
	If Not RunPacingValidate($oPacing, $sError) Then Return SetError(1, 0, 0)

	Local $iLast = Int($oPacing.Item("last_action_at_ms"))
	If $iLast < 0 Then Return 0 ; the first action of a run does not wait for a predecessor

	Local $iElapsed = Int($iNowMs) - $iLast
	; A clock that went backwards means the caller's timer was restarted. Waiting the whole gap is the safe reading.
	If $iElapsed < 0 Then Return Int($oPacing.Item("action_delay_ms"))

	Local $iRemaining = Int($oPacing.Item("action_delay_ms")) - $iElapsed
	Return ($iRemaining > 0) ? $iRemaining : 0
EndFunc   ;==>RunPacingWaitBeforeAction

Func RunPacingNoteAction(ByRef $oPacing, $iAtMs)
	Local $sError
	If Not RunPacingValidate($oPacing, $sError) Then Return SetError(1, 0, False)
	$oPacing.Item("last_action_at_ms") = Int($iAtMs)
	Return True
EndFunc   ;==>RunPacingNoteAction

Func RunPacingSettleMilliseconds(ByRef $oPacing)
	Local $sError
	If Not RunPacingValidate($oPacing, $sError) Then Return SetError(1, 0, 0)
	Return Int($oPacing.Item("settle_ms"))
EndFunc   ;==>RunPacingSettleMilliseconds

Func RunPacingRetryAttempts(ByRef $oPacing)
	Local $sError
	If Not RunPacingValidate($oPacing, $sError) Then Return SetError(1, 0, 0)
	Return Int($oPacing.Item("retry_attempts"))
EndFunc   ;==>RunPacingRetryAttempts

Func RunPacingRestsEnabled(ByRef $oPacing)
	Local $sError
	If Not RunPacingValidate($oPacing, $sError) Then Return SetError(1, 0, False)
	Return Int($oPacing.Item("break_every_minutes")) > 0
EndFunc   ;==>RunPacingRestsEnabled

; True once the run has gone break_every_minutes without a rest. Measured from the last rest, or from the start of the run
; if there has not been one, so the interval means the same thing on the first rest as on the tenth.
Func RunPacingRestIsDue(ByRef $oPacing, $iRunStartedAtMs, $iNowMs)
	Local $sError
	If Not RunPacingValidate($oPacing, $sError) Then Return SetError(1, 0, False)
	If Not RunPacingRestsEnabled($oPacing) Then Return False

	Local $iSince = Int($oPacing.Item("last_break_at_ms"))
	If $iSince < 0 Then $iSince = Int($iRunStartedAtMs)

	Local $iElapsed = Int($iNowMs) - $iSince
	If $iElapsed < 0 Then Return False
	Return $iElapsed >= Int($oPacing.Item("break_every_minutes")) * 60000
EndFunc   ;==>RunPacingRestIsDue

Func RunPacingRestMilliseconds(ByRef $oPacing)
	Local $sError
	If Not RunPacingValidate($oPacing, $sError) Then Return SetError(1, 0, 0)
	If Not RunPacingRestsEnabled($oPacing) Then Return 0
	Return Int($oPacing.Item("break_minutes")) * 60000
EndFunc   ;==>RunPacingRestMilliseconds

; Recorded at the moment the rest ends, so the next interval is counted from when work resumed rather than from when it stopped.
Func RunPacingNoteRestTaken(ByRef $oPacing, $iEndedAtMs)
	Local $sError
	If Not RunPacingValidate($oPacing, $sError) Then Return SetError(1, 0, False)
	$oPacing.Item("last_break_at_ms") = Int($iEndedAtMs)
	Return True
EndFunc   ;==>RunPacingNoteRestTaken

Func RunPacingDescribe(ByRef $oPacing)
	Local $sError
	If Not RunPacingValidate($oPacing, $sError) Then Return SetError(1, 0, $sError)
	Local $sDescription = Int($oPacing.Item("action_delay_ms")) & "ms gap / " & Int($oPacing.Item("settle_ms")) & "ms settle"
	If Int($oPacing.Item("retry_attempts")) > 0 Then $sDescription &= " / " & Int($oPacing.Item("retry_attempts")) & " retries"
	If RunPacingRestsEnabled($oPacing) Then
		$sDescription &= " / rest " & Int($oPacing.Item("break_minutes")) & "min every " & Int($oPacing.Item("break_every_minutes")) & "min"
	EndIf
	Return $sDescription
EndFunc   ;==>RunPacingDescribe
