; #FUNCTION# ====================================================================================================================
; Name ..........: Run verification state
; Description ...: Shared vocabulary for whether a run is executing against demonstrated evidence or being observed for the first time.
; Remarks .......: Diagnostic mode exists because a route that refuses to start cannot be debugged. Enabling it never edits the
;                  catalog's recognition or execution status; it only permits execution while stamping the run as unverified so
;                  logs, snapshots, and reports can never be mistaken for a demonstrated result.
; ===============================================================================================================================
#include-once
#include "..\Game\GameCatalog.au3"

Global Const $RUN_VERIFICATION_VERIFIED = "verified"
Global Const $RUN_VERIFICATION_DIAGNOSTIC = "unverified-diagnostic"

Func RunVerificationIsState($sState)
	Switch StringLower(StringStripWS(String($sState), $STR_STRIPALL))
		Case $RUN_VERIFICATION_VERIFIED, $RUN_VERIFICATION_DIAGNOSTIC
			Return True
	EndSwitch
	Return False
EndFunc   ;==>RunVerificationIsState

; Returns the verification state a surface would run under today, with a reason describing what is still missing.
Func RunVerificationSurfaceState($sSurfaceId, ByRef $sReason)
	$sReason = ""
	If CurrentGameBattleSurfaceReady($sSurfaceId, $sReason) Then Return $RUN_VERIFICATION_VERIFIED
	Return $RUN_VERIFICATION_DIAGNOSTIC
EndFunc   ;==>RunVerificationSurfaceState

; Merges two states. Unverified always wins, so a run that touched any unverified work stays unverified.
Func RunVerificationMerge($sLeft, $sRight)
	If StringLower($sLeft) = $RUN_VERIFICATION_DIAGNOSTIC Then Return $RUN_VERIFICATION_DIAGNOSTIC
	If StringLower($sRight) = $RUN_VERIFICATION_DIAGNOSTIC Then Return $RUN_VERIFICATION_DIAGNOSTIC
	Return $RUN_VERIFICATION_VERIFIED
EndFunc   ;==>RunVerificationMerge

Func RunVerificationLabel($sState)
	If StringLower($sState) = $RUN_VERIFICATION_DIAGNOSTIC Then Return "Unverified (diagnostic run)"
	Return "Verified"
EndFunc   ;==>RunVerificationLabel

; A short banner the GUI and the log can both show without further formatting.
Func RunVerificationBanner($sState, $sReason = "")
	If StringLower($sState) <> $RUN_VERIFICATION_DIAGNOSTIC Then Return ""
	Local $sBanner = "Diagnostic run: this surface has not been demonstrated on the current client."
	If StringStripWS($sReason, $STR_STRIPALL) <> "" Then $sBanner &= " " & $sReason & "."
	$sBanner &= " Treat every result as an observation, not a confirmed capability."
	Return $sBanner
EndFunc   ;==>RunVerificationBanner
