; #FUNCTION# ====================================================================================================================
; Name ..........: Acceptance stop-before-Home contract
; Description ...: Validates the inert, verifier-only barrier used to stop an exact Start generation before Home recognition.
; ===============================================================================================================================
#include-once

Global Const $ACCEPTANCE_STOP_BEFORE_HOME_ENV = "MYBOT_ACCEPTANCE_STOP_BEFORE_HOME"
Global Const $ACCEPTANCE_STOP_BEFORE_HOME_TOKEN_ENV = "MYBOT_ACCEPTANCE_STOP_BEFORE_HOME_TOKEN"
Global Const $ACCEPTANCE_STOP_BEFORE_HOME_SCHEMA = "mybot-acceptance-stop-before-home-v1"
Global Const $ACCEPTANCE_STOP_BEFORE_HOME_TIMEOUT_MS = 60000

; 0 means absent, 1 means active, and -1 means an attempted but malformed contract.
Func AcceptanceStopBeforeHomeEnvironmentState($sFlag, $sToken, ByRef $sReason)
	$sReason = ""
	$sFlag = String($sFlag)
	$sToken = String($sToken)
	If $sFlag = "" And $sToken = "" Then Return 0
	If $sFlag <> "1" Then
		$sReason = "The stop-before-Home acceptance flag must be exactly 1"
		Return -1
	EndIf
	If Not StringRegExp($sToken, "^sha256:[0-9a-f]{64}$") Then
		$sReason = "The stop-before-Home acceptance token is missing or malformed"
		Return -1
	EndIf
	Return 1
EndFunc   ;==>AcceptanceStopBeforeHomeEnvironmentState

Func AcceptanceStopBeforeHomeBindingValid($sMode, $sRunRequestId, $sSessionId, $sPlanRevision, $sPlanToken, _
		$sProfile, $sEmulator, $sInstance, ByRef $sReason)
	$sReason = ""
	If Not StringRegExp($sMode, "^(planned|native-profile)$") Then
		$sReason = "The acceptance barrier requires an accepted planned Start"
		Return False
	EndIf
	If Not StringRegExp($sRunRequestId, "^[A-Za-z0-9._-]{1,80}$") Then
		$sReason = "The acceptance barrier has no exact Start request identity"
		Return False
	EndIf
	If Not StringRegExp($sSessionId, "^[A-Za-z0-9._-]{1,128}$") Then
		$sReason = "The acceptance barrier has no exact run session identity"
		Return False
	EndIf
	Local $bPlanIdentityValid = ($sMode = "planned" And StringRegExp($sPlanToken, "^sha256:[0-9a-f]{64}$")) Or _
			($sMode = "native-profile" And $sPlanToken = "absent")
	If Not StringRegExp($sPlanRevision, "^(0|[1-9][0-9]{0,18})$") Or Not $bPlanIdentityValid Then
		$sReason = "The acceptance barrier is not bound to an accepted plan revision and token"
		Return False
	EndIf
	If Not StringRegExp($sProfile, "^[A-Za-z0-9._ -]{1,64}$") Then
		$sReason = "The acceptance barrier profile identity is missing or unsafe"
		Return False
	EndIf
	If $sEmulator <> "BlueStacks5" Or $sInstance <> "Pie64" Then
		$sReason = "The acceptance barrier requires the exact BlueStacks5 Pie64 target"
		Return False
	EndIf
	Return True
EndFunc   ;==>AcceptanceStopBeforeHomeBindingValid

Func AcceptanceStopBeforeHomeGenerationMatches($sExpectedRunRequestId, $sActualRunRequestId, _
		$sExpectedSessionId, $sActualSessionId, $sExpectedMode, $sActualMode, _
		$sExpectedPlanRevision, $sActualPlanRevision, $sExpectedPlanToken, $sActualPlanToken, _
		$sExpectedProfile, $sActualProfile, $sExpectedEmulator, $sActualEmulator, $sExpectedInstance, $sActualInstance)
	Return $sExpectedRunRequestId = $sActualRunRequestId And _
			$sExpectedSessionId = $sActualSessionId And _
			$sExpectedMode = $sActualMode And _
			$sExpectedPlanRevision = $sActualPlanRevision And _
			$sExpectedPlanToken = $sActualPlanToken And _
			$sExpectedProfile = $sActualProfile And _
			$sExpectedEmulator = $sActualEmulator And _
			$sExpectedInstance = $sActualInstance
EndFunc   ;==>AcceptanceStopBeforeHomeGenerationMatches
