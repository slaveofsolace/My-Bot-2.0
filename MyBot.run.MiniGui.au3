; #FUNCTION# ====================================================================================================================
; Name ..........: MBR Bot
; Description ...: This file contains the initialization and main loop sequences f0r the MBR Bot
; Author ........: cosote (2017)
; Modified ......:
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; Related .......:
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......: No
; ===============================================================================================================================

; AutoIt pragmas
#NoTrayIcon
#AutoIt3Wrapper_UseX64=7n
;#AutoIt3Wrapper_Res_HiDpi=Y ; HiDpi will be set during run-time!
#AutoIt3Wrapper_Run_Au3Stripper=y
#Au3Stripper_Parameters=/rsln /MI=3
;/SV=0
;#pragma compile(Console, true)
#pragma compile(FileDescription, My Bot 2.0 Mini Console)
#pragma compile(ProductVersion, 2.0.0)
#pragma compile(FileVersion, 2.0.0)
#pragma compile(LegalCopyright, My Bot 2.0 contributors - based on MyBot.run)
#include "MyBot.run.version.au3"
#pragma compile(ProductName, My Bot 2.0 Mini Console)
; The shipped MyBot.run.MiniGui.exe is the exact pinned upstream v8.2 controller required by the
; inherited image engine. Local experiments must not overwrite that provenance-locked artifact.
#pragma compile(Out, MyBot.run.MiniGui.dev.exe)

; Enforce variable declarations
Opt("MustDeclareVars", 1)

Global $g_sBotTitle = $g_sProductName & " Mini " & $g_sProductVersion
Global $g_hFrmBot = 0 ; The main GUI window

#include <APIErrorsConstants.au3>
#include <WinAPIProc.au3>
#include <WinAPISys.au3>
#include <Misc.au3>
#include <ColorConstants.au3>
#include <Date.au3>
#include <Array.au3>

#include <WindowsConstants.au3>
#include <StructureConstants.au3>
#include <StaticConstants.au3>
#include <GUIConstantsEx.au3>
#include <GDIPlus.au3>
#include <GuiToolTip.au3>

; Autoit Options
Opt("GUIResizeMode", $GUI_DOCKALL) ; Default resize mode for dock android support
Opt("GUIEventOptions", 1) ; Handle minimize and restore for dock android support
Opt("GUICloseOnESC", 0) ; Don't send the $GUI_EVENT_CLOSE message when ESC is pressed.
Opt("WinTitleMatchMode", 3) ; Window Title exact match mode
Opt("GUIOnEventMode", 1)

Global $hNtDll = DllOpen("ntdll.dll")
#cs
	Global Const $COLOR_ERROR = $COLOR_RED ; Error messages
	Global Const $COLOR_WARNING = $COLOR_MAROON ; Warning messages
	Global Const $COLOR_INFO = $COLOR_BLUE ; Information or Status updates for user
	Global Const $COLOR_SUCCESS = 0x006600 ; Dark Green, Action, method, or process completed successfully
	Global Const $COLOR_DEBUG = $COLOR_PURPLE ; Purple, basic debug color
#ce
; Global Variables
;Global $g_bRunState = True
Global $g_iGlobalActiveBotsAllowed = 0 ; Dummy
Global $g_hMutextOrSemaphoreGlobalActiveBots = 0 ; Dummy
Global $g_hStatusBar = 0 ; Dummy
Global $hMutex_BotTitle = 0 ; Mutex handle for this instance
Global $hStarted = 0 ; Timer handle watchdog started
Global $bCloseWhenAllBotsUnregistered = True ; Automatically close watchdog when all bots closed
Global $iTimeoutBroadcast = 30000 ; Milliseconds of sending broadcast messages to bots
Global $iTimeoutCheckBot = 5000 ; Milliseconds bots are checked if restart required
Global $iTimeoutRestartBot = 120000 ; Milliseconds un-responsive bot is launched again
Global $iTimeoutAutoClose = 60000 ; Milliseconds watchdog automatically closed when no bot available, -1 = disabled
Global $hTimeoutAutoClose = 0 ; Timer Handle for $iTimeoutAutoClose
Global $g_iMainLoopSleep = 50 ;
;Global $g_bBotLaunchOption_NoBotSlot = True

Global $g_hFrmBotBackend = 0
Global $g_bBotLaunched = False
Global $g_iBotBackendFindTimeout = 3000
; The launcher may need up to two seconds to confirm one exact backend generation has exited and
; publish its request-bound Stop receipt. Keep replacement launch outside that terminal-write window.
Global Const $g_iMiniBackendRecoveryDelayMs = 5000
Global $g_hMiniBackendRecoveryTimer = 0
Global $g_bMiniBackendRecoveryActive = False
Global $g_sMiniLifecycleLastState = ""
Global $g_sMiniLifecycleLastReason = ""
Global $g_iMiniLifecycleLastBackendPid = -1

Global $hStruct_SleepMicro = DllStructCreate("int64 time;")
Global $pStruct_SleepMicro = DllStructGetPtr($hStruct_SleepMicro)
Global $DELAYSLEEP = 10
Global $DELAYWINDOWSARRANGE1 = 100
Global $g_iDebugSetLog = 0

Global $g_hFrmBotEmbeddedMouse = 0

; MBR includes
#include "COCBot\MBR Global Variables.au3"
#include "COCBot\functions\Other\ExtendedErrorInfo.au3"
#include "COCBot\functions\Other\MBRFunc.au3"
#include "COCBot\functions\Other\Multilanguage.au3"
#include "COCBot\functions\Other\Base64.au3"
#include "COCBot\functions\Other\Api.au3"
#include "COCBot\functions\Other\ApiHost.au3"
#include "COCBot\functions\Other\LaunchConsole.au3"
#include "COCBot\functions\Other\Time.au3"
#include "COCBot\functions\Other\WindowsArrange.au3"

Global Const $g_sMiniEngineInitCancelSchema = "engine-init-cancel-v1"
Global Const $g_sMiniEngineInitCancelPath = @ScriptDir & "\config\engine-init-cancel.local.json"
Global Const $g_sMiniLifecycleReceiptPath = $g_sMBRFuncRuntimeLocalAppData & "\My Bot 2.0\mini-supervisor-lifecycle-v1.json"
Global Const $g_iMiniEngineInitReceiptMaxBytes = 4096
Global Const $g_iMiniEngineInitCancelMaxBytes = 2048

#include "COCBot\MBR GUI Design Mini.au3"
#include "COCBot\functions\Config\readConfig.au3"
#include "COCBot\functions\Other\UpdateStats.Mini.au3"
#include "COCBot\functions\Other\_NumberFormat.au3"

Global Enum $eBotUpdateStats = $eBotClose + 1

Func SetLog($String, $Color = $COLOR_BLACK, $LogPrefix = "L ")
	Local $log = $LogPrefix & TimeDebug() & $String
	_ConsoleWrite($log & @CRLF) ; Always write any log to console
EndFunc   ;==>SetLog

Func SetDebugLog($String, $Color = $COLOR_DEBUG, $LogPrefix = "D ")
	Return SetLog($String, $Color, $LogPrefix)
EndFunc   ;==>SetDebugLog

Func _Sleep($ms, $iSleep = True, $CheckRunState = True)
	CheckBotRequests() ; check if bot window should be moved, minized etc.
	_SleepMilli($ms)
EndFunc   ;==>_Sleep

Func _SleepMicro($iMicroSec)
	;Local $hStruct_SleepMicro = DllStructCreate("int64 time;")
	;Local $pStruct_SleepMicro = DllStructGetPtr($hStruct_SleepMicro)
	DllStructSetData($hStruct_SleepMicro, "time", $iMicroSec * -10)
	DllCall($hNtDll, "dword", "ZwDelayExecution", "int", 0, "ptr", $pStruct_SleepMicro)
	;$hStruct_SleepMicro = 0
EndFunc   ;==>_SleepMicro

Func UpdateBotTitle($sTitle = $g_sProductName & " " & $g_sProductVersion)
	Local $sMiniPrefix = $g_sProductName & " Mini"
	If StringLeft($sTitle, StringLen($sMiniPrefix)) <> $sMiniPrefix Then
		If StringLeft($sTitle, StringLen($g_sProductName)) = $g_sProductName Then
			$sTitle = $sMiniPrefix & StringTrimLeft($sTitle, StringLen($g_sProductName))
		Else
			$sTitle = $sMiniPrefix & " " & $g_sProductVersion
		EndIf
	EndIf
	If $g_sBotTitle = $sTitle Then Return
	$g_sBotTitle = $sTitle
	If $g_hFrmBot <> 0 Then
		; Update Bot Window Title also
		WinSetTitle($g_hFrmBot, "", $g_sBotTitle)
		GUICtrlSetData($g_hLblBotTitle, $g_sBotTitle)
	EndIf
	; Update Console Window (if it exists)
	DllCall("kernel32.dll", "bool", "SetConsoleTitle", "str", "Console " & $g_sBotTitle)
	; Update try icon title
	TraySetToolTip($g_sBotTitle)
	GUISetIcon($g_sLibIconPath, $eIcnGUI)

	SetDebugLog("Bot title updated to: " & $g_sBotTitle)
EndFunc   ;==>UpdateBotTitle

Func _SleepMilli($iMilliSec)
	_SleepMicro(Int($iMilliSec * 1000))
EndFunc   ;==>_SleepMilli

; added to avoid SciTE warning
Func ResumeAndroid()
EndFunc   ;==>ResumeAndroid


Func ProcessCommandLine()

	; Handle Command Line Launch Options and fill $g_asCmdLine
	If $CmdLine[0] > 0 Then
		SetDebugLog("Full Command Line: " & _ArrayToString($CmdLine, " "))
		For $i = 1 To $CmdLine[0]
			Local $bOptionDetected = True
			Switch $CmdLine[$i]
				; terminate bot if it exists (by window title!)
				Case "/restart", "/r", "-restart", "-r"
					$g_bBotLaunchOption_Restart = True
				Case "/autostart", "/a", "-autostart", "-a"
					$g_bBotLaunchOption_Autostart = True
				Case "/nowatchdog", "/nwd", "-nowatchdog", "-nwd"
					$g_bBotLaunchOption_NoWatchdog = True
				Case "/primarywindow"
					$g_bForcePrimaryWindow = True
				Case "/dpiaware", "/da", "-dpiaware", "-da"
					$g_bBotLaunchOption_ForceDpiAware = True
				Case "/dock1", "/d1", "-dock1", "-d1", "/dock", "/d", "-dock", "-d"
					$g_iBotLaunchOption_Dock = 1
				Case "/dock2", "/d2", "-dock2", "-d2"
					$g_iBotLaunchOption_Dock = 2
				Case "/nobotslot", "/nbs", "-nobotslot", "-nbs"
					$g_bBotLaunchOption_NoBotSlot = True
				Case "/debug", "/debugmode", "/dev", "-debug", "-dev"
					$g_bDevMode = True
				Case "/minigui", "/mg", "-minigui", "-mg"
					$g_iGuiMode = 2
				Case "/nogui", "/ng", "-nogui", "-ng"
					$g_iGuiMode = 0
				Case "/console", "/c", "-console", "-c"
					_WinAPI_AllocConsole()
					_WinAPI_SetConsoleIcon($g_sLibIconPath, $eIcnGUI)
				Case Else
					If StringInStr($CmdLine[$i], "/guipid=") Then
						Local $guidpid = Int(StringMid($CmdLine[$i], 9))
						If ProcessExists($guidpid) Then
							$g_iGuiPID = $guidpid
						Else
							SetDebugLog("GUI Process doesn't exist: " & $guidpid)
						EndIf
					Else
						$bOptionDetected = False
						$g_asCmdLine[0] += 1
						ReDim $g_asCmdLine[$g_asCmdLine[0] + 1]
						$g_asCmdLine[$g_asCmdLine[0]] = $CmdLine[$i]
					EndIf
			EndSwitch
			If $bOptionDetected Then SetDebugLog("Command Line Option detected: " & $CmdLine[$i])
		Next
	EndIf

	; Handle Command Line Parameters
	If $g_asCmdLine[0] > 0 Then
		$g_sProfileCurrentName = StringRegExpReplace($g_asCmdLine[1], '[/:*?"<>|]', '_')
	ElseIf FileExists($g_sProfilePath & "\profile.ini") Then
		$g_sProfileCurrentName = StringRegExpReplace(IniRead($g_sProfilePath & "\profile.ini", "general", "defaultprofile", ""), '[/:*?"<>|]', '_')
		If $g_sProfileCurrentName = "" Or Not FileExists($g_sProfilePath & "\" & $g_sProfileCurrentName) Then $g_sProfileCurrentName = "<No Profiles>"
	Else
		$g_sProfileCurrentName = "<No Profiles>"
	EndIf
EndFunc   ;==>ProcessCommandLine

Func InitializeAndroid()

	Local $s = GetTranslatedFileIni("MBR GUI Design - Loading", "StatusBar_Item_06", "Initializing Android...")
	SplashStep($s)

	If $g_bBotLaunchOption_Restart = False Then
		; initialize Android config
		InitAndroidConfig(True)

		; Change Android type and update variable
		If $g_asCmdLine[0] > 1 Then
			Local $i
			For $i = 0 To UBound($g_avAndroidAppConfig) - 1
				If StringCompare($g_avAndroidAppConfig[$i][0], $g_asCmdLine[2]) = 0 Then
					$g_iAndroidConfig = $i
					SplashStep($s & "(" & $g_avAndroidAppConfig[$i][0] & ")...", False)
					If $g_avAndroidAppConfig[$i][1] <> "" And $g_asCmdLine[0] > 2 Then
						; Use Instance Name
						UpdateAndroidConfig($g_asCmdLine[3])
					Else
						UpdateAndroidConfig()
					EndIf
					SplashStep($s & "(" & $g_avAndroidAppConfig[$i][0] & ")", False)
					ExitLoop
				EndIf
			Next
		EndIf

		SplashStep(GetTranslatedFileIni("MBR GUI Design - Loading", "StatusBar_Item_07", "Detecting Android..."))
		If $g_asCmdLine[0] < 2 Then
			;mini DetectRunningAndroid()
			;mini If Not $g_bFoundRunningAndroid Then DetectInstalledAndroid()
		EndIf

	Else

		; just increase step
		SplashStep($s)

	EndIf

	;mini CleanSecureFiles()

	;mini GetCOCDistributors() ; realy load of distributors to prevent rare bot freeze during boot

EndFunc   ;==>InitializeAndroid

Func InitAndroidConfig($bRestart = False)
	If $bRestart = False Then
		$g_sAndroidEmulator = $g_avAndroidAppConfig[$g_iAndroidConfig][0]
		$g_sAndroidInstance = $g_avAndroidAppConfig[$g_iAndroidConfig][1]
		$g_sAndroidTitle = $g_avAndroidAppConfig[$g_iAndroidConfig][2]
	EndIf

	$g_sAppClassInstance = $g_avAndroidAppConfig[$g_iAndroidConfig][3] ; Control Class and instance of android rendering
	$g_sAppPaneName = $g_avAndroidAppConfig[$g_iAndroidConfig][4] ; Control name of android rendering TODO check is still required
	$g_iAndroidClientWidth = $g_avAndroidAppConfig[$g_iAndroidConfig][5] ; Expected width of android rendering control
	$g_iAndroidClientHeight = $g_avAndroidAppConfig[$g_iAndroidConfig][6] ; Expected height of android rendering control
	$g_iAndroidWindowWidth = $g_avAndroidAppConfig[$g_iAndroidConfig][7] ; Expected Width of android window
	$g_iAndroidWindowHeight = $g_avAndroidAppConfig[$g_iAndroidConfig][8] ; Expected height of android window
	$g_iAndroidAdbSuCommand = "" ; Android path to su
	$g_sAndroidAdbPath = "" ; Path to executable HD-Adb.exe or adb.exe
	$g_sAndroidAdbDevice = $g_avAndroidAppConfig[$g_iAndroidConfig][10] ; full device name ADB connects to
	$g_iAndroidSupportFeature = $g_avAndroidAppConfig[$g_iAndroidConfig][11] ; 0 = Not available, 1 = Available, 2 = Available using ADB (experimental!)
	$g_sAndroidShellPrompt = $g_avAndroidAppConfig[$g_iAndroidConfig][12] ; empty string not available, '# ' for rooted and '$ ' for not rooted android
	$g_sAndroidMouseDevice = $g_avAndroidAppConfig[$g_iAndroidConfig][13] ; empty string not available, can be direct device '/dev/input/event2' or name by getevent -p
	$g_iAndroidEmbedMode = $g_avAndroidAppConfig[$g_iAndroidConfig][14] ; Android Dock Mode: -1 = Not available, 0 = Normal docking, 1 = Simulated docking
	$g_iAndroidBackgroundModeDefault = $g_avAndroidAppConfig[$g_iAndroidConfig][15] ; Default Android Background Mode: 1 = WinAPI mode (faster, but requires Android DirectX), 2 = ADB screencap mode (slower, but alwasy works even if Monitor is off -> "True Brackground Mode")
	$g_bAndroidAdbScreencap = $g_bAndroidAdbScreencapEnabled = True And BitAND($g_iAndroidSupportFeature, 2) = 2 ; Use Android ADB to capture screenshots in RGBA raw format
	$g_bAndroidAdbClick = $g_bAndroidAdbClickEnabled = True And AndroidAdbClickSupported() ; Enable Android ADB mouse click
	$g_bAndroidAdbInput = $g_bAndroidAdbInputEnabled = True And BitAND($g_iAndroidSupportFeature, 8) = 8 ; Enable Android ADB send text (CC requests)
	$g_bAndroidAdbInstance = $g_bAndroidAdbInstanceEnabled = True And BitAND($g_iAndroidSupportFeature, 16) = 16 ; Enable Android steady ADB shell instance when available
	$g_bAndroidAdbClickDrag = $g_bAndroidAdbClickDragEnabled = True And BitAND($g_iAndroidSupportFeature, 32) = 32 ; Enable Android ADB Click Drag script or input swipe
	$g_bAndroidEmbed = $g_bAndroidEmbedEnabled = True And $g_iAndroidEmbedMode > -1 ; Enable Android Docking
	$g_bAndroidBackgroundLaunch = $g_bAndroidBackgroundLaunchEnabled = True ; Enabled Android Background launch using Windows Scheduled Task
	$g_bAndroidBackgroundLaunched = False ; True when Android was launched in headless mode without a window
	$g_bUpdateAndroidWindowTitle = False ; If Android has always same title (like LeapDroid) instance name will be added
	; screencap might have disabled backgroundmode
	If $g_bAndroidAdbScreencap And IsDeclared("g_hChkBackground") Then
		; when GUI is initialized, update background checkbox
		chkBackground()
	EndIf

	UpdateHWnD($g_hAndroidWindow, False) ; Ensure $g_sAppClassInstance is properly set
EndFunc   ;==>InitAndroidConfig

Func UpdateAndroidConfig($instance = Default, $emulator = Default)
	If $emulator <> Default Then
		; Update $g_iAndroidConfig
		For $i = 0 To UBound($g_avAndroidAppConfig) - 1
			If $g_avAndroidAppConfig[$i][0] = $emulator Then
				If $g_iAndroidConfig <> $i Then
					$g_iAndroidConfig = $i
					$g_sAndroidEmulator = $g_avAndroidAppConfig[$g_iAndroidConfig][0]
					SetLog("Android Emulator " & $g_sAndroidEmulator)
				EndIf
				$emulator = Default
				ExitLoop
			EndIf
		Next
	EndIf
	If $emulator <> Default Then SetLog("Unknown Android Emulator " & $emulator, $COLOR_RED)
	If $instance = "" Then $instance = Default
	If $instance = Default Then $instance = $g_avAndroidAppConfig[$g_iAndroidConfig][1]
	SetDebugLog("UpdateAndroidConfig(""" & $instance & """)")

	InitAndroidConfig(False)
	$g_sAndroidInstance = $instance ; Clone or instance of emulator or "" if not supported/default instance

	; update secure setting
	If BitAND($g_iAndroidSecureFlags, 1) = 1 Then
		$g_sAndroidPicturesHostFolder = ""
	Else
		$g_sAndroidPicturesHostFolder = "mybot.run\"
	EndIf

	; validate install and initialize Android variables
	Local $Result = InitAndroid(False, False)

	SetDebugLog("UpdateAndroidConfig(""" & $instance & """) END")
	Return $Result
EndFunc   ;==>UpdateAndroidConfig

Func AndroidAdbClickSupported()
	Return BitAND($g_iAndroidSupportFeature, 4) = 4
EndFunc   ;==>AndroidAdbClickSupported

Func InitAndroid($bCheckOnly = False, $bLogChangesOnly = True)
	If $bCheckOnly = False And $g_bInitAndroid = False Then
		;SetDebugLog("InitAndroid(" & $bCheckOnly & "): " & $g_sAndroidEmulator & " is already initialized");
		Return True
	EndIf
	$g_bInitAndroidActive = True
	Local $aPriorValues = [ _
			$g_sAndroidEmulator _
			, $g_iAndroidConfig _
			, $g_sAndroidVersion _
			, $g_sAndroidInstance _
			, $g_sAndroidTitle _
			, $g_sAndroidProgramPath _
			, GetAndroidProgramParameter() _
			, ((IsArray($g_avAndroidProgramFileVersionInfo) ? _ArrayToString($g_avAndroidProgramFileVersionInfo, ",", 1) : "not available")) _
			, $g_iAndroidSecureFlags _
			, $g_sAndroidAdbPath _
			, $g_sAndroidAdbGlobalOptions _
			, $__VBoxManage_Path _
			, $g_sAndroidAdbDevice _
			, $g_sAndroidPicturesPath _
			, $g_sAndroidPicturesHostPath _
			, $g_sAndroidPicturesHostFolder _
			, $g_sAndroidMouseDevice _
			, $g_bAndroidAdbScreencap _
			, $g_bAndroidAdbInput _
			, $g_bAndroidAdbClick _
			, $g_bAndroidAdbClickDrag _
			, ($g_bChkBackgroundMode = True ? "enabled" : "disabled") _
			, $g_bNoFocusTampering _
			]
	SetDebugLog("InitAndroid(" & $bCheckOnly & "): " & $g_sAndroidEmulator)

	If Not $bCheckOnly Then
		; Check that $g_sAndroidInstance default instance is used for ""
		If $g_sAndroidInstance = "" Then $g_sAndroidInstance = $g_avAndroidAppConfig[$g_iAndroidConfig][1]

		; clear some values for optional vbox calls
		$__VBoxGuestProperties = ""
		$__VBoxExtraData = ""
	EndIf

	; call Android initialization routine
	Local $Result = Execute("Init" & $g_sAndroidEmulator & "(" & $bCheckOnly & ")")
	If $Result = "" And @error <> 0 Then
		; Not implemented
		SetLog("Android support for " & $g_sAndroidEmulator & " is not available", $COLOR_ERROR)
	EndIf

	Local $successful = @error = 0, $process_killed
	If Not $bCheckOnly And $Result Then

		; exclude Android for WerFault reporting
		If $b_sAndroidProgramWerFaultExcluded = True Then
			Local $sFileOnly = StringMid($g_sAndroidProgramPath, StringInStr($g_sAndroidProgramPath, "\", 0, -1) + 1)
			Local $aResult = DllCall("Wer.dll", "int", "WerAddExcludedApplication", "wstr", $sFileOnly, "bool", True)
			If (UBound($aResult) > 0 And $aResult[0] = $S_OK) Or RegWrite($g_sHKLM & "\Software\Microsoft\Windows\Windows Error Reporting\ExcludedApplications", $sFileOnly, "REG_DWORD", "1") = 1 Then
				SetDebugLog("Disabled WerFault for " & $sFileOnly)
			Else
				SetDebugLog("Cannot disable WerFault for " & $sFileOnly)
			EndIf
		EndIf

		; update Virtualbox properties
		If FileExists($__VBoxManage_Path) Then
			If $__VBoxGuestProperties = "" Then $__VBoxGuestProperties = LaunchConsole($__VBoxManage_Path, "guestproperty enumerate " & $g_sAndroidInstance, $process_killed)
			If $__VBoxExtraData = "" Then $__VBoxExtraData = LaunchConsole($__VBoxManage_Path, "getextradata " & $g_sAndroidInstance & " enumerate", $process_killed)
		EndIf

		UpdateAndroidBackgroundMode()

		; read Android Program Details
		Local $pAndroidFileVersionInfo
		If _WinAPI_GetFileVersionInfo($g_sAndroidProgramPath, $pAndroidFileVersionInfo) Then
			$g_avAndroidProgramFileVersionInfo = _WinAPI_VerQueryValue($pAndroidFileVersionInfo)
		Else
			$g_avAndroidProgramFileVersionInfo = 0
		EndIf

		Local $i = 0
		Local $sText = ""
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_sAndroidEmulator) Or $bLogChangesOnly = False Then SetDebugLog("Android: " & $g_sAndroidEmulator)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_iAndroidConfig) Or $bLogChangesOnly = False Then SetDebugLog("Android Config: " & $g_iAndroidConfig)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_sAndroidVersion) Or $bLogChangesOnly = False Then SetDebugLog("Android Version: " & $g_sAndroidVersion)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_sAndroidInstance) Or $bLogChangesOnly = False Then SetDebugLog("Android Instance: " & $g_sAndroidInstance)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_sAndroidTitle) Or $bLogChangesOnly = False Then SetDebugLog("Android Window Title: " & $g_sAndroidTitle)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_sAndroidProgramPath) Or $bLogChangesOnly = False Then SetDebugLog("Android Program Path: " & $g_sAndroidProgramPath)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], GetAndroidProgramParameter()) Or $bLogChangesOnly = False Then SetDebugLog("Android Program Parameter: " & GetAndroidProgramParameter())
		$sText = ((IsArray($g_avAndroidProgramFileVersionInfo) ? _ArrayToString($g_avAndroidProgramFileVersionInfo, ",", 1) : "not available"))
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $sText) Or $bLogChangesOnly = False Then SetDebugLog("Android Program FileVersionInfo: " & $sText)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_iAndroidSecureFlags) Or $bLogChangesOnly = False Then SetDebugLog("Android SecureME setting: " & $g_iAndroidSecureFlags)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_sAndroidAdbPath) Or $bLogChangesOnly = False Then SetDebugLog("Android ADB Path: " & $g_sAndroidAdbPath)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_sAndroidAdbGlobalOptions) Or $bLogChangesOnly = False Then SetDebugLog("Android ADB Global Options: " & $g_sAndroidAdbGlobalOptions)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $__VBoxManage_Path) Or $bLogChangesOnly = False Then SetDebugLog("Android VBoxManage Path: " & $__VBoxManage_Path)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_sAndroidAdbDevice) Or $bLogChangesOnly = False Then SetDebugLog("Android ADB Device: " & $g_sAndroidAdbDevice)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_sAndroidPicturesPath) Or $bLogChangesOnly = False Then SetDebugLog("Android ADB Shared Folder: " & $g_sAndroidPicturesPath)
		; check if share folder exists
		If FileExists($g_sAndroidPicturesHostPath) Then
			If ($g_sAndroidPicturesHostFolder <> "" Or BitAND($g_iAndroidSecureFlags, 1) = 1) Then
				DirCreate($g_sAndroidPicturesHostPath & $g_sAndroidPicturesHostFolder)
			EndIf
		ElseIf $g_sAndroidPicturesHostPath <> "" Then
			SetLog("Shared Folder doesn't exist, please fix:", $COLOR_ERROR)
			SetLog($g_sAndroidPicturesHostPath, $COLOR_ERROR)
		EndIf
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_sAndroidPicturesHostPath) Or $bLogChangesOnly = False Then SetDebugLog("Android ADB Shared Folder on Host: " & $g_sAndroidPicturesHostPath)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_sAndroidPicturesHostFolder) Or $bLogChangesOnly = False Then SetDebugLog("Android ADB Shared SubFolder: " & $g_sAndroidPicturesHostFolder)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_sAndroidMouseDevice) Or $bLogChangesOnly = False Then SetDebugLog("Android Mouse Device: " & $g_sAndroidMouseDevice)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_bAndroidAdbScreencap) Or $bLogChangesOnly = False Then SetDebugLog("Android ADB screencap command enabled: " & $g_bAndroidAdbScreencap)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_bAndroidAdbInput) Or $bLogChangesOnly = False Then SetDebugLog("Android ADB input command enabled: " & $g_bAndroidAdbInput)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_bAndroidAdbClick) Or $bLogChangesOnly = False Then SetDebugLog("Android ADB Mouse Click enabled: " & $g_bAndroidAdbClick)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_bAndroidAdbClickDrag) Or $bLogChangesOnly = False Then SetDebugLog("Android ADB Click Drag enabled: " & $g_bAndroidAdbClickDrag)
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], ($g_bChkBackgroundMode = True ? "enabled" : "disabled")) Or $bLogChangesOnly = False Then SetDebugLog("Bot Background Mode for screen capture: " & ($g_bChkBackgroundMode = True ? "enabled" : "disabled"))
		If CompareAndUpdate($aPriorValues[IncrUpdate($i)], $g_bNoFocusTampering) Or $bLogChangesOnly = False Then SetDebugLog("No Focus Tampering: " & $g_bNoFocusTampering)
		;$g_hAndroidWindow = WinGetHandle($g_sAndroidTitle) ;Handle for Android window
		WinGetAndroidHandle() ; Set $g_hAndroidWindow and $g_sAndroidTitle for Android window
		InitAndroidTimeLag()
		InitAndroidPageError()
		$g_bInitAndroid = Not $successful
	Else
		If $bCheckOnly = False Then $g_bInitAndroid = True
	EndIf
	SetDebugLog("InitAndroid(" & $bCheckOnly & "): " & $g_sAndroidEmulator & " END, initialization successful = " & $successful & ", result = " & $Result)
	$g_bInitAndroidActive = False
	Return $Result
EndFunc   ;==>InitAndroid

Func IncrUpdate(ByRef $i, $ReturnInitial = True)
	Local $i2 = $i
	$i += 1
	If $ReturnInitial Then Return $i2
	Return $i
EndFunc   ;==>IncrUpdate

Func CompareAndUpdate(ByRef $UpdateWhenDifferent, Const $New)
	Local $bDifferent = $UpdateWhenDifferent <> $New
	If $bDifferent Then $UpdateWhenDifferent = $New
	Return $bDifferent
EndFunc   ;==>CompareAndUpdate

Func GetVersionNormalized($VersionString, $Chars = 5)
	If StringLeft($VersionString, 1) = "v" Then $VersionString = StringMid($VersionString, 2)
	Local $a = StringSplit($VersionString, ".", 2)
	Local $i
	For $i = 0 To UBound($a) - 1
		If StringLen($a[$i]) < $Chars Then $a[$i] = _StringRepeat("0", $Chars - StringLen($a[$i])) & $a[$i]
	Next
	Return _ArrayToString($a, ".")
EndFunc   ;==>GetVersionNormalized

Func InitAndroidTimeLag()
EndFunc   ;==>InitAndroidTimeLag

Func InitAndroidPageError()
EndFunc   ;==>InitAndroidPageError

Func UpdateHWnD($hWin, $bRestart = True)
EndFunc   ;==>UpdateHWnD

Func GetAndroidProgramParameter()
	Return ""
EndFunc   ;==>GetAndroidProgramParameter

Func BotMoveRequest()
	$g_bBotMoveRequested = True
EndFunc   ;==>BotMoveRequest

Func BotMinimizeRequest()
	BotMinimize("MinimizeButton", False, 500)
EndFunc   ;==>BotMinimizeRequest

Func UpdateAndroidBackgroundMode()
EndFunc   ;==>UpdateAndroidBackgroundMode

Func readWeakBaseStats()
EndFunc   ;==>readWeakBaseStats

Func BotMinimizeRestore($bMinimize, $sCaller, $iForceUpdatingWhenMinimized = False, $iStayMinimizedMillis = 0)

	Static $siStayMinimizedMillis = 0
	Static $shStayMinimizedTimer = 0

	If $bMinimize Then
		If $iStayMinimizedMillis > 0 Then
			$siStayMinimizedMillis = $iStayMinimizedMillis
			$shStayMinimizedTimer = __TimerInit()
		EndIf
		;Local $hMutex = AcquireMutex("MinimizeRestore")
		If $g_bAndroidEmbedded = True And $g_bChkBackgroundMode = False Then
			; don't minimize bot when embedded and background mode is off
			;ReleaseMutex($hMutex)
			Return False
		EndIf
		SetDebugLog("Minimize bot window, caller: " & $sCaller, Default, True)
		$g_bFrmBotMinimized = True
		If $g_bUpdatingWhenMinimized Or $iForceUpdatingWhenMinimized = True Then
			If $g_bHideWhenMinimized Then
				WinMove2($g_hFrmBot, "", -32000, -32000, -1, -1, 0, $SWP_HIDEWINDOW, False)
				_WinAPI_SetWindowLong($g_hFrmBot, $GWL_EXSTYLE, BitOR(_WinAPI_GetWindowLong($g_hFrmBot, $GWL_EXSTYLE), $WS_EX_TOOLWINDOW))
			EndIf
			If _WinAPI_IsIconic($g_hFrmBot) Then WinSetState($g_hFrmBot, "", @SW_RESTORE)
			If _WinAPI_IsIconic($g_hAndroidWindow) Then WinSetState($g_hAndroidWindow, "", @SW_RESTORE)
			WinMove2($g_hFrmBot, "", -32000, -32000, -1, -1, 0, $SWP_SHOWWINDOW, False)
		Else
			If $g_bHideWhenMinimized Then
				WinMove2($g_hFrmBot, "", -1, -1, -1, -1, 0, $SWP_HIDEWINDOW, False)
				_WinAPI_SetWindowLong($g_hFrmBot, $GWL_EXSTYLE, BitOR(_WinAPI_GetWindowLong($g_hFrmBot, $GWL_EXSTYLE), $WS_EX_TOOLWINDOW))
			EndIf
			WinSetState($g_hFrmBot, "", @SW_MINIMIZE)
			;WinSetState($g_hAndroidWindow, "", @SW_MINIMIZE)
		EndIf
		;ReleaseMutex($hMutex)
		Return True
	EndIf

	If $siStayMinimizedMillis > 0 And __TimerDiff($shStayMinimizedTimer) < $siStayMinimizedMillis Then
		SetDebugLog("Prevent Bot Window Restore")
		Return False
	Else
		$siStayMinimizedMillis = 0
		$shStayMinimizedTimer = 0
	EndIf

	;Local $hMutex = AcquireMutex("MinimizeRestore")
	$g_bFrmBotMinimized = False
	Local $botPosX = ($g_bAndroidEmbedded = False ? $g_iFrmBotPosX : $g_iFrmBotDockedPosX)
	Local $botPosY = ($g_bAndroidEmbedded = False ? $g_iFrmBotPosY : $g_iFrmBotDockedPosY)
	Local $aPos = [$botPosX, $botPosY]
	SetDebugLog("Restore bot window to " & $botPosX & ", " & $botPosY & ", caller: " & $sCaller, Default, True)
	Local $iExStyle = _WinAPI_GetWindowLong($g_hFrmBot, $GWL_EXSTYLE)
	If BitAND($iExStyle, $WS_EX_TOOLWINDOW) Then
		WinMove2($g_hFrmBot, "", -1, -1, -1, -1, 0, $SWP_HIDEWINDOW, False)
		_WinAPI_SetWindowLong($g_hFrmBot, $GWL_EXSTYLE, BitAND($iExStyle, BitNOT($WS_EX_TOOLWINDOW)))
	EndIf
	If _WinAPI_IsIconic($g_hFrmBot) Then WinSetState($g_hFrmBot, "", @SW_RESTORE)
	If $g_bAndroidAdbScreencap = False And $g_bRunState = True And $g_bBotPaused = False And _WinAPI_IsIconic($g_hAndroidWindow) Then WinSetState($g_hAndroidWindow, "", @SW_RESTORE)
	WinMove2($g_hFrmBot, "", $botPosX, $botPosY, -1, -1, $HWND_TOP, $SWP_SHOWWINDOW)
	_WinAPI_SetActiveWindow($g_hFrmBot)
	_WinAPI_SetFocus($g_hFrmBot)
	If _CheckWindowVisibility($g_hFrmBot, $aPos) Then
		SetDebugLog("Bot Window '" & $g_sAndroidTitle & "' not visible, moving to position: " & $aPos[0] & ", " & $aPos[1])
		WinMove2($g_hFrmBot, "", $aPos[0], $aPos[1])
	EndIf
	WinSetTrans($g_hFrmBot, "", 255) ; is set to 1 when "Hide when minimized" is enabled after some time, so restore it
	;ReleaseMutex($hMutex)
	Return True

EndFunc   ;==>BotMinimizeRestore

Func BotMinimize($sCaller, $iForceUpdatingWhenMinimized = False, $iStayMinimizedMillis = 0)
	Return BotMinimizeRestore(True, $sCaller, $iForceUpdatingWhenMinimized, $iStayMinimizedMillis)
EndFunc   ;==>BotMinimize

Func BotRestore($sCaller)
	Return BotMinimizeRestore(False, $sCaller)
EndFunc   ;==>BotRestore

Func BotCloseRequest()
	If $g_iBotAction = $eBotClose Then
		; already requested to close, but user is impatient, so close now
		BotClose()
	Else
		SetLog("Closing " & $g_sBotTitle & ", please wait ...")
	EndIf
	$g_bRunState = False
	$g_bBotPaused = False
	$g_iBotAction = $eBotClose
EndFunc   ;==>BotCloseRequest

Func AndroidEmbedArrangeActive()
	Return False
EndFunc   ;==>AndroidEmbedArrangeActive

Func CheckBotShrinkExpandButton()
	Return False
EndFunc   ;==>CheckBotShrinkExpandButton

Func AndroidEmbedCheck($p1 = False, $p2 = Default, $iAction = Default)
	Return False
EndFunc   ;==>AndroidEmbedCheck

Func BotWindowCheck()
	Return True
EndFunc   ;==>BotWindowCheck

Func CheckBotZOrder()
EndFunc   ;==>CheckBotZOrder

Func BotShrinkExpandToggleExecute()
EndFunc   ;==>BotShrinkExpandToggleExecute

Func updateBtnEmbed()
EndFunc   ;==>updateBtnEmbed

Func AndroidEmbed($bEmbed = True)
EndFunc   ;==>AndroidEmbed

Func WinGetAndroidHandle()
	Return 0
EndFunc   ;==>WinGetAndroidHandle

Func GetAndroidPid()
EndFunc   ;==>GetAndroidPid

Func _CaptureDispose()
EndFunc   ;==>_CaptureDispose

Func SplashStep($s, $a = 0)
EndFunc   ;==>SplashStep

Func SuspendAndroid($bSuspend = True)
	Return False
EndFunc   ;==>SuspendAndroid

; Called from _Sleep() to avoid locked window move state, double minimize calls etc
Func CheckBotRequests()
	CheckBotZOrder() ; check Z Order of Windows is ok
	If $g_bBotMoveRequested = True Then
		$g_bBotMoveRequested = False
		_WinAPI_PostMessage($g_hFrmBot, $WM_SYSCOMMAND, 0xF012, 0) ; SC_DRAGMOVE = 0xF012
	Else
		If $g_bBotShrinkExpandToggleRequested Then BotShrinkExpandToggleExecute()
	EndIf
EndFunc   ;==>CheckBotRequests

Func SetCriticalMessageProcessing($bCritical = Default)
	Return False
EndFunc   ;==>SetCriticalMessageProcessing

Func SetupProfileFolder()
	$g_sProfileConfigPath = $g_sProfilePath & "\" & $g_sProfileCurrentName & "\config.ini"
	$g_sProfileBuildingStatsPath = $g_sProfilePath & "\" & $g_sProfileCurrentName & "\stats_buildings.ini"
	$g_sProfileBuildingPath = $g_sProfilePath & "\" & $g_sProfileCurrentName & "\building.ini"
	$g_sProfileClanGamesPath = $g_sProfilePath & "\" & $g_sProfileCurrentName & "\clangames.ini"
	$g_sProfileLogsPath = $g_sProfilePath & "\" & $g_sProfileCurrentName & "\Logs\"
	$g_sProfileLootsPath = $g_sProfilePath & "\" & $g_sProfileCurrentName & "\Loots\"
	$g_sProfileTempPath = $g_sProfilePath & "\" & $g_sProfileCurrentName & "\Temp\"
	$g_sProfileTempDebugPath = $g_sProfilePath & "\" & $g_sProfileCurrentName & "\Temp\Debug\"
	$g_sProfileDonateCapturePath = $g_sProfilePath & "\" & $g_sProfileCurrentName & '\Donate\'
	$g_sProfileDonateCaptureWhitelistPath = $g_sProfilePath & "\" & $g_sProfileCurrentName & '\Donate\White List\'
	$g_sProfileDonateCaptureBlacklistPath = $g_sProfilePath & "\" & $g_sProfileCurrentName & '\Donate\Black List\'
EndFunc   ;==>SetupProfileFolder

; Open URL in default browser using ShellExecute
; URL is retrieved from label text or an existing ToolTip Control
Func OpenURL_Label($LabelCtrlID)
	Local $url = GUICtrlRead($LabelCtrlID)
	If IsString($LabelCtrlID) Then $url = $LabelCtrlID
	If StringInStr($url, "http") <> 1 Then
		$url = _GUIToolTip_GetText($g_hToolTip, 0, GUICtrlGetHandle($LabelCtrlID))
	EndIf
	If StringInStr($url, "http") = 1 Then
		SetDebugLog("Open URL: " & $url)
		ShellExecute($url) ;open web site when clicking label
	Else
		SetDebugLog("Cannot open URL for Control ID " & $LabelCtrlID, $COLOR_ERROR)
	EndIf
EndFunc   ;==>OpenURL_Label

Func _GUICtrlStatusBar_SetTextEx($hWnd, $sText = "", $iPart = 0, $iUFlag = 0)
	If $hWnd Then _GUICtrlStatusBar_SetText($hWnd, $sText, $iPart, $iUFlag)
EndFunc   ;==>_GUICtrlStatusBar_SetTextEx

Func GUIEvents()
	;@GUI_WinHandle
	;Local $wasCritical = SetCriticalMessageProcessing(True)
	Local $wasAllowed = $g_bTogglePauseAllowed
	$g_bTogglePauseAllowed = False
	Local $GUI_CtrlId = @GUI_CtrlId
	SetDebugLog("GUIEvents: " & $GUI_CtrlId, Default, True)
	If $g_bFrmBotMinimized And $GUI_CtrlId = $GUI_EVENT_MINIMIZE Then
		; restore
		If $g_iDebugWindowMessages Then SetDebugLog("$GUI_EVENT_MINIMIZE changed to $GUI_EVENT_RESTORE", Default, True)
		$GUI_CtrlId = $GUI_EVENT_RESTORE
	EndIf
	Switch $GUI_CtrlId
		Case $GUI_EVENT_CLOSE
			If $g_iDebugWindowMessages Then SetDebugLog("$GUI_EVENT_CLOSE", Default, True)
			BotCloseRequest()

		Case $GUI_EVENT_MINIMIZE
			If $g_iDebugWindowMessages Then SetDebugLog("$GUI_EVENT_MINIMIZE", Default, True)
			BotMinimize("GUIEvents")
			;Return 0

		Case $GUI_EVENT_RESTORE
			If $g_iDebugWindowMessages Then SetDebugLog("$GUI_EVENT_RESTORE", Default, True)
			BotRestore("GUIEvents")

		Case Else
			If $g_iDebugWindowMessages Then SetDebugLog("$GUI_EVENT: " & @GUI_CtrlId, Default, True)
	EndSwitch
	$g_bTogglePauseAllowed = $wasAllowed
EndFunc   ;==>GUIEvents

Func GUIControl_WM_CLOSE($hWind, $iMsg, $wParam, $lParam)
	;Local $wasCritical = SetCriticalMessageProcessing(True)
	If $g_iDebugWindowMessages > 0 Then SetDebugLog("GUIControl_WM_CLOSE: $hWind=" & $hWind & ",$iMsg=" & $iMsg & ",$wParam=" & $wParam & ",$lParam=" & $lParam, Default, True)
	If $hWind = $g_hFrmBot Then
		BotCloseRequest()
	EndIf
EndFunc   ;==>GUIControl_WM_CLOSE

Func GUIControl_WM_COMMAND($hWind, $iMsg, $wParam, $lParam)
	If $g_bGUIControlDisabled = True Then Return $GUI_RUNDEFMSG
	Local $wasAllowed = $g_bTogglePauseAllowed
	$g_bTogglePauseAllowed = False
	If $g_iDebugWindowMessages > 1 Then SetDebugLog("GUIControl_WM_COMMAND: $hWind=" & $hWind & ",$iMsg=" & $iMsg & ",$wParam=" & $wParam & ",$lParam=" & $lParam, Default, True)
	Local $nNotifyCode = BitShift($wParam, 16)
	Local $nID = BitAND($wParam, 0x0000FFFF)
	Local $hCtrl = $lParam

	Switch $nID
		Case $g_hLblBotMinimize
			BotMinimizeRequest()
		Case $GUI_EVENT_CLOSE, $g_hLblBotClose
			; Clean up resources
			BotCloseRequest()
		Case $g_hFrmBot_URL_PIC, $g_hFrmBot_URL_PIC2
			If EnvGet("MYBOT_CONTROL_CENTER_NO_BROWSER") <> "1" Then
				ShellExecute("http://127.0.0.1:8765/")
			Else
				SetDebugLog("Control Center browser open suppressed by environment")
			EndIf
		Case $g_hLblDonate
			; Donate URL is not in text nor tooltip
			ShellExecute("https://mybot.run/forums/index.php?/donate/make-donation/")
		Case $g_hBtnStart, $g_hTblStart
			btnStart()
		Case $g_hBtnStop, $g_hTblStop
			btnStop()
		Case $g_hBtnPause, $g_hTblPause
			btnPause()
		Case $g_hBtnResume, $g_hTblResume
			btnResume()
		Case $g_hBtnHide
			btnHide()
		Case $g_hBtnMakeScreenshot, $g_hTblMakeScreenshot
			btnMakeScreenshot()
		Case $g_hPicTwoArrowShield
			btnVillageStat()
		Case $g_hPicArrowLeft, $g_hPicArrowRight
			btnVillageStat()

	EndSwitch
	#cs mini
		If $lParam = $g_hCmbGUILanguage Then
		If $nNotifyCode = $CBN_SELCHANGE Then cmbLanguage()
		EndIf
	#ce
	$g_bTogglePauseAllowed = $wasAllowed
	Return $GUI_RUNDEFMSG
EndFunc   ;==>GUIControl_WM_COMMAND

Func GUIControl_WM_MOVE($hWind, $iMsg, $wParam, $lParam)
	;If $g_bGUIControlDisabled = True Then Return $GUI_RUNDEFMSG
	If $g_bBotShrinkExpandToggleRequested Then Return $GUI_RUNDEFMSG ; bot shrinking is requested or active
	Local $wasCritical = SetCriticalMessageProcessing(True)
	Local $wasAllowed = $g_bTogglePauseAllowed
	$g_bTogglePauseAllowed = False
	If $g_iDebugWindowMessages Then SetDebugLog("GUIControl_WM_MOVE: $hWind=" & $hWind & ",$iMsg=" & $iMsg & ",$wParam=" & $wParam & ",$lParam=" & $lParam, Default, True)
	If $hWind = $g_hFrmBot Then
		If $g_bUpdatingWhenMinimized And BotWindowCheck() = False And _WinAPI_IsIconic($g_hFrmBot) Then
			; ensure bot is not really minimized (e.g. when you minimize all windows)
			BotMinimize("GUIControl_WM_MOVE")
			$g_bTogglePauseAllowed = $wasAllowed
			SetCriticalMessageProcessing($wasCritical)
			Return $GUI_RUNDEFMSG
		EndIf

		; update bot pos variables
		Local $g_iFrmBotPos = WinGetPos($g_hFrmBot)
		If $g_bAndroidEmbedded = False Then
			$g_iFrmBotPosX = ($g_iFrmBotPos[0] > -30000 ? $g_iFrmBotPos[0] : $g_iFrmBotPosX)
			$g_iFrmBotPosY = ($g_iFrmBotPos[1] > -30000 ? $g_iFrmBotPos[1] : $g_iFrmBotPosY)
		Else
			$g_iFrmBotDockedPosX = ($g_iFrmBotPos[0] > -30000 ? $g_iFrmBotPos[0] : $g_iFrmBotDockedPosX)
			$g_iFrmBotDockedPosY = ($g_iFrmBotPos[1] > -30000 ? $g_iFrmBotPos[1] : $g_iFrmBotDockedPosY)
		EndIf

		; required for screen change
		If $g_bAndroidEmbedded And AndroidEmbedArrangeActive() = False Then
			CheckBotShrinkExpandButton()
			Local $iAction = AndroidEmbedCheck(True)
			If $iAction > 0 Then
				; reposition docked android
				AndroidEmbedCheck(False, Default, $iAction)
				; redraw bot also
				;temp;_WinAPI_RedrawWindow($g_hFrmBotEx, 0, 0, $RDW_INVALIDATE)
				;temp;_WinAPI_RedrawWindow($frmBotBottom, 0, 0, $RDW_INVALIDATE)
			EndIf
			If $g_iDebugWindowMessages Then
				Local $a = $g_iFrmBotPos
				SetDebugLog("Bot Position: " & $a[0] & "," & $a[1] & " " & $a[2] & "x" & $a[3])
				$a = WinGetPos($g_hAndroidWindow)
				SetDebugLog("Android Position: " & $a[0] & "," & $a[1] & " " & $a[2] & "x" & $a[3])
				If $g_hFrmBotEmbeddedMouse <> 0 Then
					$a = WinGetPos($g_hFrmBotEmbeddedMouse)
					SetDebugLog("Mouse Window Position: " & $a[0] & "," & $a[1] & " " & $a[2] & "x" & $a[3])
				EndIf
			EndIf
		EndIf
	EndIf

	$g_bTogglePauseAllowed = $wasAllowed
	SetCriticalMessageProcessing($wasCritical)
	Return $GUI_RUNDEFMSG
EndFunc   ;==>GUIControl_WM_MOVE

Func SetTime($bForceUpdate = False)
	If $g_hTimerSinceStarted = 0 Then Return ; GIGO, no setTime when timer hasn't started yet
	Local $day = 0, $hour = 0, $min = 0, $sec = 0
	#cs mini
		If GUICtrlRead($g_hGUI_STATS_TAB, 1) = $g_hGUI_STATS_TAB_ITEM2 Or $bForceUpdate = True Then
		_TicksToDay(Int(__TimerDiff($g_hTimerSinceStarted) + $g_iTimePassed), $day, $hour, $min, $sec)
		GUICtrlSetData($g_hLblResultRuntime, $day > 0 ? StringFormat("%2u Day(s) %02i:%02i:%02i", $day, $hour, $min, $sec) : StringFormat("%02i:%02i:%02i", $hour, $min, $sec))
		EndIf
	#ce
	If GUICtrlGetState($g_hLblResultGoldNow) <> $GUI_ENABLE + $GUI_SHOW Or $bForceUpdate = True Then
		_TicksToTime(Int(__TimerDiff($g_hTimerSinceStarted) + $g_iTimePassed), $hour, $min, $sec)
		GUICtrlSetData($g_hLblResultRuntimeNow, StringFormat("%02i:%02i:%02i", $hour, $min, $sec))
	EndIf
EndFunc   ;==>SetTime

Func TogglePause()
	TogglePauseImpl("Mini")
EndFunc   ;==>TogglePause

Func btnStart()
	;$g_iBotAction = $eBotStart
	BotStart()
EndFunc   ;==>btnStart

Func btnStop()
	;$g_iBotAction = $eBotStop
	BotStop()
EndFunc   ;==>btnStop

Func btnPause()
	TogglePause()
EndFunc   ;==>btnPause

Func btnResume()
	TogglePause()
EndFunc   ;==>btnResume

Func btnVillageStat($source = "")

	If $g_iFirstRun = 0 And $g_bRunState And Not $g_bBotPaused Then SetTime(True)

	If GUICtrlGetState($g_hLblResultGoldNow) = $GUI_ENABLE + $GUI_SHOW Then
		;hide normal values
		GUICtrlSetState($g_hLblResultGoldNow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hLblResultElixirNow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hLblResultDENow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hLblResultTrophyNow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hLblResultBuilderNow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hLblResultGemNow, $GUI_ENABLE + $GUI_HIDE)
		;show stats values
		GUICtrlSetState($g_hLblResultGoldHourNow, $GUI_ENABLE + $GUI_SHOW)
		GUICtrlSetState($g_hLblResultElixirHourNow, $GUI_ENABLE + $GUI_SHOW)
		GUICtrlSetState($g_hLblResultDEHourNow, $GUI_ENABLE + $GUI_SHOW)
		If $g_iFirstRun = 0 Or $source = "UpdateStats" Then
			GUICtrlSetState($g_hLblResultRuntimeNow, $GUI_ENABLE + $GUI_SHOW)
			GUICtrlSetState($g_hLblResultAttackedHourNow, $GUI_ENABLE + $GUI_SHOW)
			GUICtrlSetState($g_hLblResultSkippedHourNow, $GUI_ENABLE + $GUI_SHOW)
		EndIf
		; hide normal pics
		GUICtrlSetState($g_hPicResultTrophyNow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hPicResultBuilderNow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hPicResultGemNow, $GUI_ENABLE + $GUI_HIDE)
		;show stats pics
		GUICtrlSetState($g_hPicResultRuntimeNow, $GUI_ENABLE + $GUI_SHOW)
		GUICtrlSetState($g_hPicResultAttackedHourNow, $GUI_ENABLE + $GUI_SHOW)
		GUICtrlSetState($g_hPicResultSkippedHourNow, $GUI_ENABLE + $GUI_SHOW)
	Else
		;show normal values
		GUICtrlSetState($g_hLblResultGoldNow, $GUI_ENABLE + $GUI_SHOW)
		GUICtrlSetState($g_hLblResultElixirNow, $GUI_ENABLE + $GUI_SHOW)
		GUICtrlSetState($g_hLblResultDENow, $GUI_ENABLE + $GUI_SHOW)
		GUICtrlSetState($g_hLblResultTrophyNow, $GUI_ENABLE + $GUI_SHOW)
		GUICtrlSetState($g_hLblResultBuilderNow, $GUI_ENABLE + $GUI_SHOW)
		GUICtrlSetState($g_hLblResultGemNow, $GUI_ENABLE + $GUI_SHOW)
		;hide stats values
		GUICtrlSetState($g_hLblResultGoldHourNow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hLblResultElixirHourNow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hLblResultDEHourNow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hLblResultRuntimeNow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hLblResultAttackedHourNow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hLblResultSkippedHourNow, $GUI_ENABLE + $GUI_HIDE)
		; show normal pics
		GUICtrlSetState($g_hPicResultTrophyNow, $GUI_ENABLE + $GUI_SHOW)
		GUICtrlSetState($g_hPicResultBuilderNow, $GUI_ENABLE + $GUI_SHOW)
		GUICtrlSetState($g_hPicResultGemNow, $GUI_ENABLE + $GUI_SHOW)
		;hide stats pics
		GUICtrlSetState($g_hPicResultRuntimeNow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hPicResultAttackedHourNow, $GUI_ENABLE + $GUI_HIDE)
		GUICtrlSetState($g_hPicResultSkippedHourNow, $GUI_ENABLE + $GUI_HIDE)
	EndIf

EndFunc   ;==>btnVillageStat

Func btnHide()
EndFunc   ;==>btnHide

Func btnSearchMode()
EndFunc   ;==>btnSearchMode

Func btnEmbed()
EndFunc   ;==>btnEmbed

Func chkBackground()
EndFunc   ;==>chkBackground

Func ButtonBoost()
EndFunc   ;==>ButtonBoost

Func tiStartStop()
	If $g_bRunState Then
		btnStop()
	Else
		btnStart()
	EndIf
EndFunc   ;==>tiStartStop

Func tiShow()
	BotRestore("tiShow")
EndFunc   ;==>tiShow

Func tiHide()
	$g_bHideWhenMinimized = Not $g_bHideWhenMinimized
	TrayItemSetState($g_hTiHide, ($g_bHideWhenMinimized ? $TRAY_CHECKED : $TRAY_UNCHECKED))
	;mini GUICtrlSetState($g_hChkHideWhenMinimized, ($g_bHideWhenMinimized ? $GUI_CHECKED : $GUI_UNCHECKED))
	If $g_bFrmBotMinimized = True Then
		If $g_bHideWhenMinimized = False Then
			BotRestore("tiHide")
		Else
			BotMinimize("tiHide")
		EndIf
	EndIf
EndFunc   ;==>tiHide

Func tiAbout()
	Local $sMsg = $g_sProductName & " local automation control center" & @CRLF & @CRLF & _
			"Product version: " & $g_sProductVersion & @CRLF & _
			"Engine compatibility: MyBot.run " & $g_sEngineVersion & @CRLF & _
			"Released under the GNU GPLv3 license." & @CRLF & _
			"Source: github.com/slaveofsolace/My-Bot-2.0"
	MsgBox(64 + $MB_APPLMODAL + $MB_TOPMOST, $g_sBotTitle, $sMsg, 0, $g_hFrmBot)
EndFunc   ;==>tiAbout

Func tiDonate()
	ShellExecute("https://mybot.run/forums/index.php?/donate/make-donation/")
EndFunc   ;==>tiDonate

Func tiExit()
	BotCloseRequest()
EndFunc   ;==>tiExit

Func BotStarted()
	SetDebugLog("Bot started")
	GUICtrlSetState($g_hBtnStart, $GUI_HIDE)
	GUICtrlSetState($g_hBtnStop, $GUI_SHOW)
	GUICtrlSetState($g_hBtnPause, $g_bBotPaused ? $GUI_HIDE : $GUI_SHOW)
	GUICtrlSetState($g_hBtnResume, $g_bBotPaused ? $GUI_SHOW : $GUI_HIDE)
	GUICtrlSetState($g_hBtnSearchMode, $GUI_HIDE)
	GUICtrlSetState($g_hChkBackgroundMode, $GUI_DISABLE)

	; enable buttons
	GUICtrlSetState($g_hBtnStart, $GUI_ENABLE)
	GUICtrlSetState($g_hBtnStop, $GUI_ENABLE)

	; update try items
	TrayItemSetText($g_hTiStartStop, GetTranslatedFileIni("MBR GUI Design - Loading", "StatusBar_Item_Stop", "Stop bot"))
	TrayItemSetState($g_hTiPause, $TRAY_ENABLE)
	TrayItemSetText($g_hTiPause, GetTranslatedFileIni("MBR GUI Design - Loading", "StatusBar_Item_Pause", "Pause bot"))

	; update task bar buttons
	_ITaskBar_UpdateTBButton($g_hTblStop, $THBF_ENABLED)
	_ITaskBar_UpdateTBButton($g_hTblStart, $THBF_DISABLED)
	_ITaskBar_UpdateTBButton($g_hTblPause, $THBF_ENABLED)
	_ITaskBar_UpdateTBButton($g_hTblResume, $THBF_DISABLED)
EndFunc   ;==>BotStarted

Func BotStopped()
	SetDebugLog("Bot stopped")
	GUICtrlSetState($g_hChkBackgroundMode, $GUI_ENABLE)
	GUICtrlSetState($g_hBtnStart, $GUI_SHOW)
	GUICtrlSetState($g_hBtnStop, $GUI_HIDE)
	GUICtrlSetState($g_hBtnPause, $GUI_HIDE)
	GUICtrlSetState($g_hBtnResume, $GUI_HIDE)
	;If $g_iTownHallLevel > 2 Then GUICtrlSetState($g_hBtnSearchMode, $GUI_ENABLE)
	GUICtrlSetState($g_hBtnSearchMode, $GUI_SHOW)
	;GUICtrlSetState($g_hBtnMakeScreenshot, $GUI_ENABLE)

	; enable buttons
	GUICtrlSetState($g_hBtnStart, $GUI_ENABLE)
	GUICtrlSetState($g_hBtnStop, $GUI_ENABLE)

	; hide attack buttons if show
	;GUICtrlSetState($g_hBtnAttackNowDB, $GUI_HIDE)
	;GUICtrlSetState($g_hBtnAttackNowLB, $GUI_HIDE)
	;GUICtrlSetState($g_hBtnAttackNowTS, $GUI_HIDE)
	;GUICtrlSetState($g_hPicTwoArrowShield, $GUI_SHOW)
	;GUICtrlSetState($g_hLblVersion, $GUI_SHOW)

	; update try items
	TrayItemSetText($g_hTiStartStop, GetTranslatedFileIni("MBR GUI Design - Loading", "StatusBar_Item_Start", "Start bot"))
	TrayItemSetState($g_hTiPause, $TRAY_DISABLE)

	; update task bar buttons
	_ITaskBar_UpdateTBButton($g_hTblStart, $THBF_ENABLED)
	_ITaskBar_UpdateTBButton($g_hTblStop, $THBF_DISABLED)
	_ITaskBar_UpdateTBButton($g_hTblPause, $THBF_DISABLED)
	_ITaskBar_UpdateTBButton($g_hTblResume, $THBF_DISABLED)
EndFunc   ;==>BotStopped

Func BotPaused()
	SetDebugLog("Bot paused")
	GUICtrlSetState($g_hBtnPause, $GUI_HIDE)
	GUICtrlSetState($g_hBtnResume, $GUI_SHOW)
	TrayItemSetText($g_hTiPause, GetTranslatedFileIni("MBR GUI Design - Loading", "StatusBar_Item_Resume", "Resume bot"))
	_ITaskBar_UpdateTBButton($g_hTblPause, $THBF_DISABLED)
	_ITaskBar_UpdateTBButton($g_hTblResume, $THBF_ENABLED)
EndFunc   ;==>BotPaused

Func BotResumed()
	SetDebugLog("Bot resumed")
	GUICtrlSetState($g_hBtnPause, $GUI_SHOW)
	GUICtrlSetState($g_hBtnResume, $GUI_HIDE)
	TrayItemSetText($g_hTiPause, GetTranslatedFileIni("MBR GUI Design - Loading", "StatusBar_Item_Pause", "Pause bot"))
	_ITaskBar_UpdateTBButton($g_hTblPause, $THBF_ENABLED)
	_ITaskBar_UpdateTBButton($g_hTblResume, $THBF_DISABLED)
EndFunc   ;==>BotResumed

Func UpdateManagedMyBot($aBotDetails)
	;Global Enum $g_eBotDetailsBotForm = 0, $g_eBotDetailsTimer, $g_eBotDetailsProfile, $g_eBotDetailsCommandLine, $g_eBotDetailsTitle, $g_eBotDetailsRunState, $g_eBotDetailsPaused, $g_eBotDetailsLaunched, $g_eBotDetailsVerifyCount, $g_eBotDetailsBotStateStruct, $g_eBotDetailsOptionalStruct, $g_eBotDetailsArraySize
	If $g_iDebugWindowMessages Then SetDebugLog("UpdateManagedMyBot: " & $aBotDetails[$g_eBotDetailsBotForm])
	Local $sTitle = $aBotDetails[$g_eBotDetailsTitle]
	Local $bRunState = $aBotDetails[$g_eBotDetailsRunState]
	Local $bPaused = $aBotDetails[$g_eBotDetailsPaused]
	Local $bLaunched = $aBotDetails[$g_eBotDetailsLaunched]
	Local $tBotState = $aBotDetails[$g_eBotDetailsBotStateStruct]
	Local $tOptionalStruct = $aBotDetails[$g_eBotDetailsOptionalStruct]
	Local $sProfile = ""
	Local $sEmulator = ""
	Local $sInstance = ""
	Local $eStructType = $g_eSTRUCT_NONE
	Local $pStructPtr = 0
	Local $hTimerSinceStarted = 0
	Local $iTimePassed = 0
	If $tBotState <> 0 Then
		If $g_iDebugWindowMessages Then SetDebugLog("UpdateManagedMyBot: Update Sate: " & $aBotDetails[$g_eBotDetailsBotForm])
		$sProfile = DllStructGetData($tBotState, "Profile")
		$sEmulator = DllStructGetData($tBotState, "AndroidEmulator")
		$sInstance = DllStructGetData($tBotState, "AndroidInstance")
		$eStructType = DllStructGetData($tBotState, "StructType")
		$pStructPtr = DllStructGetData($tBotState, "StructPtr")
		$hTimerSinceStarted = DllStructGetData($tBotState, "g_hTimerSinceStarted")
		$iTimePassed = DllStructGetData($tBotState, "g_iTimePassed")
	EndIf

	Local $hFrmBotBackend = $g_hFrmBotBackend
	Local $WatchOnlyClientPID = $g_WatchOnlyClientPID
	If $hFrmBotBackend = 0 And $g_sAndroidEmulator = $sEmulator And $g_sAndroidInstance = $sInstance Then
		; found backend bot
		$hFrmBotBackend = $aBotDetails[$g_eBotDetailsBotForm]
		$WatchOnlyClientPID = WinGetProcess($hFrmBotBackend)
	EndIf

	If $hFrmBotBackend = 0 Or $hFrmBotBackend <> $aBotDetails[$g_eBotDetailsBotForm] Then
		; not managed bot
		Return False
	EndIf

	$g_WatchOnlyClientPID = $WatchOnlyClientPID
	$g_hFrmBotBackend = $hFrmBotBackend

	Local $sStatusBar = Default
	Local $AdditionalData

	If $pStructPtr Then
		Switch $eStructType
			Case $g_eSTRUCT_STATUS_BAR
				If $g_iDebugWindowMessages Then SetDebugLog("UpdateManagedMyBot: Update Status Bar: " & $aBotDetails[$g_eBotDetailsBotForm] & ", $pStructPtr=" & $pStructPtr)
				$sStatusBar = DllStructGetData($tOptionalStruct, "Text")
				_GUICtrlStatusBar_SetTextEx($g_hStatusBar, $sStatusBar)
				$AdditionalData = $sStatusBar
			Case $g_eSTRUCT_UPDATE_STATS
				If $g_iDebugWindowMessages Then SetDebugLog("UpdateManagedMyBot: Receive Update Stats: " & $aBotDetails[$g_eBotDetailsBotForm] & ", $pStructPtr=" & $pStructPtr)
				_DllStructLoadData($tOptionalStruct, "g_aiCurrentLoot", $g_aiCurrentLoot)
				_DllStructLoadData($tOptionalStruct, "g_iFreeBuilderCount", $g_iFreeBuilderCount)
				_DllStructLoadData($tOptionalStruct, "g_iTotalBuilderCount", $g_iTotalBuilderCount)
				_DllStructLoadData($tOptionalStruct, "g_iGemAmount", $g_iGemAmount)
				_DllStructLoadData($tOptionalStruct, "g_iStatsTotalGain", $g_iStatsTotalGain)
				_DllStructLoadData($tOptionalStruct, "g_iStatsLastAttack", $g_iStatsLastAttack)
				_DllStructLoadData($tOptionalStruct, "g_iStatsBonusLast", $g_iStatsBonusLast)
				_DllStructLoadData($tOptionalStruct, "g_iFirstAttack", $g_iFirstAttack)
				_DllStructLoadData($tOptionalStruct, "g_aiAttackedCount", $g_aiAttackedCount)
				_DllStructLoadData($tOptionalStruct, "g_iSkippedVillageCount", $g_iSkippedVillageCount)
				$g_iBotAction = $eBotUpdateStats
		EndSwitch
	EndIf

	If $hTimerSinceStarted <> $g_hTimerSinceStarted Then
		$g_hTimerSinceStarted = $hTimerSinceStarted
	EndIf

	If $iTimePassed <> $g_iTimePassed Then
		$g_iTimePassed = $iTimePassed
	EndIf

	If $g_iDebugWindowMessages Then SetDebugLog("UpdateManagedMyBot: " & $aBotDetails[$g_eBotDetailsBotForm] & ", Profile: " & $sProfile & ", Android: " & $sEmulator & ", Instance: " & $sInstance & ", StructType: " & $eStructType & ", Ptr: " & $pStructPtr & ", Data:" & $AdditionalData)

	If $g_sProfileCurrentName <> $sProfile Then
		$g_sProfileCurrentName = $sProfile
		; Set the profile name on the village info group.
		GUICtrlSetData($g_hGrpVillage, GetTranslatedFileIni("MBR GUI Design Bottom", "GrpVillage", "Village") & ": " & $g_sProfileCurrentName)
	EndIf
	If $sEmulator <> "" Then $g_sAndroidEmulator = $sEmulator
	If $sInstance <> "" Then $g_sAndroidInstance = $sInstance

	UpdateBotTitle($sTitle)

	Local $bStartStopInconsistent = (BitAND(GUICtrlGetState($g_hBtnStart), $GUI_SHOW) > 0 And $g_bRunState = True) Or (BitAND(GUICtrlGetState($g_hBtnStop), $GUI_SHOW) > 0 And $g_bRunState = False)

	; Check Start / Stop change
	If $bRunState And (Not $g_bRunState Or $bStartStopInconsistent) Then
		$g_bBotPaused = $bPaused ; update in case bot started and pause
		BotStarted()
	ElseIf Not $bRunState And ($g_bRunState = True Or $bStartStopInconsistent) Then
		BotStopped()
	Else
		; Check Pause change
		If $bPaused And Not $g_bBotPaused Then
			BotPaused()
		ElseIf Not $bPaused And $g_bBotPaused Then
			BotResumed()
		EndIf
	EndIf

	$g_bRunState = $bRunState
	$g_bBotPaused = $bPaused
	$g_bBotLaunched = $bLaunched
	If $bRunState Then
		_MiniWriteLifecycleState($bPaused ? "paused" : "running", $bPaused ? "backend reported paused" : "backend reported running", $g_WatchOnlyClientPID)
	ElseIf $bLaunched Then
		_MiniWriteLifecycleState("ready-idle", "backend reported idle", $g_WatchOnlyClientPID)
	EndIf

	Return True
EndFunc   ;==>UpdateManagedMyBot

; Keep the exact MiniGui parent as the lightweight recovery owner, but present the inherited full
; native configuration surface in the backend. The browser is a control plane; it must not make
; the Village, Attack, Bot, Log, profile, and advanced settings tabs disappear from the product.
Func LaunchBotBackend($bNoGUI = False)
	_MiniWriteLifecycleState("starting", "backend launch requested", 0)

	Local $sParam = ""
	For $i = 1 To $CmdLine[0]
		Switch $CmdLine[$i]
			Case "/ng", "/mg"
				; skip GUI options
			Case "/restart"
				; skip restart
			Case Else
				If $sParam = "" Then
					$sParam = $CmdLine[$i]
				Else
					$sParam &= " " & $CmdLine[$i]
				EndIf
		EndSwitch
	Next

	$sParam = StringStripWS($sParam & ($bNoGUI ? " /ng" : "") & " /guipid=" & @AutoItPID, 3)
	Local $cmd = """" & @ScriptDir & "\MyBot.run.exe"""
	If @Compiled = 0 Then $cmd = """" & @AutoItExe & """ /AutoIt3ExecuteScript """ & @ScriptDir & "\MyBot.run.au3" & """"
	$cmd &= " " & $sParam

	; wait 5 Minutes for bot to complete boot
	Local $hTimer = __TimerInit()
	Local $pid = 0
	Local $bCheck = True

	$g_bBotLaunched = False
	$g_hFrmBotBackend = 0
	$g_WatchOnlyClientPID = Default

	; check if backend bot is already running
	SetLog("Check if backend My Bot process is already running...")
	While __TimerDiff($hTimer) < 5 * 60 * 1000

		If $g_WatchOnlyClientPID = Default And __TimerDiff($hTimer) > $g_iBotBackendFindTimeout Then
			$bCheck = False
			SetLog("My Bot backend process not found, launching now...")
			SetDebugLog("My Bot backend process launching: " & $cmd)
			If $g_bMBRFuncEngineSupervisorValid Then
				EnvSet($g_sMBRFuncEngineTokenEnv, $g_sMBRFuncEngineSupervisorToken)
				EnvSet($g_sMBRFuncEngineLauncherPidEnv, $g_sMBRFuncEngineLauncherPidText)
				EnvSet($g_sMBRFuncEngineLauncherCreatedEnv, $g_sMBRFuncEngineLauncherCreated)
			EndIf
			$pid = Run($cmd, @ScriptDir)
			Local $iRunError = @error
			EnvSet($g_sMBRFuncEngineTokenEnv, "")
			EnvSet($g_sMBRFuncEngineLauncherPidEnv, "")
			EnvSet($g_sMBRFuncEngineLauncherCreatedEnv, "")
			If $pid = 0 Then
				SetLog("Cannot launch My Bot backend process", $COLOR_RED)
				_MiniWriteLifecycleState("failed", "backend process launch failed with error " & $iRunError, 0, True)
				Return 0
			EndIf
			If $g_iDebugSetLog Then
				SetDebugLog("My Bot backend process launched, PID = " & $pid)
			Else
				SetLog("My Bot backend process launched")
			EndIf
			$g_WatchOnlyClientPID = $pid
			_MiniWriteLifecycleState("starting", "backend process launched", $pid, True)
			ClearManagedMyBotDetails()
		EndIf

		If $g_bBotLaunched Then
			If ProcessExists($g_WatchOnlyClientPID) Then
				$pid = $g_WatchOnlyClientPID
				_MiniWriteLifecycleState("ready-idle", "backend reported idle and ready", $pid)
				ExitLoop
			Else
				; launch bot again
				$g_WatchOnlyClientPID = Default
			EndIf
		Else
			If $g_WatchOnlyClientPID <> Default And ProcessExists($g_WatchOnlyClientPID) = 0 Then
				SetDebugLog("My Bot backend process not launched, PID = " & $g_WatchOnlyClientPID)
				$g_WatchOnlyClientPID = Default
			EndIf
		EndIf

		_WinAPI_BroadcastSystemMessage($WM_MYBOTRUN_API, 0x01FF, $g_hFrmBot, $BSF_POSTMESSAGE + $BSF_IGNORECURRENTTASK, $BSM_APPLICATIONS)

		;Local $iActiveBots = GetActiveMyBotCount($iTimeoutBroadcast + 3000)
		;SetDebugLog("Active bots: " & $iActiveBots)
		Sleep(2000)
	WEnd

	If Not $g_bBotLaunched Then
		SetLog("Bot didn't launch in 5 Minutes")
		_MiniWriteLifecycleState("failed", "backend did not report ready before timeout", $pid, True)
	EndIf

	Return $pid

EndFunc   ;==>LaunchBotBackend

Func _MiniLifecycleJsonString($sValue)
	Local $sText = String($sValue)
	$sText = StringReplace($sText, "\", "\\")
	$sText = StringReplace($sText, '"', '\"')
	$sText = StringReplace($sText, @CRLF, "\n")
	$sText = StringReplace($sText, @CR, "\n")
	$sText = StringReplace($sText, @LF, "\n")
	$sText = StringReplace($sText, @TAB, "\t")
	Return '"' & $sText & '"'
EndFunc   ;==>_MiniLifecycleJsonString

Func _MiniLifecycleBool($bValue)
	Return $bValue ? "true" : "false"
EndFunc   ;==>_MiniLifecycleBool

Func _MiniWriteLifecycleState($sState, $sReason = "", $iBackendPid = Default, $bForce = False)
	If $iBackendPid = Default Then $iBackendPid = ($g_WatchOnlyClientPID = Default ? 0 : Int($g_WatchOnlyClientPID))
	If Not $bForce And $sState = $g_sMiniLifecycleLastState And $sReason = $g_sMiniLifecycleLastReason And Int($iBackendPid) = $g_iMiniLifecycleLastBackendPid Then Return True
	Local $bBackendAlive = Int($iBackendPid) > 0 And ProcessExists(Int($iBackendPid))
	Local $sBackendCreated = $bBackendAlive ? _MBRFuncProcessCreationId(Int($iBackendPid)) : ""
	Local $bBackendWindowAttached = $g_hFrmBotBackend <> 0 And Int($iBackendPid) > 0 And WinGetProcess($g_hFrmBotBackend) = Int($iBackendPid)
	Local $sControllerCreated = _MBRFuncProcessCreationId(@AutoItPID)
	Local $sParent = $g_sMBRFuncRuntimeLocalAppData & "\My Bot 2.0"
	DirCreate($sParent)
	Local $sTemporary = $g_sMiniLifecycleReceiptPath & ".tmp." & @AutoItPID
	Local $sJson = "{"
	$sJson &= _MiniLifecycleJsonString("schema_version") & ":1,"
	$sJson &= _MiniLifecycleJsonString("schema") & ":" & _MiniLifecycleJsonString("my-bot-mini-supervisor-lifecycle-v1") & ","
	$sJson &= _MiniLifecycleJsonString("state") & ":" & _MiniLifecycleJsonString($sState) & ","
	$sJson &= _MiniLifecycleJsonString("reason") & ":" & _MiniLifecycleJsonString($sReason) & ","
	$sJson &= _MiniLifecycleJsonString("recorded_at_local") & ":" & _MiniLifecycleJsonString(@YEAR & "-" & @MON & "-" & @MDAY & "T" & @HOUR & ":" & @MIN & ":" & @SEC) & ","
	$sJson &= _MiniLifecycleJsonString("controller_pid") & ":" & @AutoItPID & ","
	$sJson &= _MiniLifecycleJsonString("controller_created") & ":" & _MiniLifecycleJsonString($sControllerCreated) & ","
	$sJson &= _MiniLifecycleJsonString("backend_pid") & ":" & Int($iBackendPid) & ","
	$sJson &= _MiniLifecycleJsonString("backend_created") & ":" & _MiniLifecycleJsonString($sBackendCreated) & ","
	$sJson &= _MiniLifecycleJsonString("backend_alive") & ":" & _MiniLifecycleBool($bBackendAlive) & ","
	$sJson &= _MiniLifecycleJsonString("backend_window_attached") & ":" & _MiniLifecycleBool($bBackendWindowAttached) & ","
	$sJson &= _MiniLifecycleJsonString("profile") & ":" & _MiniLifecycleJsonString($g_sProfileCurrentName) & ","
	$sJson &= _MiniLifecycleJsonString("emulator") & ":" & _MiniLifecycleJsonString($g_sAndroidEmulator) & ","
	$sJson &= _MiniLifecycleJsonString("instance") & ":" & _MiniLifecycleJsonString($g_sAndroidInstance) & ","
	$sJson &= _MiniLifecycleJsonString("recovery_active") & ":" & _MiniLifecycleBool($g_bMiniBackendRecoveryActive) & ","
	$sJson &= _MiniLifecycleJsonString("recovery_delay_ms") & ":" & Int($g_iMiniBackendRecoveryDelayMs) & ","
	$sJson &= _MiniLifecycleJsonString("start_replayed") & ":false"
	$sJson &= "}"
	FileDelete($sTemporary)
	Local $hFile = FileOpen($sTemporary, 10)
	If $hFile = -1 Then Return False
	Local $bWritten = FileWrite($hFile, $sJson)
	Local $bFlushed = FileFlush($hFile)
	FileClose($hFile)
	If Not $bWritten Or Not $bFlushed Then
		FileDelete($sTemporary)
		Return False
	EndIf
	If Not FileMove($sTemporary, $g_sMiniLifecycleReceiptPath, 1) Then
		FileDelete($sTemporary)
		Return False
	EndIf
	$g_sMiniLifecycleLastState = $sState
	$g_sMiniLifecycleLastReason = $sReason
	$g_iMiniLifecycleLastBackendPid = Int($iBackendPid)
	Return True
EndFunc   ;==>_MiniWriteLifecycleState

; The managed backend owns the planner service. If launcher supervision closes a blocked or crashed
; generation, keep the visible controller alive and recreate one exact-path idle backend. Start is
; never replayed: the restored Control Center reconnects in Idle and requires a new user command.
Func _MiniEnsureBackendAvailable()
	If $g_WatchOnlyClientPID <> Default And $g_WatchOnlyClientPID > 0 And ProcessExists($g_WatchOnlyClientPID) Then
		$g_hMiniBackendRecoveryTimer = 0
		_MiniWriteLifecycleState("ready-idle", "backend process is alive", $g_WatchOnlyClientPID)
		Return True
	EndIf
	If $g_bMiniBackendRecoveryActive Then Return False
	If $g_hMiniBackendRecoveryTimer = 0 Then
		$g_hMiniBackendRecoveryTimer = __TimerInit()
		SetLog("Native engine exited; preparing one exact-path recovery generation", $COLOR_WARNING)
		_MiniWriteLifecycleState("recovering", "backend exited; waiting before one exact-path recovery generation", 0, True)
		Return False
	EndIf
	If __TimerDiff($g_hMiniBackendRecoveryTimer) < $g_iMiniBackendRecoveryDelayMs Then Return False

	$g_hMiniBackendRecoveryTimer = __TimerInit()
	$g_bMiniBackendRecoveryActive = True
	_MiniWriteLifecycleState("recovering", "launching one exact-path recovery generation", 0, True)
	Local $iRecoveredPid = LaunchBotBackend()
	$g_bMiniBackendRecoveryActive = False
	If $iRecoveredPid > 0 Then
		$g_hMiniBackendRecoveryTimer = 0
		SetLog("Native engine recovered in Idle; Start was not replayed", $COLOR_SUCCESS)
		_MiniWriteLifecycleState("ready-idle", "backend recovered in Idle; Start was not replayed", $iRecoveredPid, True)
		Return True
	EndIf
	SetLog("Native engine recovery did not become ready; retrying remains bounded by the controller watchdog", $COLOR_ERROR)
	_MiniWriteLifecycleState("failed", "backend recovery did not become ready", $iRecoveredPid, True)
	Return False
EndFunc   ;==>_MiniEnsureBackendAvailable

Func _MiniEngineReceiptString($sReceipt, $sName)
	Local $aValue = StringRegExp($sReceipt, '"' & $sName & '"\s*:\s*"([A-Za-z0-9_-]+)"', $STR_REGEXPARRAYMATCH)
	If @error Or Not IsArray($aValue) Or UBound($aValue) <> 1 Then Return ""
	Return $aValue[0]
EndFunc   ;==>_MiniEngineReceiptString

Func _MiniEngineReceiptInt($sReceipt, $sName)
	Local $aValue = StringRegExp($sReceipt, '"' & $sName & '"\s*:\s*([0-9]+)', $STR_REGEXPARRAYMATCH)
	If @error Or Not IsArray($aValue) Or UBound($aValue) <> 1 Then Return 0
	Return Int($aValue[0])
EndFunc   ;==>_MiniEngineReceiptInt

Func _MiniEngineRequestId($sJson, $sName)
	Local $aValue = StringRegExp($sJson, '"' & $sName & '"\s*:\s*"([A-Za-z0-9._-]{1,80})"', $STR_REGEXPARRAYMATCH)
	If @error Or Not IsArray($aValue) Or UBound($aValue) <> 1 Then Return ""
	Return $aValue[0]
EndFunc   ;==>_MiniEngineRequestId

Func _MiniEngineCancelPathSafe($sPath, $bRequireFile = False)
	Local $sTemporaryPrefix = $g_sMiniEngineInitCancelPath & ".tmp."
	If $sPath <> $g_sMiniEngineInitCancelPath And StringLeft($sPath, StringLen($sTemporaryPrefix)) <> $sTemporaryPrefix Then Return False
	Local $sConfigDir = @ScriptDir & "\config"
	Local $aRoot = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", @ScriptDir)
	If @error Or Not IsArray($aRoot) Or $aRoot[0] = 0xFFFFFFFF Or BitAND($aRoot[0], 0x10) = 0 Or BitAND($aRoot[0], 0x400) <> 0 Then Return False
	Local $aParent = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $sConfigDir)
	If @error Or Not IsArray($aParent) Or $aParent[0] = 0xFFFFFFFF Or BitAND($aParent[0], 0x10) = 0 Or BitAND($aParent[0], 0x400) <> 0 Then Return False
	If Not FileExists($sPath) Then Return Not $bRequireFile
	Local $aFile = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $sPath)
	If @error Or Not IsArray($aFile) Or $aFile[0] = 0xFFFFFFFF Then Return False
	Return BitAND($aFile[0], 0x10) = 0 And BitAND($aFile[0], 0x400) = 0
EndFunc   ;==>_MiniEngineCancelPathSafe

Func _MiniEngineReceiptMatches($sReceipt, ByRef $sStartRequestId)
	$sStartRequestId = ""
	If Not $g_bMBRFuncEngineSupervisorValid Then Return False
	If _MiniEngineReceiptString($sReceipt, "schema") <> $g_sMBRFuncEngineSupervisorSchema Then Return False
	If Not StringRegExp($g_sMBRFuncEngineSupervisorToken, "^[0-9a-f]{64}$") Or _MiniEngineReceiptString($sReceipt, "token") <> $g_sMBRFuncEngineSupervisorToken Then Return False
	Local $iLauncherPid = Int($g_sMBRFuncEngineLauncherPidText)
	If $iLauncherPid <= 0 Or _MiniEngineReceiptInt($sReceipt, "launcher_pid") <> $iLauncherPid Then Return False
	If _MiniEngineReceiptString($sReceipt, "launcher_created") <> $g_sMBRFuncEngineLauncherCreated Or _MBRFuncProcessCreationId($iLauncherPid) <> $g_sMBRFuncEngineLauncherCreated Then Return False
	If _MBRFuncParentPid(@AutoItPID) <> $iLauncherPid Then Return False
	Local $sControllerCreated = _MBRFuncProcessCreationId(@AutoItPID)
	If _MiniEngineReceiptInt($sReceipt, "controller_pid") <> @AutoItPID Or Not StringRegExp($sControllerCreated, "^[0-9a-f]{16}$") Then Return False
	If _MiniEngineReceiptString($sReceipt, "controller_created") <> $sControllerCreated Then Return False
	Local $iBackendPid = _MiniEngineReceiptInt($sReceipt, "backend_pid")
	If $iBackendPid <= 0 Or $iBackendPid <> $g_WatchOnlyClientPID Or Not ProcessExists($iBackendPid) Then Return False
	If $g_hFrmBotBackend = 0 Or WinGetProcess($g_hFrmBotBackend) <> $iBackendPid Then Return False
	Local $sBackendCreated = _MBRFuncProcessCreationId($iBackendPid)
	If Not StringRegExp($sBackendCreated, "^[0-9a-f]{16}$") Or _MiniEngineReceiptString($sReceipt, "backend_created") <> $sBackendCreated Then Return False
	If _MiniEngineReceiptInt($sReceipt, "parent_pid") <> @AutoItPID Or _MBRFuncParentPid($iBackendPid) <> @AutoItPID Then Return False
	Local $sPhase = _MiniEngineReceiptString($sReceipt, "phase")
	If Not StringRegExp($sPhase, "^(prepared|pool-entered|pool-returned|max-entered|max-returned|android-entered|android-returned|gui-entered)$") Then Return False
	If _MiniEngineReceiptInt($sReceipt, "sequence") <= 0 Then Return False
	$sStartRequestId = _MiniEngineRequestId($sReceipt, "start_request_id")
	Return $sStartRequestId <> ""
EndFunc   ;==>_MiniEngineReceiptMatches

Func _MiniEngineNewStopRequestId()
	Local $sRequestId = "mini-stop-" & @AutoItPID & "-" & @YEAR & @MON & @MDAY & @HOUR & @MIN & @SEC & @MSEC & "-" & Random(100000, 999999, 1)
	If Not StringRegExp($sRequestId, "^[A-Za-z0-9._-]{1,80}$") Then Return ""
	Return $sRequestId
EndFunc   ;==>_MiniEngineNewStopRequestId

Func _MiniEngineDeleteTemporary($sPath)
	If Not FileExists($sPath) Then Return True
	If Not _MiniEngineCancelPathSafe($sPath, True) Then Return False
	Return FileDelete($sPath) = 1 Or Not FileExists($sPath)
EndFunc   ;==>_MiniEngineDeleteTemporary

Func _MiniTryWriteEngineInitCancel()
	If Not FileExists($g_sMBRFuncEngineReceiptPath) Or Not _MBRFuncEngineReceiptPathSafe(True) Then Return False
	Local $iReceiptSize = FileGetSize($g_sMBRFuncEngineReceiptPath)
	If @error Or $iReceiptSize <= 0 Or $iReceiptSize > $g_iMiniEngineInitReceiptMaxBytes Then Return False
	Local $sReceipt = FileRead($g_sMBRFuncEngineReceiptPath)
	If @error Or StringLen($sReceipt) <= 0 Or StringLen($sReceipt) > $g_iMiniEngineInitReceiptMaxBytes Then Return False
	Local $sStartRequestId = ""
	If Not _MiniEngineReceiptMatches($sReceipt, $sStartRequestId) Then Return False
	Local $sStopRequestId = _MiniEngineNewStopRequestId()
	If $sStopRequestId = "" Then Return False
	Local $sCancel = '{"schema":"' & $g_sMiniEngineInitCancelSchema & '","token":"' & $g_sMBRFuncEngineSupervisorToken & _
		'","expected_start_request_id":"' & $sStartRequestId & '","stop_request_id":"' & $sStopRequestId & '"}'
	If StringLen($sCancel) <= 0 Or StringLen($sCancel) > $g_iMiniEngineInitCancelMaxBytes Then Return False
	If Not _MiniEngineCancelPathSafe($g_sMiniEngineInitCancelPath, False) Then Return False
	Local $sTemporary = $g_sMiniEngineInitCancelPath & ".tmp." & @AutoItPID & "." & @MSEC & "." & Random(100000, 999999, 1)
	If FileExists($sTemporary) Or Not _MiniEngineCancelPathSafe($sTemporary, False) Then Return False
	Local $hCancel = FileOpen($sTemporary, 10)
	If $hCancel = -1 Then Return False
	Local $bWritten = FileWrite($hCancel, $sCancel) = 1
	Local $bFlushed = FileFlush($hCancel)
	FileClose($hCancel)
	If Not $bWritten Or Not $bFlushed Or Not _MiniEngineCancelPathSafe($sTemporary, True) Then
		_MiniEngineDeleteTemporary($sTemporary)
		Return False
	EndIf
	If Not _MBRFuncEngineReceiptPathSafe(True) Or FileRead($g_sMBRFuncEngineReceiptPath) <> $sReceipt Then
		_MiniEngineDeleteTemporary($sTemporary)
		Return False
	EndIf
	Local $sCurrentStartRequestId = ""
	If Not _MiniEngineReceiptMatches($sReceipt, $sCurrentStartRequestId) Or $sCurrentStartRequestId <> $sStartRequestId Or _
			Not _MiniEngineCancelPathSafe($g_sMiniEngineInitCancelPath, False) Then
		_MiniEngineDeleteTemporary($sTemporary)
		Return False
	EndIf
	If Not FileMove($sTemporary, $g_sMiniEngineInitCancelPath, 1) Then
		_MiniEngineDeleteTemporary($sTemporary)
		Return False
	EndIf
	If Not _MiniEngineCancelPathSafe($g_sMiniEngineInitCancelPath, True) Then Return False
	Return FileGetSize($g_sMiniEngineInitCancelPath) <= $g_iMiniEngineInitCancelMaxBytes And FileRead($g_sMiniEngineInitCancelPath) = $sCancel
EndFunc   ;==>_MiniTryWriteEngineInitCancel

Func BotStart()
	If $g_hFrmBotBackend = 0 Or $g_WatchOnlyClientPID = 0 Or WinGetProcess($g_hFrmBotBackend) <> $g_WatchOnlyClientPID Then
		LaunchBotBackend()
		If Not $g_bBotLaunched Then Return
	EndIf
	GUICtrlSetState($g_hBtnStart, $GUI_DISABLE)
	_MiniWriteLifecycleState("running", "Start command forwarded to owned backend", $g_WatchOnlyClientPID, True)
	_WinAPI_PostMessage($g_hFrmBotBackend, $WM_MYBOTRUN_API, 0x1000, $g_hFrmBot)
EndFunc   ;==>BotStart

Func BotStop()
	If $g_hFrmBotBackend = 0 Or $g_WatchOnlyClientPID = 0 Or WinGetProcess($g_hFrmBotBackend) <> $g_WatchOnlyClientPID Then
		LaunchBotBackend()
		If Not $g_bBotLaunched Then Return
	EndIf
	GUICtrlSetState($g_hBtnStop, $GUI_DISABLE)
	_MiniWriteLifecycleState("stopping", "Stop command forwarded to owned backend", $g_WatchOnlyClientPID, True)
	_MiniTryWriteEngineInitCancel()
	_WinAPI_PostMessage($g_hFrmBotBackend, $WM_MYBOTRUN_API, 0x1010, $g_hFrmBot)
EndFunc   ;==>BotStop

Func btnMakeScreenshot()
	_WinAPI_PostMessage($g_hFrmBotBackend, $WM_MYBOTRUN_API, 0x1050, $g_hFrmBot)
EndFunc   ;==>btnMakeScreenshot

Func TogglePauseImpl($source)
	If $g_bBotPaused Then
		_WinAPI_PostMessage($g_hFrmBotBackend, $WM_MYBOTRUN_API, 0x1020, $g_hFrmBot)
	Else
		_WinAPI_PostMessage($g_hFrmBotBackend, $WM_MYBOTRUN_API, 0x1030, $g_hFrmBot)
	EndIf
EndFunc   ;==>TogglePauseImpl

Func BotClose($SaveConfig = Default, $bExit = True)
	_MiniWriteLifecycleState("stopping", "Mini controller is closing", $g_WatchOnlyClientPID, True)
	_WinAPI_PostMessage($g_hFrmBotBackend, $WM_MYBOTRUN_API, 0x1040, $g_hFrmBot)

	$g_bRunState = False
	$g_bBotPaused = False
	SetLog("Closing " & $g_sBotTitle & " now ...")
	LockBotSlot(False)

	ReleaseMutex($hMutex_BotTitle)
	DllClose("ntdll.dll")

	_GDIPlus_Shutdown()
	_Crypt_Shutdown()
	GUIDelete($g_hFrmBot)

	; Global DllStuctCreate
	$g_aiAndroidAdbScreencapBuffer = 0 ; Allocated in MBR Global Variables.au3
	$g_hStruct_SleepMicro = 0 ; Allocated in MBR Global Variables.au3, used in _Sleep.au3

	; Unregister managing hosts
	;UnregisterManagedMyBotHost()

	If $bExit = True Then Exit
EndFunc   ;==>BotClose

Func ReferenceFunctions()
	If True Then Return
	UpdateManagedMyBot(0)
	GetTroopName(0)
EndFunc   ;==>ReferenceFunctions

Func ReferenceGlobals()
	If True Then Return
EndFunc   ;==>ReferenceGlobals

ProcessCommandLine()

_ITaskBar_Init(False)
_Crypt_Startup()
_GDIPlus_Startup() ; Start GDI+ Engine (incl. a new thread)

$g_iGuiMode = 2
$g_bGuiRemote = True ; GUI Remote flag
$g_WatchDogLogStatusBar = True
$g_iDebugSetLog = 1
;$g_iDebugWindowMessages = 1

#cs
	$hMutex_BotTitle = CreateMutex($sWatchdogMutex)
	If $hMutex_BotTitle = 0 Then
	;MsgBox($MB_OK + $MB_ICONINFORMATION, $sBotTitle, "My Bot Watchdog is already running.")
	Exit
	EndIf
#ce

SetupProfileFolder() ; Setup profile folders

InitAndroidConfig()

; early load of config
If FileExists($g_sProfileConfigPath) Or FileExists($g_sProfileBuildingPath) Then
	readConfig()
EndIf

InitializeAndroid() ; Initialize Android emulator

CreateMainGUI() ; Just create the main window

CreateMainGUIControls() ; Create all GUI Controls

; Launch bot backend process
LaunchBotBackend()

If $g_bBotLaunched Then
	; update stats
	_WinAPI_PostMessage($g_hFrmBotBackend, $WM_MYBOTRUN_API, 0x0200, $g_hFrmBot)
EndIf

;UpdateMainGUI()
GUICtrlSetState($g_hBtnStart, $GUI_ENABLE)

; Show main GUI
ShowMainGUI()

; update GUI PID
_WinAPI_PostMessage($g_hFrmBotBackend, $WM_MYBOTRUN_API, 0x1060, $g_hFrmBot)

; GUI events and messages
GUISetOnEvent($GUI_EVENT_CLOSE, "GUIEvents", $g_hFrmBot)
GUISetOnEvent($GUI_EVENT_MINIMIZE, "GUIEvents", $g_hFrmBot)
GUISetOnEvent($GUI_EVENT_RESTORE, "GUIEvents", $g_hFrmBot)

GUIRegisterMsg($WM_COMMAND, "GUIControl_WM_COMMAND")
GUIRegisterMsg($WM_CLOSE, "GUIControl_WM_CLOSE")
GUIRegisterMsg($WM_MOVE, "GUIControl_WM_MOVE")

;DllCall($g_hLibUser32DLL, "none", "DisableProcessWindowsGhosting")
DllCall("user32.dll", "none", "DisableProcessWindowsGhosting")

Local $hStatusUpdateTimer = 0, $hTimeUpdateTimer = 0
Local $iMainLoop = 1
While 1
	_Sleep($g_iMainLoopSleep, True, False)
	_MiniEnsureBackendAvailable()

	Switch $g_iBotAction
		#cs
			Case $eBotStart
			BotStart()
			If $g_iBotAction = $eBotStart Then $g_iBotAction = $eBotNoAction

			; test error handling when bot started and then stopped
			; force app crash for debugging/testing purposes
			;DllCallAddress("NONE", 0)
			; force au3 script error for debugging/testing purposes
			;Local $iTmp = $iStartDelay[0]

			Case $eBotStop
			BotStop()
			If $g_iBotAction = $eBotStop Then $g_iBotAction = $eBotNoAction
			Case $eBotSearchMode
			;BotSearchMode()
			If $g_iBotAction = $eBotSearchMode Then $g_iBotAction = $eBotNoAction
		#ce
		Case $eBotClose
			BotClose()
		Case $eBotUpdateStats
			UpdateStats()
			$g_iBotAction = $eBotNoAction
		Case Else
			; update status (incl. stats)
			If $iMainLoop > 20 And ($hStatusUpdateTimer = 0 Or __TimerDiff($hStatusUpdateTimer) > $iTimeoutBroadcast) Then
				$iMainLoop = 0
				$hStatusUpdateTimer = __TimerInit()
				_WinAPI_PostMessage($g_hFrmBotBackend, $WM_MYBOTRUN_API, 0x0200, $g_hFrmBot)
			EndIf
			If $hTimeUpdateTimer = 0 Or __TimerDiff($hTimeUpdateTimer) > 750 Then
				SetTime()
				$hTimeUpdateTimer = __TimerInit()
			EndIf
	EndSwitch

	$iMainLoop += 1
WEnd

ReferenceFunctions()
ReferenceGlobals()
