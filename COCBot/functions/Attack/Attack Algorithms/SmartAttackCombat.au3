; Deterministic Smart Attack combat adapter.
; The legacy standard algorithm remains the actuator. This layer owns only decisions the planner names:
; selected-Hero ability timing and bounded Rage/Freeze use from fresh live-bar coordinates.
; It never guesses a spell target: without a proven enemy Town Hall point inside the live battle diamond,
; spells remain unused and the reason is recorded.

#include-once

Global $g_bSmartCombatActive = False
Global $g_hSmartCombatStarted = 0
Global $g_iSmartCombatEntryX = -1
Global $g_iSmartCombatEntryY = -1
Global $g_iSmartCombatTargetX = -1
Global $g_iSmartCombatTargetY = -1
Global $g_iSmartCombatRageStage = 0
Global $g_iSmartCombatFreezeStage = 0
Global $g_iSmartCombatInitialRage = 0
Global $g_iSmartCombatInitialFreeze = 0
Global $g_iSmartCombatSelectedSide = $SMART_ATTACK_SIDE_NONE
Global $g_bSmartCombatRageHalted = False
Global $g_bSmartCombatFreezeHalted = False
Global $g_bSmartCombatTargetWarningLogged = False
Global $g_aiSmartCombatHeroAttempts[$eHeroCount] = [0, 0, 0, 0, 0]

Func SmartAttackCombatReset()
	$g_bSmartCombatActive = False
	$g_hSmartCombatStarted = 0
	$g_iSmartCombatEntryX = -1
	$g_iSmartCombatEntryY = -1
	$g_iSmartCombatTargetX = -1
	$g_iSmartCombatTargetY = -1
	$g_iSmartCombatRageStage = 0
	$g_iSmartCombatFreezeStage = 0
	$g_iSmartCombatInitialRage = 0
	$g_iSmartCombatInitialFreeze = 0
	$g_iSmartCombatSelectedSide = $SMART_ATTACK_SIDE_NONE
	$g_bSmartCombatRageHalted = False
	$g_bSmartCombatFreezeHalted = False
	$g_bSmartCombatTargetWarningLogged = False
	For $iHero = 0 To $eHeroCount - 1
		$g_aiSmartCombatHeroAttempts[$iHero] = 0
	Next
EndFunc   ;==>SmartAttackCombatReset

Func SmartAttackCombatSelectDeploymentSide()
	If Not RunExecutionSmartAttackEnabled() Then Return False
	Local $iBaseState = $SMART_ATTACK_BASE_UNKNOWN
	If $g_iMatchMode = $LB Then
		$iBaseState = $SMART_ATTACK_BASE_ACTIVE
	ElseIf $g_iMatchMode = $DB Then
		$iBaseState = $SMART_ATTACK_BASE_DEAD
	EndIf
	Local $bUniqueTownHall = $g_bImglocTHUnique And $g_iImglocTHLevel > 0 And $g_iTHx > 0 And $g_iTHy > 0
	Local $aDecision = SmartAttackPolicyChooseSide($g_aiPixelBottomRight, $g_aiPixelBottomLeft, _
			$g_aiPixelTopRight, $g_aiPixelTopLeft, $iBaseState, $bUniqueTownHall, $g_iTHx, $g_iTHy, 10)
	$g_iSmartCombatSelectedSide = Int($aDecision[$SMART_ATTACK_SIDE_RESULT_ID])
	If $g_iSmartCombatSelectedSide = $SMART_ATTACK_SIDE_NONE Then
		SetLog("Smart Attack could not score a valid red-line side; refusing implicit bottom-right fallback", $COLOR_ERROR)
		RunEventLogCombatDecision("Smart side selection failed: no valid red-line side")
		Return False
	EndIf
	Local $sMessage = "Smart side " & $aDecision[$SMART_ATTACK_SIDE_RESULT_NAME] & " selected: " & _
			$aDecision[$SMART_ATTACK_SIDE_RESULT_REASON] & ", points=" & $aDecision[$SMART_ATTACK_SIDE_RESULT_POINT_COUNT] & _
			", median=" & $aDecision[$SMART_ATTACK_SIDE_RESULT_MEDIAN_X] & "," & $aDecision[$SMART_ATTACK_SIDE_RESULT_MEDIAN_Y] & _
			", score=" & $aDecision[$SMART_ATTACK_SIDE_RESULT_SCORE]
	SetLog($sMessage, $COLOR_INFO)
	RunEventLogCombatDecision($sMessage)
	Return True
EndFunc   ;==>SmartAttackCombatSelectDeploymentSide

Func SmartAttackCombatSelectedSide()
	Return $g_iSmartCombatSelectedSide
EndFunc   ;==>SmartAttackCombatSelectedSide

Func SmartAttackCombatStart($iEntryX, $iEntryY)
	SmartAttackCombatReset()
	If Not RunExecutionSmartAttackEnabled() Then Return True

	$g_bSmartCombatActive = True
	$g_hSmartCombatStarted = __TimerInit()
	$g_iSmartCombatEntryX = Int($iEntryX)
	$g_iSmartCombatEntryY = Int($iEntryY)
	; The search may retain its highest-scoring candidate when it found several. Keep that candidate
	; diagnostic-only: the same exact uniqueness proof used by side selection is required before any
	; tactical target can receive a spell click.
	If $g_bImglocTHUnique And $g_iImglocTHLevel > 0 And $g_iTHx > 0 And $g_iTHy > 0 Then
		$g_iSmartCombatTargetX = Int($g_iTHx)
		$g_iSmartCombatTargetY = Int($g_iTHy)
	Else
		$g_iSmartCombatTargetX = -1
		$g_iSmartCombatTargetY = -1
	EndIf

	SmartAttackCombatArmSelectedHeroes()
	If Not _SmartAttackCombatCaptureInitialSpells() Then
		$g_bSmartCombatRageHalted = True
		$g_bSmartCombatFreezeHalted = True
		SetLog("Smart Attack could not establish an initial spell inventory; spell clicks are disabled", $COLOR_WARNING)
	EndIf
	Local $sTarget = "no stable Town Hall target"
	If _SmartAttackCombatTargetValid($g_iSmartCombatTargetX, $g_iSmartCombatTargetY) Then _
		$sTarget = "Town Hall " & $g_iSmartCombatTargetX & "," & $g_iSmartCombatTargetY
	Local $sMessage = "Smart combat started from " & $g_iSmartCombatEntryX & "," & $g_iSmartCombatEntryY & _
			" toward " & $sTarget & "; hero abilities use tactical time/damage milestones"
	SetLog($sMessage, $COLOR_INFO)
	RunEventLogCombatDecision($sMessage)

	; The first Rage is an entry spell. Later spells are paced by elapsed time or observed damage.
	SmartAttackCombatTick(0)
	Return True
EndFunc   ;==>SmartAttackCombatStart

Func _SmartAttackCombatCaptureInitialSpells()
	If Not $g_bRunState Or Not IsAttackPage() Then Return False
	ForceCaptureRegion()
	_CaptureRegion2()
	Local $aLiveBar = GetAttackBar(False, $g_iMatchMode)
	If Not IsArray($aLiveBar) Then Return False
	Local $aRage = SmartAttackPolicySelectAttackBarSlot($aLiveBar, $eRSpell)
	Local $aFreeze = SmartAttackPolicySelectAttackBarSlot($aLiveBar, $eFSpell)
	If $aRage[$SMART_ATTACK_SLOT_FOUND] Then $g_iSmartCombatInitialRage = Int($aRage[$SMART_ATTACK_SLOT_AMOUNT])
	If $aFreeze[$SMART_ATTACK_SLOT_FOUND] Then $g_iSmartCombatInitialFreeze = Int($aFreeze[$SMART_ATTACK_SLOT_AMOUNT])
	SetLog("Smart Attack spell inventory: Rage=" & $g_iSmartCombatInitialRage & ", Freeze=" & _
			$g_iSmartCombatInitialFreeze, $COLOR_INFO)
	Return True
EndFunc   ;==>_SmartAttackCombatCaptureInitialSpells

Func SmartAttackCombatArmSelectedHeroes()
	If Not RunExecutionSmartAttackEnabled() Then Return False
	Local $iMask = $g_aiAttackUseHeroes[$g_iMatchMode]
	If BitAND($iMask, $eHeroKing) = $eHeroKing And $g_bDropKing Then _SmartAttackCombatArmHero($eHeroBarbarianKing)
	If BitAND($iMask, $eHeroQueen) = $eHeroQueen And $g_bDropQueen Then _SmartAttackCombatArmHero($eHeroArcherQueen)
	If BitAND($iMask, $eHeroPrince) = $eHeroPrince And $g_bDropPrince Then _SmartAttackCombatArmHero($eHeroMinionPrince)
	If BitAND($iMask, $eHeroWarden) = $eHeroWarden And $g_bDropWarden Then _SmartAttackCombatArmHero($eHeroGrandWarden)
	If BitAND($iMask, $eHeroChampion) = $eHeroChampion And $g_bDropChampion Then _SmartAttackCombatArmHero($eHeroRoyalChampion)
	Return True
EndFunc   ;==>SmartAttackCombatArmSelectedHeroes

Func _SmartAttackCombatArmHero($iHero)
	Switch $iHero
		Case $eHeroBarbarianKing
			$g_bCheckKingPower = True
		Case $eHeroArcherQueen
			$g_bCheckQueenPower = True
		Case $eHeroMinionPrince
			$g_bCheckPrincePower = True
		Case $eHeroGrandWarden
			$g_bCheckWardenPower = True
		Case $eHeroRoyalChampion
			$g_bCheckChampionPower = True
		Case Else
			Return False
	EndSwitch
	If $g_aHeroesTimerActivation[$iHero] = 0 Then $g_aHeroesTimerActivation[$iHero] = __TimerInit()
	Return True
EndFunc   ;==>_SmartAttackCombatArmHero

Func SmartAttackCombatTick($iDamagePercent = -1)
	If Not $g_bSmartCombatActive Or Not RunExecutionSmartAttackEnabled() Then Return False
	If Not $g_bRunState Or Not IsAttackPage() Then Return False
	Local $iElapsedMs = Int(__TimerDiff($g_hSmartCombatStarted))
	Local $iDamage = Int($iDamagePercent)
	If $iDamage < 0 Then $iDamage = Int($g_iPercentageDamage)
	_SmartAttackCombatCastDueRage($iElapsedMs, $iDamage)
	_SmartAttackCombatCastDueFreeze($iElapsedMs, $iDamage)
	Return True
EndFunc   ;==>SmartAttackCombatTick

Func SmartAttackCombatTickHeroes($iDamagePercent = -1, $bFinalOpportunity = False)
	If Not $g_bSmartCombatActive Or Not RunExecutionSmartAttackEnabled() Then Return False
	If Not $g_bRunState Or Not IsAttackPage() Then Return False
	Local $iDamage = Int($iDamagePercent)
	If $iDamage < 0 Then $iDamage = Int($g_iPercentageDamage)
	For $iHero = 0 To $eHeroCount - 1
		If Not _SmartAttackCombatHeroArmed($iHero) Then ContinueLoop
		Local $iElapsedMs = 0
		If $g_aHeroesTimerActivation[$iHero] <> 0 Then $iElapsedMs = Int(__TimerDiff($g_aHeroesTimerActivation[$iHero]))
		Local $sReason = SmartAttackPolicyHeroAbilityReason($iHero, $iElapsedMs, $iDamage)
		If $bFinalOpportunity And $sReason = "" Then $sReason = "battle-end deadline"
		If $sReason <> "" Then _SmartAttackCombatActivateHero($iHero, $sReason, $iElapsedMs, $iDamage)
	Next
	Return True
EndFunc   ;==>SmartAttackCombatTickHeroes

Func _SmartAttackCombatHeroArmed($iHero)
	Switch $iHero
		Case $eHeroBarbarianKing
			Return $g_bCheckKingPower
		Case $eHeroArcherQueen
			Return $g_bCheckQueenPower
		Case $eHeroMinionPrince
			Return $g_bCheckPrincePower
		Case $eHeroGrandWarden
			Return $g_bCheckWardenPower
		Case $eHeroRoyalChampion
			Return $g_bCheckChampionPower
	EndSwitch
	Return False
EndFunc   ;==>_SmartAttackCombatHeroArmed

Func _SmartAttackCombatHeroImage($iHero)
	Switch $iHero
		Case $eHeroBarbarianKing
			Return $g_sImgKingBar
		Case $eHeroArcherQueen
			Return $g_sImgQueenBar
		Case $eHeroMinionPrince
			Return $g_sImgPrinceBar
		Case $eHeroGrandWarden
			Return $g_sImgWardenBar
		Case $eHeroRoyalChampion
			Return $g_sImgChampionBar
	EndSwitch
	Return ""
EndFunc   ;==>_SmartAttackCombatHeroImage

Func _SmartAttackCombatDisableHero($iHero)
	Switch $iHero
		Case $eHeroBarbarianKing
			$g_bCheckKingPower = False
		Case $eHeroArcherQueen
			$g_bCheckQueenPower = False
		Case $eHeroMinionPrince
			$g_bCheckPrincePower = False
		Case $eHeroGrandWarden
			$g_bCheckWardenPower = False
		Case $eHeroRoyalChampion
			$g_bCheckChampionPower = False
	EndSwitch
	$g_aHeroesTimerActivation[$iHero] = 0
EndFunc   ;==>_SmartAttackCombatDisableHero

Func _SmartAttackCombatActivateHero($iHero, $sReason, $iElapsedMs, $iDamagePercent)
	Local $sImage = _SmartAttackCombatHeroImage($iHero)
	If $sImage = "" Then Return False
	ForceCaptureRegion()
	Local $aAbility = decodeSingleCoord(FindImageInPlace2($g_asHeroShortNames[$iHero] & "Ability", $sImage, _
			0, 570 + $g_iBottomOffsetY, 858, 638 + $g_iBottomOffsetY, True))
	If Not IsArray($aAbility) Or UBound($aAbility) <> 2 Then
		$g_aiSmartCombatHeroAttempts[$iHero] += 1
		If $g_aiSmartCombatHeroAttempts[$iHero] >= 3 Then
			Local $sMissing = "Smart Attack could not find " & $g_asHeroNames[$iHero] & _
					" ability after three fresh checks; no blind portrait click was sent"
			SetLog($sMissing, $COLOR_WARNING)
			RunEventLogHeroAbility($g_asHeroNames[$iHero], "not available after three fresh checks", "warning")
			_SmartAttackCombatDisableHero($iHero)
		EndIf
		Return False
	EndIf

	_SmartAttackCombatExactClick($aAbility[0], $aAbility[1], 2, "SmartHeroAbility-" & $g_asHeroShortNames[$iHero])
	Local $sReceipt = $sReason & "; elapsed_ms=" & Int($iElapsedMs) & "; destruction=" & Int($iDamagePercent)
	Local $sMessage = "Smart Attack issued " & $g_asHeroNames[$iHero] & " ability command: " & $sReceipt
	SetLog($sMessage, $COLOR_ACTION)
	RunEventLogHeroAbility($g_asHeroNames[$iHero], $sReceipt)
	_SmartAttackCombatDisableHero($iHero)
	Return True
EndFunc   ;==>_SmartAttackCombatActivateHero

Func _SmartAttackCombatTargetValid($iX, $iY)
	If $iX <= 0 Or $iX >= $g_iGAME_WIDTH Or $iY <= 0 Or $iY > 555 + $g_iBottomOffsetY Then Return False
	Local $aPoint[2] = [Int($iX), Int($iY)]
	Local $aDecision = SmartAttackPolicyTargetSafetyDecision($aPoint, isInsideDiamondRedArea($aPoint))
	Return $aDecision[$SMART_ATTACK_TARGET_SAFE]
EndFunc   ;==>_SmartAttackCombatTargetValid

Func _SmartAttackCombatCastDueRage($iElapsedMs, $iDamage)
	If $g_bSmartCombatRageHalted Or $g_iSmartCombatRageStage >= 3 Then Return
	Local $bTargetSafe = _SmartAttackCombatTargetValid($g_iSmartCombatTargetX, $g_iSmartCombatTargetY)
	If Not $bTargetSafe Then
		_SmartAttackCombatRetainSpells("Rage", "enemy Town Hall target was not proven")
		$g_bSmartCombatRageHalted = True
		Return
	EndIf
	Local $aDecision = SmartAttackPolicyRageDecision($g_iSmartCombatRageStage, $g_iSmartCombatInitialRage, _
			$iElapsedMs, $bTargetSafe)
	If Not $aDecision[$SMART_ATTACK_SPELL_CAST] Then
		If $aDecision[$SMART_ATTACK_SPELL_REASON] = "no-spell-available" Or _
				$aDecision[$SMART_ATTACK_SPELL_REASON] = "schedule-exhausted" Then $g_iSmartCombatRageStage = 3
		Return
	EndIf
	Local $aTarget = SmartAttackPolicyTargetPoint($g_iSmartCombatEntryX, $g_iSmartCombatEntryY, _
			$g_iSmartCombatTargetX, $g_iSmartCombatTargetY, $aDecision[$SMART_ATTACK_SPELL_TARGET_PROGRESS])
	If Not IsArray($aTarget) Or UBound($aTarget) <> 2 Or Not _SmartAttackCombatTargetValid($aTarget[0], $aTarget[1]) Then
		_SmartAttackCombatRetainSpells("Rage", "computed path target was outside the proven battle diamond")
		$g_bSmartCombatRageHalted = True
		Return
	EndIf
	Local $sOutcome = ""
	If _SmartAttackCombatCastSpell($eRSpell, "Rage", $aTarget[0], $aTarget[1], _
			"path stage " & ($g_iSmartCombatRageStage + 1), $sOutcome) Then
		If $sOutcome = "empty" Then
			$g_iSmartCombatRageStage = 3
		Else
			$g_iSmartCombatRageStage += 1
		EndIf
	Else
		$g_bSmartCombatRageHalted = True
	EndIf
EndFunc   ;==>_SmartAttackCombatCastDueRage

Func _SmartAttackCombatCastDueFreeze($iElapsedMs, $iDamage)
	If $g_bSmartCombatFreezeHalted Or $g_iSmartCombatFreezeStage >= 5 Then Return
	Local $bTargetSafe = _SmartAttackCombatTargetValid($g_iSmartCombatTargetX, $g_iSmartCombatTargetY)
	If Not $bTargetSafe Then
		_SmartAttackCombatRetainSpells("Freeze", "enemy Town Hall target was not proven")
		$g_bSmartCombatFreezeHalted = True
		Return
	EndIf
	Local $aDecision = SmartAttackPolicyFreezeDecision($g_iSmartCombatFreezeStage, $g_iSmartCombatInitialFreeze, _
			$iElapsedMs, $bTargetSafe)
	If Not $aDecision[$SMART_ATTACK_SPELL_CAST] Then
		If $aDecision[$SMART_ATTACK_SPELL_REASON] = "no-spell-available" Then $g_iSmartCombatFreezeStage = 5
		Return
	EndIf
	Local $sOutcome = ""
	If _SmartAttackCombatCastSpell($eFSpell, "Freeze", $g_iSmartCombatTargetX, $g_iSmartCombatTargetY, _
			"core interval " & ($g_iSmartCombatFreezeStage + 1), $sOutcome) Then
		If $sOutcome = "empty" Then
			$g_iSmartCombatFreezeStage = 5
		Else
			$g_iSmartCombatFreezeStage += 1
		EndIf
	Else
		$g_bSmartCombatFreezeHalted = True
	EndIf
EndFunc   ;==>_SmartAttackCombatCastDueFreeze

Func _SmartAttackCombatCastSpell($iSpellType, $sSpellName, $iTargetX, $iTargetY, $sReason, ByRef $sOutcome)
	$sOutcome = "failed"
	Local $bScanValid = False, $bFound = False, $iAmount = 0, $iPortraitX = 0, $iPortraitY = 0
	_SmartAttackCombatReadSpell($iSpellType, $bScanValid, $bFound, $iAmount, $iPortraitX, $iPortraitY)
	If Not $bScanValid Then
		_SmartAttackCombatRetainSpells($sSpellName, "live attack bar could not be read")
		Return False
	EndIf
	If Not $bFound Or $iAmount <= 0 Then
		$sOutcome = "empty"
		Return True
	EndIf

	SetLog("Smart Attack casting " & $sSpellName & " at " & $iTargetX & "," & $iTargetY & _
			" (" & $sReason & ", " & $iAmount & " before)", $COLOR_ACTION)
	_SmartAttackCombatExactClick($iPortraitX, $iPortraitY, 1, "SmartSpellSelect-" & $sSpellName)
	If _Sleep(120, False) Then Return False
	AttackRemainingTime(False)
	_SmartAttackCombatExactClick($iTargetX, $iTargetY, 1, "SmartSpellCast-" & $sSpellName)
	If _Sleep(450, False) Then Return False

	Local $bAfterValid = False, $bAfterFound = False, $iAfter = 0, $iAfterX = 0, $iAfterY = 0
	_SmartAttackCombatReadSpell($iSpellType, $bAfterValid, $bAfterFound, $iAfter, $iAfterX, $iAfterY)
	Local $bNeedSecondAbsenceProof = $bAfterValid And Not $bAfterFound And $iAmount = 1
	If Not $bAfterValid Or $bNeedSecondAbsenceProof Then
		; One bounded retry covers a transient spell animation. A final portrait disappearance is
		; accepted only after two independent valid absence scans; no second cast is sent.
		If _Sleep(300, False) Then Return False
		_SmartAttackCombatReadSpell($iSpellType, $bAfterValid, $bAfterFound, $iAfter, $iAfterX, $iAfterY)
	EndIf
	; A portrait may disappear only when the final spell was consumed. If the pre-cast stack was
	; larger than one, an absent row is an unreadable result, not proof that the whole stack vanished.
	If Not $bAfterValid Or (Not $bAfterFound And $iAmount > 1) Or ($bAfterFound And $iAfter >= $iAmount) Then
		Local $sFailure = $sSpellName & " cast was not proven; before=" & $iAmount & ", after=" & _
				($bAfterValid ? $iAfter : -1) & ". Further " & $sSpellName & " clicks are disabled"
		SetLog($sFailure, $COLOR_ERROR)
		RunEventLogSpellRetained($sSpellName, "post-cast quantity did not decrease")
		Return False
	EndIf

	$sOutcome = "cast"
	RunEventLogSpellCast($sSpellName, $iTargetX, $iTargetY, $sReason & "; quantity " & $iAmount & "->" & _
			($bAfterFound ? $iAfter : 0))
	SetLog("Smart Attack proved " & $sSpellName & " quantity " & $iAmount & " -> " & _
			($bAfterFound ? $iAfter : 0), $COLOR_SUCCESS)
	Return True
EndFunc   ;==>_SmartAttackCombatCastSpell

Func _SmartAttackCombatReadSpell($iSpellType, ByRef $bScanValid, ByRef $bFound, ByRef $iAmount, ByRef $iX, ByRef $iY)
	$bScanValid = False
	$bFound = False
	$iAmount = 0
	$iX = 0
	$iY = 0
	If Not $g_bRunState Or Not IsAttackPage() Then Return False
	ForceCaptureRegion()
	_CaptureRegion2()
	Local $aLiveBar = GetAttackBar(False, $g_iMatchMode)
	If Not IsArray($aLiveBar) Then Return False
	$bScanValid = True
	Local $aSlot = SmartAttackPolicySelectAttackBarSlot($aLiveBar, $iSpellType)
	$bFound = $aSlot[$SMART_ATTACK_SLOT_FOUND]
	If $bFound Then
		$iAmount = Int($aSlot[$SMART_ATTACK_SLOT_AMOUNT])
		$iX = Int($aSlot[$SMART_ATTACK_SLOT_X])
		$iY = Int($aSlot[$SMART_ATTACK_SLOT_Y])
	EndIf
	Return True
EndFunc   ;==>_SmartAttackCombatReadSpell

Func _SmartAttackCombatExactClick($iX, $iY, $iTimes, $sTag)
	Local $bRandomClick = $g_bUseRandomClick
	$g_bUseRandomClick = False
	PureClick(Int($iX), Int($iY), Int($iTimes), 120, $sTag)
	$g_bUseRandomClick = $bRandomClick
EndFunc   ;==>_SmartAttackCombatExactClick

Func _SmartAttackCombatRetainSpells($sSpellName, $sReason)
	Local $sMessage = "Smart Attack retained " & $sSpellName & ": " & $sReason
	SetLog($sMessage, $COLOR_WARNING)
	RunEventLogSpellRetained($sSpellName, $sReason)
EndFunc   ;==>_SmartAttackCombatRetainSpells
