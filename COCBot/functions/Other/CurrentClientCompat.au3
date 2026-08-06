; #FUNCTION# ====================================================================================================================
; Name ..........: Current client compatibility registration
; Description ...: Registers current emulator adapters and stable run orchestration modules without changing the legacy core table.
; Remarks .......: This file is part of My Bot and is distributed under the terms of the GNU GPL v3.
; ===============================================================================================================================
#include-once

#include "..\Android\AndroidLDPlayer9.au3"
#include "..\Android\AndroidMumu.au3"
#include "..\Run\RunPlan.au3"
#include "..\Run\AccountQueue.au3"
#include "..\Run\BattleRoute.au3"
#include "..\Run\RunSession.au3"

Global $__LDPlayer9_Idx = -1
Global $__Mumu_Idx = -1

Func _RegisterLDPlayer9Adapter()
	Local $iExisting = _ArraySearch($g_avAndroidAppConfig, "LDPlayer9", 0, 0, 0, 0, 1, 0)
	If $iExisting >= 0 Then Return $iExisting

	Local $iRow = UBound($g_avAndroidAppConfig, 1)
	ReDim $g_avAndroidAppConfig[$iRow + 1][16]
	$g_avAndroidAppConfig[$iRow][0] = "LDPlayer9"
	$g_avAndroidAppConfig[$iRow][1] = "leidian0"
	$g_avAndroidAppConfig[$iRow][2] = "LD9-"
	$g_avAndroidAppConfig[$iRow][3] = "[CLASS:subWin; INSTANCE:1]"
	$g_avAndroidAppConfig[$iRow][4] = "sub"
	$g_avAndroidAppConfig[$iRow][5] = $g_iDEFAULT_WIDTH
	$g_avAndroidAppConfig[$iRow][6] = $g_iDEFAULT_HEIGHT - 48
	$g_avAndroidAppConfig[$iRow][7] = $g_iDEFAULT_WIDTH
	$g_avAndroidAppConfig[$iRow][8] = $g_iDEFAULT_HEIGHT - 48
	$g_avAndroidAppConfig[$iRow][9] = 0
	$g_avAndroidAppConfig[$iRow][10] = "emulator-5554"
	$g_avAndroidAppConfig[$iRow][11] = 1 + 2 + 4 + 8 + 16 + 32 + 128
	$g_avAndroidAppConfig[$iRow][12] = "# "
	$g_avAndroidAppConfig[$iRow][13] = "input"
	$g_avAndroidAppConfig[$iRow][14] = -1
	$g_avAndroidAppConfig[$iRow][15] = 1
	Return $iRow
EndFunc   ;==>_RegisterLDPlayer9Adapter

Func _RegisterMumuAdapter()
	Local $iExisting = _ArraySearch($g_avAndroidAppConfig, "MuMu", 0, 0, 0, 0, 1, 0)
	If $iExisting >= 0 Then Return $iExisting

	Local $iRow = UBound($g_avAndroidAppConfig, 1)
	ReDim $g_avAndroidAppConfig[$iRow + 1][16]
	$g_avAndroidAppConfig[$iRow][0] = "MuMu"
	$g_avAndroidAppConfig[$iRow][1] = "MuMuPlayerGlobal-12.0-0"
	$g_avAndroidAppConfig[$iRow][2] = "MuMu-"
	$g_avAndroidAppConfig[$iRow][3] = "[CLASS:nemuwin; INSTANCE:1]"
	$g_avAndroidAppConfig[$iRow][4] = "nemudisplay"
	$g_avAndroidAppConfig[$iRow][5] = $g_iDEFAULT_WIDTH
	$g_avAndroidAppConfig[$iRow][6] = $g_iDEFAULT_HEIGHT - 48
	$g_avAndroidAppConfig[$iRow][7] = $g_iDEFAULT_WIDTH
	$g_avAndroidAppConfig[$iRow][8] = $g_iDEFAULT_HEIGHT - 48
	$g_avAndroidAppConfig[$iRow][9] = 0
	$g_avAndroidAppConfig[$iRow][10] = "127.0.0.1:5555"
	$g_avAndroidAppConfig[$iRow][11] = 1 + 2 + 4 + 8 + 16 + 32 + 256
	$g_avAndroidAppConfig[$iRow][12] = "# "
	$g_avAndroidAppConfig[$iRow][13] = "Xiaomi Input"
	$g_avAndroidAppConfig[$iRow][14] = -1
	$g_avAndroidAppConfig[$iRow][15] = 1
	Return $iRow
EndFunc   ;==>_RegisterMumuAdapter

Func RegisterCurrentClientCompat()
	$__LDPlayer9_Idx = _RegisterLDPlayer9Adapter()
	$__Mumu_Idx = _RegisterMumuAdapter()
	SetDebugLog("Current client adapters registered: LDPlayer9=" & $__LDPlayer9_Idx & ", MuMu=" & $__Mumu_Idx)
EndFunc   ;==>RegisterCurrentClientCompat

; Keep dynamically dispatched functions available in compiled builds.
Func ReferenceCurrentClientCompat()
	If True Then Return

	GetLDPlayer9ProgramParameter()
	OpenLDPlayer9()
	InitLDPlayer9()
	ConfigureSharedFolderLDPlayer9()
	GetLDPlayer9BackgroundMode()
	CheckScreenLDPlayer9()
	SetScreenLDPlayer9()
	RebootLDPlayer9SetScreen()
	GetLDPlayer9RunningInstance()
	GetLDPlayer9SvcPid()
	CloseLDPlayer9()
	CloseUnsupportedLDPlayer9()
	ZoomOutLDPlayer9()
	LDPlayer9BotStartEvent()
	LDPlayer9BotStopEvent()

	GetMumuProgramParameter()
	OpenMumu()
	InitMumu()
	ConfigureSharedFolderMumu()
	GetMumuBackgroundMode()
	CheckScreenMumu()
	SetScreenMumu()
	RebootMumuSetScreen()
	GetMumuRunningInstance()
	GetMumuSvcPid()
	CloseMumu()
	CloseUnsupportedMumu()
	ZoomOutMumu()
	MumuBotStartEvent()
	MumuBotStopEvent()

	Local $oPlan = RunPlanCreateDefault(), $sPlanError
	RunPlanValidate($oPlan, $sPlanError)
	RunPlanShouldStop($oPlan, 0, 0, 0, False)
	Local $oQueue = AccountQueueCreate()
	AccountQueueAdd($oQueue, "profile", "Profile")
	Local $sProfile, $sName
	AccountQueueNext($oQueue, $sProfile, $sName)

	Local $oRoute = BattleRouteFromRunPlan($oPlan, $sPlanError), $sRouteReason
	BattleRouteSetReadiness($oRoute, False, False, "fixture required")
	BattleRouteCanStart($oRoute, $sRouteReason)
	Local $oSession = RunSessionCreate($oPlan, "reference")
	RunSessionSetAccount($oSession, "profile")
	RunSessionStart($oSession)
	RunSessionRecordBattle($oSession, True, 0, 0, 0)
	RunSessionEvaluateStop($oSession, 0, False)
	RunSessionRequestStop($oSession, "reference")
	RunSessionComplete($oSession)
	RunSessionSnapshot($oSession)
EndFunc   ;==>ReferenceCurrentClientCompat

RegisterCurrentClientCompat()
ReferenceCurrentClientCompat()
