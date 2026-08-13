#NoTrayIcon
#AutoIt3Wrapper_UseX64=n
#include <FileConstants.au3>
#pragma compile(FileDescription, My Bot 2.0 - managed engine compatibility probe)
#include "MyBot.run.version.au3"
#pragma compile(ProductName, My Bot)
#pragma compile(Out, MyBot.run.EngineProbe.exe)

Global Const $ENGINE_PROBE_PROTOCOL = "engine-probe/v1"

If $CmdLine[0] <> 1 Then Exit 2
Local $sTokenPath = $CmdLine[1]
Local $sAllowedPrefix = @ScriptDir & "\config\engine-probe-"
If StringInStr($sTokenPath, $sAllowedPrefix, 0, 1) <> 1 Or StringRight($sTokenPath, 3) <> ".ok" Then Exit 2
Local $sPhasePath = $sTokenPath & ".phase"

Local $hLibrary = DllOpen(@ScriptDir & "\lib\MyBot.run.dll")
If $hLibrary = -1 Then Exit 3
If Not _EngineProbePublish($sPhasePath, $ENGINE_PROBE_PROTOCOL & "|opened") Then Exit 5
If Not _EngineProbePublish($sPhasePath, $ENGINE_PROBE_PROTOCOL & "|call-entered") Then Exit 5
Local $aProbe = DllCall($hLibrary, "none", "setProcessingPoolSize", "int", -1)
Local $iProbeError = @error
If $iProbeError Or Not IsArray($aProbe) Then Exit 4

; Publish success as soon as the managed export returns. Do not close the mixed-mode DLL here:
; CLR teardown can block even though the call itself succeeded. The parent owns this exact helper
; PID and will give it a short exit grace, then close it and prove it is gone before accepting success.
If Not _EngineProbePublish($sTokenPath, $ENGINE_PROBE_PROTOCOL & "|call-returned") Then Exit 6
_EngineProbePublish($sPhasePath, $ENGINE_PROBE_PROTOCOL & "|call-returned")
Exit 0

Func _EngineProbePublish($sPath, $sReceipt)
	Local $sTemporary = $sPath & "." & @AutoItPID & ".tmp"
	FileDelete($sTemporary)
	Local $hReceipt = FileOpen($sTemporary, BitOR($FO_OVERWRITE, $FO_CREATEPATH, $FO_UTF8_NOBOM))
	If $hReceipt = -1 Then Return False
	Local $bWritten = FileWrite($hReceipt, $sReceipt & @LF)
	FileFlush($hReceipt)
	FileClose($hReceipt)
	If Not $bWritten Or Not FileMove($sTemporary, $sPath, $FC_OVERWRITE) Then
		FileDelete($sTemporary)
		Return False
	EndIf
	Return True
EndFunc   ;==>_EngineProbePublish
