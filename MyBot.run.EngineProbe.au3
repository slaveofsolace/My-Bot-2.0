#NoTrayIcon
#AutoIt3Wrapper_UseX64=n
#include <FileConstants.au3>
#pragma compile(FileDescription, My Bot 2.0 - managed engine compatibility probe)
#include "MyBot.run.version.au3"
#pragma compile(ProductName, My Bot)
#pragma compile(Out, MyBot.run.EngineProbe.exe)

Global Const $ENGINE_PROBE_PROTOCOL = "engine-probe/v2"

If $CmdLine[0] <> 1 Then Exit 2
Local $sTokenPath = $CmdLine[1]
Local $sAllowedPrefix = @ScriptDir & "\config\engine-probe-"
If StringInStr($sTokenPath, $sAllowedPrefix, 0, 1) <> 1 Or StringRight($sTokenPath, 3) <> ".ok" Then Exit 2
Local $sMarkerPath = @ScriptDir & "\MyBot.run.txt"
Local $sLibraryPath = @ScriptDir & "\lib\MyBot.run.dll"
If Not FileExists($sMarkerPath) Or FileGetSize($sMarkerPath) <> 0 Then Exit 3
If Not FileExists($sLibraryPath) Or FileGetSize($sLibraryPath) <= 0 Then Exit 4

; This packaged helper is deliberately a non-CLR integrity canary. The operational backend is the
; only process allowed to load and call the mixed-mode engine, under the resident launcher's exact
; PID/creation-bound supervision. Keeping this helper static prevents a diagnostic invocation from
; recreating the historical unbounded first-export stall in a second process.
If Not _EngineProbePublish($sTokenPath, $ENGINE_PROBE_PROTOCOL & "|static-ready") Then Exit 6
Exit 0

Func _EngineProbePublish($sPath, $sReceipt)
	Local $sTemporary = $sPath & "." & @AutoItPID & ".tmp"
	FileDelete($sTemporary)
	Local $hReceipt = FileOpen($sTemporary, BitOR($FO_OVERWRITE, $FO_CREATEPATH, $FO_UTF8_NOBOM))
	If $hReceipt = -1 Then Return False
	Local $bWritten = FileWrite($hReceipt, $sReceipt & @LF)
	Local $bFlushed = FileFlush($hReceipt)
	FileClose($hReceipt)
	If Not $bWritten Or Not $bFlushed Or Not FileMove($sTemporary, $sPath, $FC_OVERWRITE) Then
		FileDelete($sTemporary)
		Return False
	EndIf
	Return True
EndFunc   ;==>_EngineProbePublish
