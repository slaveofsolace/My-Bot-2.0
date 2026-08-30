; #FUNCTION# ====================================================================================================================
; Name ..........: Acceptance stop-before-Home contract
; Description ...: Validates the inert, verifier-only barrier used to stop an exact Start generation before Home recognition.
; ===============================================================================================================================
#include-once

Global Const $ACCEPTANCE_STOP_BEFORE_HOME_ENV = "MYBOT_ACCEPTANCE_STOP_BEFORE_HOME"
Global Const $ACCEPTANCE_STOP_BEFORE_HOME_TOKEN_ENV = "MYBOT_ACCEPTANCE_STOP_BEFORE_HOME_TOKEN"
Global Const $ACCEPTANCE_STOP_BEFORE_HOME_SCHEMA = "mybot-acceptance-stop-before-home-v1"
Global Const $ACCEPTANCE_LAUNCH_OWNER_SCHEMA = "my-bot-launch-only-emulator-owner-v2"
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

Func AcceptanceLaunchOwnerIdentityValid($sAuthorizationSha256, $sRuntimeSha256, $sIssuedAtUtc, _
		$iPlayerPid, $sPlayerCreated, $sPlayerPath, $iPlayerParentPid, $sPlayerParentCreated, $sPlayerParentPath, _
		$iAdbPid, $sAdbCreated, $sAdbPath, $sAdbSha256, $iAdbParentPid, $sAdbParentCreated, $sAdbParentPath, _
		ByRef $sReason)
	$sReason = ""
	If Not StringRegExp($sAuthorizationSha256, "^[0-9a-f]{64}$") Or _
			Not StringRegExp($sRuntimeSha256, "^[0-9a-f]{64}$") Or _
			Not StringRegExp($sAdbSha256, "^[0-9a-f]{64}$") Then
		$sReason = "The launch-owner receipt is missing an exact authorization, runtime, or ADB digest"
		Return False
	EndIf
	If Not StringRegExp($sIssuedAtUtc, "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z$") Then
		$sReason = "The launch-owner receipt has no exact UTC issuance timestamp"
		Return False
	EndIf
	If $iPlayerPid <= 0 Or $iAdbPid <= 0 Or $iPlayerParentPid <= 0 Or $iAdbParentPid <= 0 Or _
			$iPlayerParentPid <> $iAdbParentPid Then
		$sReason = "The launch-owner receipt does not bind one exact backend parent to the player and ADB child"
		Return False
	EndIf
	Local $aCreated = [$sPlayerCreated, $sPlayerParentCreated, $sAdbCreated, $sAdbParentCreated]
	For $sCreated In $aCreated
		If Not StringRegExp($sCreated, "^[0-9a-f]{16}$") Then
			$sReason = "The launch-owner receipt contains a missing or malformed process creation identity"
			Return False
		EndIf
	Next
	If $sPlayerParentCreated <> $sAdbParentCreated Or $sPlayerParentPath <> $sAdbParentPath Then
		$sReason = "The player and ADB identities do not share one exact backend parent generation"
		Return False
	EndIf
	Local $aPaths = [$sPlayerPath, $sPlayerParentPath, $sAdbPath, $sAdbParentPath]
	For $sPath In $aPaths
		If StringLen($sPath) < 4 Or StringLen($sPath) > 1024 Or _
				Not StringRegExp($sPath, "^[A-Za-z]:\\") Or StringRegExp($sPath, "[\x00-\x1f]") Then
			$sReason = "The launch-owner receipt contains a missing or unsafe executable path"
			Return False
		EndIf
	Next
	If Not StringRegExp(StringLower($sPlayerPath), "\\hd-player\.exe$") Or _
			Not StringRegExp(StringLower($sAdbPath), "\\(?:hd-adb|adb)\.exe$") Or _
			Not StringRegExp(StringLower($sPlayerParentPath), "\\mybot\.run\.exe$") Then
		$sReason = "The launch-owner receipt does not identify the exact player, ADB, and backend executable families"
		Return False
	EndIf
	Return True
EndFunc   ;==>AcceptanceLaunchOwnerIdentityValid
