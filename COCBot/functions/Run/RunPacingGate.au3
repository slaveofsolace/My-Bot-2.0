; #FUNCTION# ====================================================================================================================
; Name ..........: Run pacing gate
; Description ...: Makes the pacing settings actually take effect, by holding actions back until their gap has passed.
; Remarks .......: RunPacing.au3 is deliberately pure - it reads no clock and sleeps for nobody, which is what lets the contract
;                  tests check its arithmetic without waiting for real milliseconds. This is the other half: the one place that
;                  reads a clock and does the sleeping, so the module underneath stays testable.
;
;                  Nothing here does anything until a run installs pacing. With none installed every function returns
;                  immediately, so a bot that never opens the Run Planner behaves exactly as it did before this file existed.
;                  That matters because the gate sits in Click(), which is the most-travelled function in the program.
;                  This file is part of My Bot, distributed under the GNU GPL.
; ===============================================================================================================================
#include-once
#include "RunPacing.au3"
#include "RunEventLog.au3"

; The pacing a run installed, or 0 for none. Absence is the default and the safe state.
Global $g_oRunPacingActive = 0

; Milliseconds since this handle was taken. One fixed origin means "when did the last action happen" is answerable without
; storing wall-clock times, and it never goes backwards the way a system clock can.
Global $g_hRunPacingClock = TimerInit()

; When pacing was installed. Rests are measured from here until the first one is taken.
Global $g_iRunPacingStartedAtMs = -1

Func RunPacingNowMs()
	Return Int(TimerDiff($g_hRunPacingClock))
EndFunc   ;==>RunPacingNowMs

Func RunPacingIsActive()
	Return IsObj($g_oRunPacingActive)
EndFunc   ;==>RunPacingIsActive

; Installs a run's pacing. The object is shared rather than copied, so the timestamps the gate writes are the ones the run's
; own intent carries.
Func RunPacingActivate(ByRef $oPacing, ByRef $sError)
	$sError = ""
	If Not RunPacingValidate($oPacing, $sError) Then Return SetError(1, 0, False)
	$g_oRunPacingActive = $oPacing
	$g_iRunPacingStartedAtMs = RunPacingNowMs()
	; Neither counter carries over from a previous run: the first action of a new run has no predecessor to wait for.
	$oPacing.Item("last_action_at_ms") = -1
	$oPacing.Item("last_break_at_ms") = -1
	Return True
EndFunc   ;==>RunPacingActivate

Func RunPacingDeactivate()
	$g_oRunPacingActive = 0
	$g_iRunPacingStartedAtMs = -1
EndFunc   ;==>RunPacingDeactivate

; Waits, in slices, and reports whether a running bot was stopped while it waited.
;
; _Sleep's own run-state check cannot be used here. It returns True whenever $g_bRunState is False, and that is the ordinary
; state of a bot sitting idle - so a gate built on it would report "stopped" for every click made outside a run and the
; caller would swallow the action. What actually matters is a bot that was running and has since been asked to stop, so that
; is what this watches for, and an idle bot simply waits out its gap like any other caller.
Func _RunPacingWait($iMilliseconds)
	If $iMilliseconds <= 0 Then Return False
	Local $bWasRunning = $g_bRunState

	Local $iRemaining = Int($iMilliseconds)
	While $iRemaining > 0
		Local $iSlice = ($iRemaining > 250) ? 250 : $iRemaining
		_Sleep($iSlice, False, False)
		If $bWasRunning And Not $g_bRunState Then Return True
		$iRemaining -= $iSlice
	WEnd
	Return False
EndFunc   ;==>_RunPacingWait

; Called immediately before an action goes out. Returns True only if a running bot was stopped while waiting, which callers
; pass straight through so a paced run stops as promptly as an unpaced one.
;
; The static guard is not paranoia: _Sleep pumps the message loop, and a GUI handler that clicked would otherwise re-enter
; this and wait against a timestamp that had not been written yet.
Func RunPacingGateAction()
	Local Static $bInside = False
	If Not IsObj($g_oRunPacingActive) Then Return False
	If $bInside Then Return False

	$bInside = True
	Local $iWait = RunPacingWaitBeforeAction($g_oRunPacingActive, RunPacingNowMs())
	Local $bStopped = _RunPacingWait($iWait)

	; Recorded after the wait, so the gap is measured between actions rather than between decisions to act. It is written
	; even when the bot stopped, so a run that resumes does not fire its next action with no gap at all.
	RunPacingNoteAction($g_oRunPacingActive, RunPacingNowMs())
	$bInside = False
	Return $bStopped
EndFunc   ;==>RunPacingGateAction

; Called after something that starts an animation, before the screen is read. Returns True if a running bot was stopped.
Func RunPacingSettle()
	If Not IsObj($g_oRunPacingActive) Then Return False
	Return _RunPacingWait(RunPacingSettleMilliseconds($g_oRunPacingActive))
EndFunc   ;==>RunPacingSettle

Func RunPacingActiveRetryAttempts()
	If Not IsObj($g_oRunPacingActive) Then Return 0
	Return RunPacingRetryAttempts($g_oRunPacingActive)
EndFunc   ;==>RunPacingActiveRetryAttempts

; Takes a scheduled rest if one is owed. Returns True if the bot was asked to stop during it.
;
; The rest is slept in one-second slices rather than one long call so the Stop button stays responsive: a run resting for ten
; minutes should not take ten minutes to notice it was stopped.
Func RunPacingRestIfDue()
	If Not IsObj($g_oRunPacingActive) Then Return False
	If Not RunPacingRestIsDue($g_oRunPacingActive, $g_iRunPacingStartedAtMs, RunPacingNowMs()) Then Return False

	Local $iRest = RunPacingRestMilliseconds($g_oRunPacingActive)
	If $iRest <= 0 Then Return False

	SetLog("Pacing: resting " & Round($iRest / 60000, 1) & " minutes", $COLOR_INFO)
	RunEventLogRestStarted(Round($iRest / 60000, 1))
	; Slept in slices so the Stop button stays responsive: a run resting for ten minutes should not take ten minutes to
	; notice it was stopped.
	If _RunPacingWait($iRest) Then Return True

	; Stamped at the end, so the next interval counts from when work resumed rather than from when it stopped.
	RunPacingNoteRestTaken($g_oRunPacingActive, RunPacingNowMs())
	RunEventLogRestEnded()
	SetLog("Pacing: resuming", $COLOR_INFO)
	Return False
EndFunc   ;==>RunPacingRestIfDue
