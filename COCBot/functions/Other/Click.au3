; #FUNCTION# ====================================================================================================================
; Name ..........: Click, PureClick, ClickP
; Description ...: Clicks the BS screen on desired location
; Syntax ........: Click($x, $y, $times, $speed, $debugtxt, $bForceControl)
; Parameters ....: $x, $y are mandatory; optional $bForceControl bypasses ADB input for a verified window-control click
; Return values .: None
; Author ........: (2014)
; Modified ......: HungLe (may-2015) Sardo 2015-08
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; Related .......: checkMainscreen, isProblemAffect
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......: No
; ===============================================================================================================================

#include-once
#include <WinAPISys.au3>
#include "..\Run\RunPacingGate.au3"
#include "..\Run\NoPremiumPermitPolicy.au3"

; Premium-currency and purchase input is disabled in this build. This is a source-level invariant,
; not a profile preference: neither a saved INI value nor a GUI callback may turn it off.
Global Const $NO_PREMIUM_POLICY_ENABLED = True
Global Const $NO_PREMIUM_SURFACE_SAFE = 0
Global Const $NO_PREMIUM_SURFACE_BLOCKED = 1
Global Const $NO_PREMIUM_SURFACE_UNKNOWN = 2
Global $g_bNoPremiumPolicyTripped = False
Global $g_sNoPremiumInputPermitAction = ""
Global $g_iNoPremiumInputPermitX = -1
Global $g_iNoPremiumInputPermitY = -1
Global $g_hNoPremiumInputPermitTimer = 0

; Read one already-captured pixel without invoking any input helper. Keep the read error separate from
; the match result so a missing/corrupt recognition frame is never mistaken for an ordinary screen.
Func _NoPremiumPixelMatches(ByRef $aScreenCode, ByRef $bReadOk)
	If $g_hBitmap = 0 Or Not IsArray($aScreenCode) Or UBound($aScreenCode) < 4 Then
		$bReadOk = False
		Return False
	EndIf
	Local $iPixel = _GDIPlus_BitmapGetPixel($g_hBitmap, Int($aScreenCode[0]), Int($aScreenCode[1]))
	Local $iPixelError = @error
	If $iPixelError Then
		$bReadOk = False
		Return False
	EndIf
	Return _ColorCheck(Hex($iPixel, 6), Hex($aScreenCode[2], 6), $aScreenCode[3])
EndFunc   ;==>_NoPremiumPixelMatches

; Passive only: this function recognizes the inherited gem confirmation and shop-window anchors and
; never clicks a close, confirmation, or fallback coordinate.
Func NoPremiumSurfaceState(ByRef $sReason, $sPermitAction = "", $iExpectedX = Default, $iExpectedY = Default)
        $sReason = ""
	Local $iFrameWidth = _GDIPlus_ImageGetWidth($g_hBitmap)
	Local $iFrameWidthError = @error
	Local $iFrameHeight = _GDIPlus_ImageGetHeight($g_hBitmap)
	Local $iFrameHeightError = @error
	If $iFrameWidthError Or $iFrameHeightError Or $iFrameWidth <> $g_iGAME_WIDTH Or $iFrameHeight <> $g_iGAME_HEIGHT Then
		$sReason = "premium-surface recognition frame is unavailable or non-canonical"
		Return $NO_PREMIUM_SURFACE_UNKNOWN
	EndIf
        Local $bReadOk = True
	Local $bGemCorner = _NoPremiumPixelMatches($aIsGemWindow1, $bReadOk)
	Local $bGemLine1 = _NoPremiumPixelMatches($aIsGemWindow2, $bReadOk)
	Local $bGemLine2 = _NoPremiumPixelMatches($aIsGemWindow3, $bReadOk)
	Local $bGemLine3 = _NoPremiumPixelMatches($aIsGemWindow4, $bReadOk)
	Local $bShopWindow = _NoPremiumPixelMatches($g_aShopWindowOpen, $bReadOk)
	If Not $bReadOk Then
		$sReason = "premium-surface recognition failed"
		Return $NO_PREMIUM_SURFACE_UNKNOWN
	EndIf
	If $bGemCorner Or ($bGemLine1 And $bGemLine2 And $bGemLine3) Then
		$sReason = "gem confirmation surface recognized"
		Return $NO_PREMIUM_SURFACE_BLOCKED
	EndIf
        If $bShopWindow Then
                $sReason = "shop surface recognized"
                Return $NO_PREMIUM_SURFACE_BLOCKED
        EndIf
	; Negative legacy anchors are never sufficient. The exact action, exact target point, and
	; its reviewed current-client framebuffer predicate must all agree on this fresh frame.
	If Not NoPremiumPermitTargetValid($sPermitAction, $iExpectedX, $iExpectedY) Then
		$sReason = "no exact reviewed action and target permit"
		Return $NO_PREMIUM_SURFACE_UNKNOWN
	EndIf
	Local $bRouteReady = False
	Switch StringLower(String($sPermitAction))
		Case $NO_PREMIUM_ACTION_COLLECTOR_GOLD
			$bRouteReady = OpenHomeCollectorTargetReady(1, Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_COLLECTOR_ELIXIR
			$bRouteReady = OpenHomeCollectorTargetReady(2, Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_COLLECTOR_DARK
			$bRouteReady = OpenHomeCollectorTargetReady(3, Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_LOOT_CART_OPEN
			$bRouteReady = OpenHomeLootCartOpenPointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_LOOT_CART_COLLECT
			$bRouteReady = OpenHomeLootCartCollectPointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_DAILY_REWARD_CLAIM
			$bRouteReady = OpenHomeDailyRewardClaimPointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_DAILY_REWARD_CLOSE
			$bRouteReady = OpenHomeDailyRewardClosePointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_RECOVERY_RELOAD_GAME
			$bRouteReady = OpenHomeInactivityReloadPointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_TREASURY_CASTLE
			$bRouteReady = OpenHomeTreasuryCastlePointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_TREASURY_ENTRY
			$bRouteReady = OpenHomeTreasuryEntryPointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_TREASURY_CLOSE
			$bRouteReady = OpenHomeTreasuryClosePointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_CLAN_REQUEST_ARMY
			$bRouteReady = OpenClanRequestArmyOverviewPointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_EXACT_TRAINING_ARMY
			$bRouteReady = OpenClanRequestArmyOverviewPointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_CLAN_REQUEST_REQUEST
			$bRouteReady = OpenClanRequestRequestPointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_CLAN_REQUEST_SEND
			$bRouteReady = OpenClanRequestSendPointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_CLAN_REQUEST_CANCEL
			$bRouteReady = OpenClanRequestCancelPointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_CLAN_REQUEST_CLOSE
			$bRouteReady = OpenClanRequestClosePointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_BUILDER_SWITCH
			$bRouteReady = OpenBuilderBaseHomeBoatPointReady(Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_BUILDER_COLLECT_GOLD
			$bRouteReady = OpenBuilderBaseResourceTargetReady(1, Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_BUILDER_COLLECT_ELIXIR
			$bRouteReady = OpenBuilderBaseResourceTargetReady(2, Int($iExpectedX), Int($iExpectedY))
		Case $NO_PREMIUM_ACTION_BUILDER_RETURN_HOME
			$bRouteReady = OpenBuilderBaseReturnBoatPointReady(Int($iExpectedX), Int($iExpectedY))
	EndSwitch
	If $bRouteReady Then Return $NO_PREMIUM_SURFACE_SAFE
	$sReason = "positive current-client surface was not recognized for action " & $sPermitAction
	Return $NO_PREMIUM_SURFACE_UNKNOWN
EndFunc   ;==>NoPremiumSurfaceState

Func NoPremiumClearInputPermit()
	$g_sNoPremiumInputPermitAction = ""
	$g_iNoPremiumInputPermitX = -1
	$g_iNoPremiumInputPermitY = -1
	$g_hNoPremiumInputPermitTimer = 0
EndFunc   ;==>NoPremiumClearInputPermit

; A reviewed route calls this immediately after its own positive, current-client recognition.
; The gate captures and validates the same allowlisted surface again, and consumes the one-shot
; permit before returning to the transport. No profile/config value can mint a permit.
Func NoPremiumGrantInputPermit($sAction, $iExpectedX, $iExpectedY)
	; A failed mint must never leave an older permit available to another transport.
	NoPremiumClearInputPermit()
	If TestCapture() Then Return False
	If Not $NO_PREMIUM_POLICY_ENABLED Or $g_bNoPremiumPolicyTripped Then Return SetError(7, 1, False)
	If Not NoPremiumPermitActionKnown($sAction) Or Not NoPremiumPermitTargetValid($sAction, $iExpectedX, $iExpectedY) Then _
		Return NoPremiumActionBlocked("unreviewed premium-safety action or target requested: " & $sAction)
	Local $hCaptured = OpenHomeCollectorsCapture()
	Local $sReason = ""
	If $hCaptured = 0 Or $g_hBitmap = 0 Then _
		Return NoPremiumActionBlocked("positive current-client capture failed for action " & $sAction)
	If NoPremiumSurfaceState($sReason, $sAction, $iExpectedX, $iExpectedY) <> $NO_PREMIUM_SURFACE_SAFE Then _
		Return NoPremiumActionBlocked($sReason)
	$g_sNoPremiumInputPermitAction = StringLower(String($sAction))
	$g_iNoPremiumInputPermitX = Int($iExpectedX)
	$g_iNoPremiumInputPermitY = Int($iExpectedY)
	$g_hNoPremiumInputPermitTimer = TimerInit()
	Return True
EndFunc   ;==>NoPremiumGrantInputPermit

; Latch a terminal receipt before returning to the caller. There is intentionally no cleanup click:
; the main Stop lifecycle owns process/config restoration after all further game input is disabled.
Func NoPremiumActionBlocked($sReason)
        Local $sMessage = "Premium input blocked; input_issued=false; " & String($sReason)
	NoPremiumClearInputPermit()
	If Not $g_bNoPremiumPolicyTripped Then
		$g_bNoPremiumPolicyTripped = True
		SetLog($sMessage, $COLOR_ERROR)
		RunEventLogWrite("safety.premium-blocked", "error", $sMessage, "", $RUN_VERIFICATION_DIAGNOSTIC)
		Assign("g_sRunExecutionMessage", $sMessage, $ASSIGN_FORCEGLOBAL)
		RunControlReportRunFailure($sMessage)
		Assign("g_bRunControlStopRequested", True, $ASSIGN_FORCEGLOBAL)
		$g_bRunState = False
		$g_iBotAction = $eBotStop
		RunControlWriteStatus(True)
	EndIf
	Return SetError(7, 0, False)
EndFunc   ;==>NoPremiumActionBlocked

; Lowest-level pre-input gate shared by the window-control and ADB click transports. A fresh frame is
; mandatory. The recursion latch converts any capture-time attempt to issue input into a terminal
; unknown-recognition failure instead of permitting a nested bypass.
Func NoPremiumPreInputGate($sTransport, $iActualX = Default, $iActualY = Default)
        If Not $NO_PREMIUM_POLICY_ENABLED Then Return NoPremiumActionBlocked("source policy invariant is unavailable")
        If $g_bNoPremiumPolicyTripped Then Return SetError(7, 1, False)
	Local $sPermitAction = $g_sNoPremiumInputPermitAction
	Local $iExpectedX = $g_iNoPremiumInputPermitX
	Local $iExpectedY = $g_iNoPremiumInputPermitY
	Local $hPermitTimer = $g_hNoPremiumInputPermitTimer
	If $sPermitAction = "" Or $hPermitTimer = 0 Then Return NoPremiumActionBlocked("no exact reviewed action permit before " & $sTransport & " input")
	If StringLower(String($sTransport)) <> "window-control" And StringLower(String($sTransport)) <> "adb-minitouch-click" Then _
		Return NoPremiumActionBlocked("point permit cannot authorize " & $sTransport & " input")
	If Not NoPremiumPermitAgeValid(TimerDiff($hPermitTimer)) Then _
		Return NoPremiumActionBlocked("reviewed action permit expired before " & $sTransport & " input")
	If Not NoPremiumPermitPointMatches($iExpectedX, $iExpectedY, $iActualX, $iActualY) Then _
		Return NoPremiumActionBlocked("reviewed action target changed before " & $sTransport & " input")
        Static $bEvaluating = False
	If $bEvaluating Then Return NoPremiumActionBlocked("premium-surface recognition re-entered through " & $sTransport)
	; Consume before the second capture. Capture-time re-entry, retry, reuse, and every
	; multi-egress helper therefore encounter an empty permit and terminate fail closed.
	NoPremiumClearInputPermit()
	$bEvaluating = True
	Local $hCaptured = OpenHomeCollectorsCapture()
	Local $sReason = ""
	Local $iState = $NO_PREMIUM_SURFACE_UNKNOWN
	If $hCaptured <> 0 And $g_hBitmap <> 0 And NoPremiumPermitAgeValid(TimerDiff($hPermitTimer)) Then _
		$iState = NoPremiumSurfaceState($sReason, $sPermitAction, $iExpectedX, $iExpectedY)
	$bEvaluating = False
	If $g_bNoPremiumPolicyTripped Then Return SetError(7, 2, False)
	If $hCaptured = 0 Or $g_hBitmap = 0 Then _
		Return NoPremiumActionBlocked("premium-surface capture failed before " & $sTransport & " input")
	If Not NoPremiumPermitAgeValid(TimerDiff($hPermitTimer)) Then _
		Return NoPremiumActionBlocked("reviewed action permit expired during final recognition before " & $sTransport & " input")
	If $iState <> $NO_PREMIUM_SURFACE_SAFE Then Return NoPremiumActionBlocked($sReason & " before " & $sTransport & " input")
	Return True
EndFunc   ;==>NoPremiumPreInputGate

; Reviewed one-point routes use this instead of Click(). Pacing occurs before either
; recognition capture, while randomization and legacy problem-cleanup callbacks are absent.
; The permit is minted once, consumed once at the selected low-level transport, and cleared
; again on every return path in case the transport failed before reaching its gate.
Func NoPremiumPointClick($sAction, $iX, $iY, $iSpeed = 120, $sDebugText = "", $bForceControl = False)
	If TestCapture() Then Return False
	If Not NoPremiumPermitActionKnown($sAction) Or Not NoPremiumPermitTargetValid($sAction, $iX, $iY) Then _
		Return NoPremiumActionBlocked("unreviewed point-click action or target requested: " & $sAction)
	If RunPacingGateAction() Then Return False
	If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, 0, False)
	Local $bIssued = False, $iIssueError = 0, $iIssueExtended = 0
	If $g_bAndroidAdbClick = True And Not $bForceControl Then
		If Not NoPremiumGrantInputPermit($sAction, $iX, $iY) Then Return False
		If RunControlStopRequested() Or Not $g_bRunState Then
			NoPremiumClearInputPermit()
			Return SetError(2, 0, False)
		EndIf
		$bIssued = AndroidClick(Int($iX), Int($iY), 1, $iSpeed, False)
		$iIssueError = @error
		$iIssueExtended = @extended
	Else
		Local $iSuspendMode = ResumeAndroid()
		MoveMouseOutBS()
		If Not NoPremiumGrantInputPermit($sAction, $iX, $iY) Then
			SuspendAndroid($iSuspendMode)
			Return False
		EndIf
		If RunControlStopRequested() Or Not $g_bRunState Then
			NoPremiumClearInputPermit()
			SuspendAndroid($iSuspendMode)
			Return SetError(2, 0, False)
		EndIf
		$bIssued = (_ControlClick(Int($iX), Int($iY)) <> 0)
		$iIssueError = @error
		$iIssueExtended = @extended
		SuspendAndroid($iSuspendMode)
	EndIf
	NoPremiumClearInputPermit()
	If $g_bDebugClick Then SetDebugLog("Reviewed point click " & $sAction & " at " & Int($iX) & "," & Int($iY) & " " & $sDebugText)
	RunPacingSettle()
	Return SetError($iIssueError, $iIssueExtended, $bIssued)
EndFunc   ;==>NoPremiumPointClick

Func Click($x, $y, $times = 1, $speed = 120, $debugtxt = "", $bForceControl = False)
	Local $txt = "", $aPrevCoor[2] = [$x, $y], $bIssued = False
	If $g_bUseRandomClick Then
		$x = Random($x - 5, $x + 5, 1)
		$y = Random($y - 5, $y + 5, 1)
		$speed = Random($speed - $speed * 0.15, $speed + $speed * 0.15, 1)
		If $g_bDebugClick Then
			$txt = _DecodeDebug($debugtxt)
			SetLog("Random Click X: " & $aPrevCoor[0] & " To " & $x & ", Y: " & $aPrevCoor[1] & " To " & $y & ", Times: " & $times & ", Speed: " & $speed & " " & $debugtxt & $txt, $COLOR_ACTION, "Verdana", "7.5", 0)
		EndIf
	Else
		If $g_bDebugClick Or TestCapture() Then
			$txt = _DecodeDebug($debugtxt)
			SetLog("Click " & $x & "," & $y & "," & $times & "," & $speed & " " & $debugtxt & $txt, $COLOR_ACTION, "Verdana", "7.5", 0)
		EndIf
	EndIf

        If TestCapture() Then Return False
	If $times < 1 Then Return False
	If $times > 1 Then Return NoPremiumActionBlocked("multi-click window/ADB request requires one positive route permit per egress")

	; Holds this action back until the run's configured gap has passed. Returns immediately when no run has installed
	; pacing, which is every bot that has not started a plan, so the untouched path costs one IsObj.
	;
	; Only Click() is gated, not PureClick or PureClickTrain: those drive troop training in tight loops that already
	; space themselves with their own speed argument, and a second delay on top would double-space something tuned.
	If RunPacingGateAction() Then Return False

	If $g_bAndroidAdbClick = True And Not $bForceControl Then
		Local $bAndroidIssued = AndroidClick($x, $y, $times, $speed)
		Local $iAndroidError = @error, $iAndroidExtended = @extended
		RunPacingSettle()
		Return SetError($iAndroidError, $iAndroidExtended, $bAndroidIssued = True)
	EndIf

	Local $SuspendMode = ResumeAndroid()
	If $times <> 1 Then
		For $i = 0 To ($times - 1)
			If isProblemAffectBeforeClick($i) Then
				If $g_bDebugClick Then SetLog("VOIDED Click " & $x & "," & $y & "," & $times & "," & $speed & " " & $debugtxt & $txt, $COLOR_ERROR, "Verdana", "7.5", 0)
				checkMainScreen(False)
				SuspendAndroid($SuspendMode)
				Return $bIssued ; if need to clear screen do not click
			EndIf
			MoveMouseOutBS()
			If _ControlClick($x, $y) Then $bIssued = True
			If _Sleep($speed, False) Then ExitLoop
		Next
	Else
		If isProblemAffectBeforeClick() Then
			If $g_bDebugClick Then SetLog("VOIDED Click " & $x & "," & $y & "," & $times & "," & $speed & " " & $debugtxt & $txt, $COLOR_ERROR, "Verdana", "7.5", 0)
			checkMainScreen(False)
			SuspendAndroid($SuspendMode)
			Return False ; if need to clear screen do not click
		EndIf
		MoveMouseOutBS()
		$bIssued = (_ControlClick($x, $y) <> 0)
	EndIf
	SuspendAndroid($SuspendMode)
	RunPacingSettle()
	Return $bIssued
EndFunc   ;==>Click

Func _ControlClick($x, $y)
	If TestCapture() Then Return False
	Local $bPremiumReady = NoPremiumPreInputGate("window-control", $x, $y)
	Local $iPremiumError = @error, $iPremiumExtended = @extended
	If Not $bPremiumReady Then Return SetError($iPremiumError, $iPremiumExtended, 0)
	;Local $hWin = ($g_bAndroidEmbedded = False ? $g_hAndroidWindow : $g_aiAndroidEmbeddedCtrlTarget[1])
	Local $useHWnD = $g_iAndroidControlClickWindow = 1 And $g_bAndroidEmbedded = False
	Local $hWin = (($useHWnD) ? ($g_hAndroidWindow) : ($g_hAndroidControl))
	$x = Int($x) + $g_aiMouseOffset[0]
	$y = Int($y) + $g_aiMouseOffset[1]
	If $g_bAndroidEmbedded = False Then
		; special fix for incorrect mouse offset in Android Window (undocked)
		$x += $g_aiMouseOffsetWindowOnly[0]
		$y += $g_aiMouseOffsetWindowOnly[1]
	EndIf
	If $hWin = $g_hAndroidWindow Then
		$x += $g_aiBSrpos[0]
		$y += $g_aiBSrpos[1]
	EndIf
	If $g_iAndroidControlClickMode = 0 Then
		Return ControlClick($hWin, "", "", "left", "1", $x, $y)
	EndIf
	Local $WM_LBUTTONDOWN = 0x0201, $WM_LBUTTONUP = 0x0202
	Local $lParam = BitOR(Int($y) * 0x10000, BitAND(Int($x), 0xFFFF)) ; HiWord = y-coordinate, LoWord = x-coordinate
	; _WinAPI_PostMessage or _SendMessage
	_SendMessage($hWin, $WM_LBUTTONDOWN, 0x0001, $lParam)
	_SleepMicro(GetClickDownDelay() * 1000)
	_SendMessage($hWin, $WM_LBUTTONUP, 0x0000, $lParam)
	_SleepMicro(GetClickUpDelay() * 1000)
	Return 1
EndFunc   ;==>_ControlClick

Func isProblemAffectBeforeClick($iCount = 0)
	If NeedCaptureRegion($iCount) = True Then Return isProblemAffect(True)
	Return False
EndFunc   ;==>isProblemAffectBeforeClick

; ClickP : takes an array[2] (or array[4]) as a parameter [x,y]
Func ClickP($point, $howMuch = 1, $speed = 120, $debugtxt = "")
	If $speed = 0 Then $speed = 120
	Click($point[0], $point[1], $howMuch, $speed, $debugtxt)
EndFunc   ;==>ClickP

Func BuildingClick($x, $y, $debugtxt = "")
	Local $point[2] = [$x, $y]
	ConvertToVillagePos($x, $y)
	If $g_bDebugClick Then
		Local $txt = _DecodeDebug($debugtxt)
		SetLog("BuildingClick " & $point[0] & "," & $point[1] & " converted to " & $x & "," & $y & " " & $debugtxt & $txt, $COLOR_ACTION)
	EndIf
	Return Click($x, $y, 1, 0, $debugtxt)
EndFunc   ;==>BuildingClick

Func BuildingClickP($point, $debugtxt = "")
	Return BuildingClick($point[0], $point[1], $debugtxt)
EndFunc   ;==>BuildingClickP

Func PureClick($x, $y, $times = 1, $speed = 120, $debugtxt = "")
	Local $txt = "", $aPrevCoor[2] = [$x, $y]
	If $g_bUseRandomClick Then
		$x = Random($x - 5, $x + 5, 1)
		$y = Random($y - 5, $y + 5, 1)
		$speed = Random($speed - $speed * 0.15, $speed + $speed * 0.15, 1)
		If $g_bDebugClick Then
			$txt = _DecodeDebug($debugtxt)
			SetLog("Random PureClick X: " & $aPrevCoor[0] & " To " & $x & ", Y: " & $aPrevCoor[1] & " To " & $y & ", Times: " & $times & ", Speed: " & $speed & " " & $debugtxt & $txt, $COLOR_ACTION, "Verdana", "7.5", 0)
		EndIf
	Else
		If $g_bDebugClick Then
			$txt = _DecodeDebug($debugtxt)
			SetLog("PureClick " & $x & "," & $y & "," & $times & "," & $speed & " " & $debugtxt & $txt, $COLOR_ACTION, "Verdana", "7.5", 0)
		EndIf
	EndIf

        If TestCapture() Then Return
	If $times < 1 Then Return False
	If $times > 1 Then Return NoPremiumActionBlocked("multi-click PureClick request requires one positive route permit per egress")

	If $g_bAndroidAdbClick = True Then
		For $i = 1 To $times
			AndroidClick($x, $y, 1, $speed, False)
		Next
		Return
	EndIf

	Local $SuspendMode = ResumeAndroid()
	If $times <> 1 Then
		For $i = 0 To ($times - 1)
			MoveMouseOutBS()
			_ControlClick($x, $y)
			If _Sleep($speed, False) Then ExitLoop
		Next
	Else
		MoveMouseOutBS()
		_ControlClick($x, $y)
	EndIf
	SuspendAndroid($SuspendMode)
EndFunc   ;==>PureClick

; PureClickP : takes an array[2] (or array[4]) as a parameter [x,y]
Func PureClickP($point, $howMuch = 1, $speed = 120, $debugtxt = "")
	If $speed = 0 Then $speed = 120
	PureClick($point[0], $point[1], $howMuch, $speed, $debugtxt)
EndFunc   ;==>PureClickP

Func PureClickTrain($x, $y, $times = 1, $speed = 165, $debugtxt = "")
	Local $txt = "", $aPrevCoor[2] = [$x, $y]
	If $g_bUseRandomClick Then
		$x = Random($x - 5, $x + 5, 1)
		$y = Random($y - 5, $y + 5, 1)
		If $g_bDebugClick Then
			$txt = _DecodeDebug($debugtxt)
			SetLog("Random PureClickTrain X: " & $aPrevCoor[0] & " To " & $x & ", Y: " & $aPrevCoor[1] & " To " & $y & ", Times: " & $times & ", Speed: " & $speed & " " & $debugtxt & $txt, $COLOR_ACTION, "Verdana", "7.5", 0)
		EndIf
	Else
		If $g_bDebugClick Then
			$txt = _DecodeDebug($debugtxt)
			SetLog("PureClickTrain " & $x & "," & $y & "," & $times & "," & $speed & " " & $debugtxt & $txt, $COLOR_ACTION, "Verdana", "7.5", 0)
		EndIf
	EndIf

        If TestCapture() Then Return
	If $times < 1 Then Return False
	If $times > 1 Then Return NoPremiumActionBlocked("multi-click training request requires one positive route permit per egress")

	If $g_bAndroidAdbClick = True Then
		For $i = 1 To $times
			AndroidClick($x, $y, 1, $speed, False)
		Next
		Return
	EndIf

	Local $SuspendMode = ResumeAndroid()
	If $times <> 1 Then
		For $i = 0 To ($times - 1)
			MoveMouseOutBS()
			_ControlClick($x, $y)
			If _Sleep($speed, False) Then ExitLoop
		Next
	Else
		MoveMouseOutBS()
		_ControlClick($x, $y)
	EndIf
	SuspendAndroid($SuspendMode)
EndFunc   ;==>PureClickTrain

Func GemClick($x, $y, $times = 1, $speed = 120, $debugtxt = "")
	If TestCapture() Then Return False
	Return NoPremiumActionBlocked("GemClick is permanently unavailable")
EndFunc   ;==>GemClick

; GemClickP : takes an array[2] (or array[4]) as a parameter [x,y]
Func GemClickP($point, $howMuch = 1, $speed = 120, $debugtxt = "")
	If $speed = 0 Then $speed = 120
	Return GemClick($point[0], $point[1], $howMuch, $speed, $debugtxt = "")
EndFunc   ;==>GemClickP

Func AttackClick($x, $y, $times = 1, $speed = 120, $afterDelay = 0, $debugtxt = "")
	If $speed = 0 Then $speed = 120
	$speed = Random($speed - $speed * 0.1, $speed + $speed * 0.1, 1)
	Local $timer = __TimerInit()
	; Protect the Attack Bar
	If $y > 555 + $g_iBottomOffsetY Then $y = 555 + $g_iBottomOffsetY
	AttackRemainingTime(False) ; flag attack started
	Local $result = PureClick($x, $y, $times, $speed, $debugtxt)
	Local $delay = $times * $speed + $afterDelay - __TimerDiff($timer)
	If IsKeepClicksActive() = False And $delay > 0 Then _Sleep($delay, False)
	Return $result
EndFunc   ;==>AttackClick

Func AttackClickCSV($x, $y, $times = 1, $speed = 120, $afterDelay = 0, $debugtxt = "")
	If $speed = 0 Then $speed = 120
	Local $timer = __TimerInit()
	; Protect the Attack Bar
	If $y > 555 + $g_iBottomOffsetY Then
		$y = Random(553, 555, 1) + $g_iBottomOffsetY
		If $x > ($g_iGAME_WIDTH / 2) Then
			$x = Random(($g_iGAME_WIDTH / 2) + 60, ($g_iGAME_WIDTH / 2) + 100, 1)
		Else
			$x = Random(($g_iGAME_WIDTH / 2) - 100, ($g_iGAME_WIDTH / 2) - 60, 1)
		EndIf
	EndIf
	AttackRemainingTime(False) ; flag attack started
	Local $result = PureClickTrain($x, $y, $times, $speed, $debugtxt)
	Local $delay = $times * $speed + $afterDelay - __TimerDiff($timer)
	If IsKeepClicksActive() = False And $delay > 0 Then _Sleep($delay, False)
	Return $result
EndFunc   ;==>AttackClickCSV

Func ClickAway($Region = Default )
	Local $aiRegionToUse = Random(0, 1, 1) > 0 ? $aiClickAwayRegionLeft : $aiClickAwayRegionRight
	If $Region = "Left" Then
		$aiRegionToUse = $aiClickAwayRegionLeft
	ElseIf $Region = "Right" Then
		$aiRegionToUse = $aiClickAwayRegionRight
	EndIf

	Local $aiSpot[2] = [Random($aiRegionToUse[0], $aiRegionToUse[2], 1), Random($aiRegionToUse[1], $aiRegionToUse[3], 1)]
	If $g_bDebugClick Then SetDebugLog("ClickAway(): on X:" & $aiSpot[0] & ", Y:" & $aiSpot[1], $COLOR_DEBUG)
	ClickP($aiSpot, 1, 180, "#0000")
EndFunc   ;==>ClickAway

Func ClickAway2()
	Local $aiRegionToUse = Random(0, 1, 1) > 0 ? $aiClickAwayRegionLeft2 : $aiClickAwayRegionRight2
	Local $aiSpot[2] = [Random($aiRegionToUse[0], $aiRegionToUse[2], 1), Random($aiRegionToUse[1], $aiRegionToUse[3], 1)]
	If $g_bDebugClick Then SetDebugLog("ClickAway2(): on X:" & $aiSpot[0] & ", Y:" & $aiSpot[1], $COLOR_DEBUG)
	ClickP($aiSpot, 1, 180, "#0000")
EndFunc   ;==>ClickAway2

Func _DecodeDebug($message)
	Local $separator = " | "
	Switch $message
		; AWAY CLICKS
		Case "#0000"
			Return $separator & "Away"
		Case "#0214", "#0215", "#0216", "#0217", "#0218", "#0219", "#0220", "#0221", "#0235", "#0242", "#0268", "#0291", "#0292", "#0295", "#0298", "#0300", "#0301", "#0302"
			Return $separator & "Away"
		Case "#0303", "#0306", "#0308", "#0309", "#0310", "#0311", "#0312", "#0319", "#0333", "#0257", "#0139", "#0125", "#0251", "#0335", "#0313", "#0314", "#0332", "#0329"
			Return $separator & "Away"
		Case "#0121", "#0124", "#0133", "#0157", "#0161", "#0165", "#0166", "#0167", "#0170", "#0171", "#0176", "#0224", "#0234", "#0265", "#0346", "#0348", "#0350", "#0351"
			Return $separator & "Away"
		Case "#0352", "#0353", "#0354", "#0355", "#0356", "#0357", "#0358", "#0359", "#0360", "#0361", "#0362", "#0363", "#0364", "#0365", "#0366", "#0367", "#0368", "#0369"
			Return $separator & "Away"
		Case "#0370", "#0371", "#0373", "#0374", "#0375", "#0376", "#0377", "#0378", "#0379", "#0380", "#0381", "#0382", "#0383", "#0384", "#0385", "#0386", "#0387", "#0388"
			Return $separator & "Away"
		Case "#0389", "#0390", "#0391", "#0392", "#0393", "#0394", "#0395", "#0501", "#0502", "#0503", "#0504", "#0467", "#0505", "#0931", "#0932", "#0933"
			Return $separator & "Away"
			; ATTACK TH
		Case "#0001"
			Return $separator & "AtkTH - Select Barbarian"
		Case "#0002", "#0006"
			Return $separator & "AtkTH - Barbarian Bottom Left"
		Case "#0003", "#0007"
			Return $separator & "AtkTH - Barbarian Bottom Right"
		Case "#0004", "#0008"
			Return $separator & "AtkTH - Barbarian Top Right"
		Case "#0005", "#0009"
			Return $separator & "AtkTH - Barbarian Top Left"
		Case "#0010"
			Return $separator & "AtkTH - Select Archer"
		Case "#0011", "#0015"
			Return $separator & "AtkTH - Arcer Bottom Left"
		Case "#0012", "#0016"
			Return $separator & "AtkTH - Arcer Bottom Right"
		Case "#0013", "#0017"
			Return $separator & "AtkTH - Arcer Top Right"
		Case "#0014", "#0018"
			Return $separator & "AtkTH - Arcer Top Left"
		Case "#0155"
			Return $separator & "Attack - Next Button"
			;COLLECT
		Case "#0331"
			Return $separator & "Collect resources"
		Case "#0330"
			Return $separator & "Collect resources*"
		Case "#0432"
			Return $separator & "Clean tombs*"
		Case "#0431"
			Return $separator & "Clean yard"
		Case "#0430"
			Return $separator & "Clean yard*"
		Case "#0433"
			Return $separator & "Continue"
			;TRAIN
		Case "#0266"
			Return $separator & "Train - TrainIT Selected Troop"
		Case "#0269"
			Return $separator & "Train - Open Barrack"
		Case "#0270"
			Return $separator & "Train - Train Troops button"
		Case "#0271"
			Return $separator & "Train - Next Button "
		Case "#0272", "#0286", "#0289", "#0325"
			Return $separator & "Train - Prev Button "
		Case "#0273", "#0284", "#0285", "#0287", "#0288"
			Return $separator & "Train - Remove Troops"
		Case "#0274"
			Return $separator & "Train - Train Barbarian"
		Case "#0275"
			Return $separator & "Train - Train Archer"
		Case "#0276"
			Return $separator & "Train - Train Giant"
		Case "#0277"
			Return $separator & "Train - Train Goblin"
		Case "#0278"
			Return $separator & "Train - Train Wall Breaker"
		Case "#0279"
			Return $separator & "Train - Train Balloon"
		Case "#0280"
			Return $separator & "Train - Train Wizard"
		Case "#0281"
			Return $separator & "Train - Train Healer"
		Case "#0282"
			Return $separator & "Train - Train Dragon"
		Case "#0283"
			Return $separator & "Train - Train P.E.K.K.A."
		Case "#0290"
			Return $separator & "Train - GemClick Spell"
		Case "#0293"
			Return $separator & "Train - Click Army Camp"
		Case "#0294"
			Return $separator & "Train - Open Info Army Camp"
		Case "#0336"
			Return $separator & "Train - Go to first barrack"
		Case "#0337"
			Return $separator & "Train - Click Prev Button*"
		Case "#0338"
			Return $separator & "Train - Click Next Button*"
		Case "#0339"
			Return $separator & "Train - Select Prev Barrack/SP"
		Case "#0340"
			Return $separator & "Train - Click Next Barrack/SP"
		Case "#0341"
			Return $separator & "Train - Train Bowler"
		Case "#0342"
			Return $separator & "Train - Train Baby Dragon"
		Case "#0343"
			Return $separator & "Train - Train Miner"
		Case "#0344"
			Return $separator & "Train - Train Super Miner"
		Case "#0345"
			Return $separator & "Train - Train Ice Golem"
		Case "#0346"
			Return $separator & "Train - Train Yeti"
		Case "#0347"
			Return $separator & "Train - Train Dragon Rider"
		Case "#0348"
			Return $separator & "Train - Train Rocket Ballon"
		Case "#0350"
			Return $separator & "Train - Train Super Bowler"

			;DONATE
		Case "#0168"
			Return $separator & "Donate - Open Chat"
		Case "#0169"
			Return $separator & "Donate - Select Clan Tab"
		Case "#0172"
			Return $separator & "Donate - Scroll"
		Case "#0173"
			Return $separator & "Donate - Click Chat"
		Case "#0174"
			Return $separator & "Donate - Click Donate Button"
		Case "#0175"
			Return $separator & "Donate - Donate Selected Troop first row"
		Case "#0600"
			Return $separator & "Donate - Donate Selected Troop second row"
		Case "#0601"
			Return $separator & "Donate - Donate Selected Troop spell"
			;TEST LANGUAGE
		Case "#0144"
			Return $separator & "ChkLang - Config Button"
		Case "#0145", "#0146", "#0147", "#0148"
			Return $separator & "ChkLang - Close Page"
			;PROFILE REPORT
		Case "#0222"
			Return $separator & "Profile - Profile Button"
		Case "#0223"
			Return $separator & "Profile - Close Page"
			;REQUEST CC
		Case "#0250"
			Return $separator & "Request - Click Castle Clan"
		Case "#0253"
			Return $separator & "Request - Click Request Button"
		Case "#0254", "#0255"
			Return $separator & "Request - Click Select Text For Request"
		Case "#0256"
			Return $separator & "Request - Click Send Request"
		Case "#0334"
			Return $separator & "Request - Click Train Button"
			;RETURN HOME
		Case "#0099"
			Return $separator & "Return Home - End Battle"
		Case "#0100"
			Return $separator & "Return Home - Surrender, Confirm"
		Case "#0101"
			Return $separator & "Return Home - Return Home Button"
		Case "#0396"
			Return $separator & "Reach Limit - Return home, Press End Battle "
			;DETECT CLAN LEVEL
		Case "#0468"
			Return $separator & "Clan Level - Open Chat"
		Case "#0469"
			Return $separator & "Clan Level - Open Chat Clan Tab "
		Case "#0470"
			Return $separator & "Clan Level - Click Info Clan Button"
		Case "#071", "#0472"
			Return $separator & "Clan Level - Close Chat"
		Case "#0473"
			Return $separator & "Clan Level - Close Clan Info Page"

		Case "#0149"
			Return $separator & "Prepare Search - Press Attack Button"
		Case "#0150"
			Return $separator & "Prepare Search - Press Find a Match Button"

			;AllTroops
		Case "#0030"
			Return $separator & "Attack - press surrender"
		Case "#0031"
			Return $separator & "Attack - press confirm surrender"

		Case "#0510"
			Return $separator & "Attack Search - Open chat tab"
		Case "#0511"
			Return $separator & "Attack Search - close chat tab"
		Case "#0512"
			Return $separator & "Attack Search - Press retry search button"
		Case "#0513"
			Return $separator & "Attack Search - Return Home button"
		Case "#0514"
			Return $separator & "Attack Search - Clouds, keep game alive"

			;Personal Challenges
		Case "#0666"
			Return $separator & "Personal Challenges - Open button"
		Case "#0667"
			Return $separator & "Personal Challenges - Close button"

		Case "#0000"
			Return $separator & " "

		Case Else
			Return ""
	EndSwitch
EndFunc   ;==>_DecodeDebug

Func SendText($sText)
        Local $result = 1
	Local $error = 0
	If $g_bAndroidAdbInput = True Then
		AndroidSendText($sText)
		$error = @error
        EndIf
        If $g_bAndroidAdbInput = False Or $error <> 0 Then
		If TestCapture() Then Return 0
		Local $bPremiumReady = NoPremiumPreInputGate("window-text")
		Local $iPremiumError = @error, $iPremiumExtended = @extended
		If Not $bPremiumReady Then Return SetError($iPremiumError, $iPremiumExtended, 0)
                Local $SuspendMode = ResumeAndroid()
		;$Result = ControlSend($g_hAndroidWindow, "", "", $sText, 0)
		Local $ascText = ""
		Local $r, $i, $vk, $shiftBits, $char
		Local $c = 0
		For $i = 1 To StringLen($sText)
			$char = StringMid($sText, $i, 1)
			$vk = _VkKeyScan($char)
			$shiftBits = @extended
			If $vk = -1 And $shiftBits = -1 Then
				; key not found, skip it
				SetDebugLog("SendText cannot send character: " & $char)
				$c += 1
			Else
				If BitAND($shiftBits, 1) > 0 Then $ascText &= "{LSHIFT down}"
				If BitAND($shiftBits, 2) > 0 Then $ascText &= "{LCTRL down}"
				If BitAND($shiftBits, 4) > 0 Then $ascText &= "{LALT down}"
				$ascText &= "{ASC " & _WinAPI_MapVirtualKey($vk, $MAPVK_VK_TO_CHAR) & "}"
				If BitAND($shiftBits, 4) > 0 Then $ascText &= "{LALT up}"
				If BitAND($shiftBits, 2) > 0 Then $ascText &= "{LCTRL up}"
				If BitAND($shiftBits, 1) > 0 Then $ascText &= "{LSHIFT up}"
				;SetDebugLog("SendText: " & $char & " as " & $ascText)
				$r = ControlSend($g_hAndroidWindow, "", "", $ascText, 0)
				$ascText = ""
				If $r = 1 Then
					;If _Sleep(50) = True Then ExitLoop
					$c += 1
				EndIf
			EndIf
		Next
		$result = 0
		If $c = StringLen($sText) Then $result = 1
		SuspendAndroid($SuspendMode)
	EndIf
	Return $result
EndFunc   ;==>SendText

; return value is VK code
; @extended contains shift state bits:
; 1 = SHIFT key
; 2 = CTRL key
; 4 = ALT key
; Source: https://www.autoitscript.com/forum/topic/138681-user32dllvkkeyscan-not-doing-it-right/?do=findComment&comment=971876
Func _VkKeyScan($s_Char)
	Local $a_Ret = DllCall("user32.dll", "short", "VkKeyScanW", "ushort", AscW($s_Char))
	If @error Then Return SetError(@error, @extended, -1)
	Return SetExtended(BitShift($a_Ret[0], 8), BitAND($a_Ret[0], 0xFF))
EndFunc   ;==>_VkKeyScan

Func GetClickDownDelay()
	Return $g_iAndroidControlClickDownDelay + Int($g_iAndroidControlClickAdditionalDelay / 2)
EndFunc   ;==>GetClickDownDelay

Func GetClickUpDelay()
	Return $g_iAndroidControlClickDelay + Int($g_iAndroidControlClickAdditionalDelay / 2)
EndFunc   ;==>GetClickUpDelay
