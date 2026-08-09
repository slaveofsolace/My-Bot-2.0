#NoTrayIcon
#AutoIt3Wrapper_UseX64=n
#include <FileConstants.au3>
#pragma compile(FileDescription, My Bot 2.0 - managed engine compatibility probe)
#include "MyBot.run.version.au3"
#pragma compile(ProductName, My Bot)
#pragma compile(Out, MyBot.run.EngineProbe.exe)

If $CmdLine[0] <> 1 Then Exit 2
Local $sTokenPath = $CmdLine[1]
Local $sAllowedPrefix = @ScriptDir & "\config\engine-probe-"
If StringInStr($sTokenPath, $sAllowedPrefix, 0, 1) <> 1 Or StringRight($sTokenPath, 3) <> ".ok" Then Exit 2

Local $hLibrary = DllOpen(@ScriptDir & "\lib\MyBot.run.dll")
If $hLibrary = -1 Then Exit 3
Local $aProbe = DllCall($hLibrary, "none", "setProcessingPoolSize", "int", -1)
Local $iProbeError = @error
DllClose($hLibrary)
If $iProbeError Or Not IsArray($aProbe) Then Exit 4

Local $sTemporary = $sTokenPath & "." & @AutoItPID & ".tmp"
Local $hToken = FileOpen($sTemporary, BitOR($FO_OVERWRITE, $FO_CREATEPATH, $FO_UTF8_NOBOM))
If $hToken = -1 Then Exit 5
Local $bWritten = FileWrite($hToken, "ok" & @LF)
FileFlush($hToken)
FileClose($hToken)
If Not $bWritten Or Not FileMove($sTemporary, $sTokenPath, $FC_OVERWRITE) Then
	FileDelete($sTemporary)
	Exit 6
EndIf
Exit 0
