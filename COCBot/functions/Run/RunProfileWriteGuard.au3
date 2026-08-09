; #FUNCTION# ====================================================================================================================
; Name ..........: Run profile write guard
; Description ...: Keeps one-run planner overrides out of persistent profile configuration.
; Remarks .......: Regular profile serialization is skipped while overrides are active because Normal GUI saves first
;                  read unchanged controls back into globals, while Mini GUI saves the temporary globals directly.
;                  Clan Games has one planner-owned field, so its serializer receives the captured profile value while
;                  continuing to save unrelated settings and progress.
; ===============================================================================================================================
#include-once

Global $g_bRunExecutionOverridesApplied = False
Global $g_bRunProfileSnapshotReady = False
Global $g_bRunProfileClanGamesEnabled = False
Global $g_bRunProfileAutoLabUpgradeEnabled = False
Global $g_bRunProfileDonateLikeCrazy = False

Func RunProfileOverrideBegin($bClanGamesEnabled, $bAutoLabUpgradeEnabled, $bDonateLikeCrazy)
	$g_bRunProfileClanGamesEnabled = $bClanGamesEnabled
	$g_bRunProfileAutoLabUpgradeEnabled = $bAutoLabUpgradeEnabled
	$g_bRunProfileDonateLikeCrazy = $bDonateLikeCrazy
	$g_bRunProfileSnapshotReady = True
	$g_bRunExecutionOverridesApplied = True
	Return True
EndFunc   ;==>RunProfileOverrideBegin

Func RunProfileOverrideEnd()
	$g_bRunExecutionOverridesApplied = False
	$g_bRunProfileSnapshotReady = False
	$g_bRunProfileClanGamesEnabled = False
	$g_bRunProfileAutoLabUpgradeEnabled = False
	$g_bRunProfileDonateLikeCrazy = False
	Return True
EndFunc   ;==>RunProfileOverrideEnd

Func RunProfileRegularConfigSerializationAllowed()
	Return Not $g_bRunExecutionOverridesApplied
EndFunc   ;==>RunProfileRegularConfigSerializationAllowed

Func RunProfileOverridesActive()
	Return $g_bRunExecutionOverridesApplied
EndFunc   ;==>RunProfileOverridesActive

Func RunProfileClanGamesEnabledForSerialization($bCurrentValue)
	If $g_bRunExecutionOverridesApplied And $g_bRunProfileSnapshotReady Then Return $g_bRunProfileClanGamesEnabled
	Return $bCurrentValue
EndFunc   ;==>RunProfileClanGamesEnabledForSerialization

Func RunProfileAutoLabUpgradeEnabledForSerialization($bCurrentValue)
	If $g_bRunExecutionOverridesApplied And $g_bRunProfileSnapshotReady Then Return $g_bRunProfileAutoLabUpgradeEnabled
	Return $bCurrentValue
EndFunc   ;==>RunProfileAutoLabUpgradeEnabledForSerialization

Func RunProfileDonateLikeCrazyForSerialization($bCurrentValue)
	If $g_bRunExecutionOverridesApplied And $g_bRunProfileSnapshotReady Then Return $g_bRunProfileDonateLikeCrazy
	Return $bCurrentValue
EndFunc   ;==>RunProfileDonateLikeCrazyForSerialization
