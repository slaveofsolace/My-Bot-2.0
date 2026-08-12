; #FUNCTION# ====================================================================================================================
; Name ..........: algorith_AllTroops
; Description ...: This file contens all functions to attack algorithm will all Troops , using Barbarians, Archers, Goblins, Giants and Wallbreakers as they are available
; Syntax ........: algorithm_AllTroops()
; Parameters ....: None
; Return values .: None
; Author ........:
; Modified ......: Didipe (05-2015), ProMac(2016), MonkeyHunter(03-2017)
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; Related .......:
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......: No
; ===============================================================================================================================

Func algorithm_AllTroops() ;Attack Algorithm for all existing troops
	If $g_bDebugSetLog Then SetDebugLog("algorithm_AllTroops()", $COLOR_DEBUG)
	SmartAttackCombatReset()
	SetSlotSpecialTroops()
	If RunExecutionStandardDeploymentProofRequired() Then RunExecutionResetDeploymentProof(_AttackDeployableTroopCount())

	If _Sleep($DELAYALGORITHM_ALLTROOPS1) Then Return

	If Not SmartAttackStrategy($g_iMatchMode) Then
		SetLog("Attack geometry was not proven; no deployment clicks were sent", $COLOR_ERROR)
		Return
	EndIf

	Local $nbSides = 0
	Switch $g_aiAttackStdDropSides[$g_iMatchMode]
		Case 0 ;Single sides ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
			SetLog("Attacking on a single side", $COLOR_INFO)
			$nbSides = 1
		Case 1 ;Two sides ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
			SetLog("Attacking on two sides", $COLOR_INFO)
			$nbSides = 2
		Case 2 ;Three sides ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
			SetLog("Attacking on three sides", $COLOR_INFO)
			$nbSides = 3
		Case 3 ;All sides ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
			SetLog("Attacking on all sides", $COLOR_INFO)
			$nbSides = 4
		Case 4 ;DE Side - Live Base only ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
			SetLog("Attacking on Dark Elixir Side.", $COLOR_INFO)
			$nbSides = 1
			If Not ($g_abAttackStdSmartAttack[$g_iMatchMode]) Then GetBuildingEdge($eSideBuildingDES) ; Get DE Storage side when Redline is not used.
		Case 5 ;TH Side - Live Base only ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
			SetLog("Attacking on Town Hall Side.", $COLOR_INFO)
			$nbSides = 1
			If Not ($g_abAttackStdSmartAttack[$g_iMatchMode]) Then GetBuildingEdge($eSideBuildingTH) ; Get Townhall side when Redline is not used.
	EndSwitch
	If ($nbSides = 0) Then Return
	If _Sleep($DELAYALGORITHM_ALLTROOPS2) Then Return

	$g_iSidesAttack = $nbSides

	; Reset the deploy Giants points , spread along red line
	$g_iSlotsGiants = 0
	Local $GiantComp = 0
	; Giants quantities
	For $i = 0 To UBound($g_avAttackTroops) - 1
		If $g_avAttackTroops[$i][0] = $eGiant Then
			$GiantComp = $g_avAttackTroops[$i][1]
		EndIf
	Next

	; Lets select the deploy points according by Giants qunatities & sides
	; Deploy points : 0 - spreads along the red line , 1 - one deploy point .... X - X deploy points
	Switch $GiantComp
		Case 0 To 10
			$g_iSlotsGiants = 2
		Case Else
			Switch $nbSides
				Case 1 To 2
					$g_iSlotsGiants = 4
				Case Else
					$g_iSlotsGiants = 0
			EndSwitch
	EndSwitch

	; $ListInfoDeploy = [Troop, No. of Sides, $WaveNb, $MaxWaveNb, $slotsPerEdge]
	If $g_iMatchMode = $LB And $g_aiAttackStdDropSides[$LB] = 4 Then ; Customise DE side wave deployment here
		Switch $g_aiAttackStdDropOrder[$g_iMatchMode]
			Case 0
				If $g_bCustomDropOrderEnable Then
					Local $listInfoDeploy[48][5] = [[MatchTroopDropName(0), MatchSidesDrop(0), MatchTroopWaveNb(0), 1, MatchSlotsPerEdge(0)], _
							[MatchTroopDropName(1), MatchSidesDrop(1), MatchTroopWaveNb(1), 1, MatchSlotsPerEdge(1)], _
							[MatchTroopDropName(2), MatchSidesDrop(2), MatchTroopWaveNb(2), 1, MatchSlotsPerEdge(2)], _
							[MatchTroopDropName(3), MatchSidesDrop(3), MatchTroopWaveNb(3), 1, MatchSlotsPerEdge(3)], _
							[MatchTroopDropName(4), MatchSidesDrop(4), MatchTroopWaveNb(4), 1, MatchSlotsPerEdge(4)], _
							[MatchTroopDropName(5), MatchSidesDrop(5), MatchTroopWaveNb(5), 1, MatchSlotsPerEdge(5)], _
							[MatchTroopDropName(6), MatchSidesDrop(6), MatchTroopWaveNb(6), 1, MatchSlotsPerEdge(6)], _
							[MatchTroopDropName(7), MatchSidesDrop(7), MatchTroopWaveNb(7), 1, MatchSlotsPerEdge(7)], _
							[MatchTroopDropName(8), MatchSidesDrop(8), MatchTroopWaveNb(8), 1, MatchSlotsPerEdge(8)], _
							[MatchTroopDropName(9), MatchSidesDrop(9), MatchTroopWaveNb(9), 1, MatchSlotsPerEdge(9)], _
							[MatchTroopDropName(10), MatchSidesDrop(10), MatchTroopWaveNb(10), 1, MatchSlotsPerEdge(10)], _
							[MatchTroopDropName(11), MatchSidesDrop(11), MatchTroopWaveNb(11), 1, MatchSlotsPerEdge(11)], _
							[MatchTroopDropName(12), MatchSidesDrop(12), MatchTroopWaveNb(12), 1, MatchSlotsPerEdge(12)], _
							[MatchTroopDropName(13), MatchSidesDrop(13), MatchTroopWaveNb(13), 1, MatchSlotsPerEdge(13)], _
							[MatchTroopDropName(14), MatchSidesDrop(14), MatchTroopWaveNb(14), 1, MatchSlotsPerEdge(14)], _
							[MatchTroopDropName(15), MatchSidesDrop(15), MatchTroopWaveNb(15), 1, MatchSlotsPerEdge(15)], _
							[MatchTroopDropName(16), MatchSidesDrop(16), MatchTroopWaveNb(16), 1, MatchSlotsPerEdge(16)], _
							[MatchTroopDropName(17), MatchSidesDrop(17), MatchTroopWaveNb(17), 1, MatchSlotsPerEdge(17)], _
							[MatchTroopDropName(18), MatchSidesDrop(18), MatchTroopWaveNb(18), 1, MatchSlotsPerEdge(18)], _
							[MatchTroopDropName(19), MatchSidesDrop(19), MatchTroopWaveNb(19), 1, MatchSlotsPerEdge(19)], _
							[MatchTroopDropName(20), MatchSidesDrop(20), MatchTroopWaveNb(20), 1, MatchSlotsPerEdge(20)], _
							[MatchTroopDropName(21), MatchSidesDrop(21), MatchTroopWaveNb(21), 1, MatchSlotsPerEdge(21)], _
							[MatchTroopDropName(22), MatchSidesDrop(22), MatchTroopWaveNb(22), 1, MatchSlotsPerEdge(22)], _
							[MatchTroopDropName(23), MatchSidesDrop(23), MatchTroopWaveNb(23), 1, MatchSlotsPerEdge(23)], _
							[MatchTroopDropName(24), MatchSidesDrop(24), MatchTroopWaveNb(24), 1, MatchSlotsPerEdge(24)], _
							[MatchTroopDropName(25), MatchSidesDrop(25), MatchTroopWaveNb(25), 1, MatchSlotsPerEdge(25)], _
							[MatchTroopDropName(26), MatchSidesDrop(26), MatchTroopWaveNb(26), 1, MatchSlotsPerEdge(26)], _
							[MatchTroopDropName(27), MatchSidesDrop(27), MatchTroopWaveNb(27), 1, MatchSlotsPerEdge(27)], _
							[MatchTroopDropName(28), MatchSidesDrop(28), MatchTroopWaveNb(28), 1, MatchSlotsPerEdge(28)], _
							[MatchTroopDropName(29), MatchSidesDrop(29), MatchTroopWaveNb(29), 1, MatchSlotsPerEdge(29)], _
							[MatchTroopDropName(30), MatchSidesDrop(30), MatchTroopWaveNb(30), 1, MatchSlotsPerEdge(30)], _
							[MatchTroopDropName(31), MatchSidesDrop(31), MatchTroopWaveNb(31), 1, MatchSlotsPerEdge(31)], _
							[MatchTroopDropName(32), MatchSidesDrop(32), MatchTroopWaveNb(32), 1, MatchSlotsPerEdge(32)], _
							[MatchTroopDropName(33), MatchSidesDrop(33), MatchTroopWaveNb(33), 1, MatchSlotsPerEdge(33)], _
							[MatchTroopDropName(34), MatchSidesDrop(34), MatchTroopWaveNb(34), 1, MatchSlotsPerEdge(34)], _
							[MatchTroopDropName(35), MatchSidesDrop(35), MatchTroopWaveNb(35), 1, MatchSlotsPerEdge(35)], _
							[MatchTroopDropName(36), MatchSidesDrop(36), MatchTroopWaveNb(36), 1, MatchSlotsPerEdge(36)], _
							[MatchTroopDropName(37), MatchSidesDrop(37), MatchTroopWaveNb(37), 1, MatchSlotsPerEdge(37)], _
							[MatchTroopDropName(38), MatchSidesDrop(38), MatchTroopWaveNb(38), 1, MatchSlotsPerEdge(38)], _
							[MatchTroopDropName(39), MatchSidesDrop(39), MatchTroopWaveNb(39), 1, MatchSlotsPerEdge(39)], _
							[MatchTroopDropName(40), MatchSidesDrop(40), MatchTroopWaveNb(40), 1, MatchSlotsPerEdge(40)], _
							[MatchTroopDropName(41), MatchSidesDrop(41), MatchTroopWaveNb(41), 1, MatchSlotsPerEdge(41)], _
							[MatchTroopDropName(42), MatchSidesDrop(42), MatchTroopWaveNb(42), 1, MatchSlotsPerEdge(42)], _
							[MatchTroopDropName(43), MatchSidesDrop(43), MatchTroopWaveNb(43), 1, MatchSlotsPerEdge(43)], _
							[MatchTroopDropName(44), MatchSidesDrop(44), MatchTroopWaveNb(44), 1, MatchSlotsPerEdge(44)], _
							[MatchTroopDropName(45), MatchSidesDrop(45), MatchTroopWaveNb(45), 1, MatchSlotsPerEdge(45)], _
							[MatchTroopDropName(46), MatchSidesDrop(46), MatchTroopWaveNb(46), 1, MatchSlotsPerEdge(46)], _
							[MatchTroopDropName(47), MatchSidesDrop(47), MatchTroopWaveNb(47), 1, MatchSlotsPerEdge(47)]]
				Else
					Local $listInfoDeploy[48][5] = [[$eGole, $nbSides, 1, 1, 2] _
							, [$eIceG, $nbSides, 1, 1, 2] _
							, [$eLava, $nbSides, 1, 1, 2] _
							, [$eYeti, $nbSides, 1, 1, 2] _
							, [$eIceH, $nbSides, 1, 1, 2] _
							, [$eGiant, $nbSides, 1, 1, $g_iSlotsGiants] _
							, [$eSGiant, $nbSides, 1, 1, $g_iSlotsGiants] _
							, [$eDrag, $nbSides, 1, 1, 0] _
							, [$eSDrag, $nbSides, 1, 1, 0] _
							, ["CC", 1, 1, 1, 1] _
							, [$eBall, $nbSides, 1, 1, 0] _
							, [$eRBall, $nbSides, 1, 1, 0] _
							, [$eBabyD, $nbSides, 1, 1, 1] _
							, [$eInfernoD, $nbSides, 1, 1, 1] _
							, [$eHogs, $nbSides, 1, 1, 1] _
							, [$eSHogs, $nbSides, 1, 1, 1] _
							, [$eValk, $nbSides, 1, 1, 0] _
							, [$eSValk, $nbSides, 1, 1, 0] _
							, [$eBowl, $nbSides, 1, 1, 0] _
							, [$eSBowl, $nbSides, 1, 1, 0] _
							, [$eHunt, $nbSides, 1, 1, 0] _
							, [$eAppWard, $nbSides, 1, 1, 0] _
							, [$eDruid, $nbSides, 1, 1, 0] _
							, [$eFurn, $nbSides, 1, 1, 0] _
							, [$eMine, $nbSides, 1, 1, 0] _
							, [$eSMine, $nbSides, 1, 1, 0] _
							, [$eEDrag, $nbSides, 1, 1, 0] _
							, [$eRDrag, $nbSides, 1, 1, 0] _
							, [$eETitan, $nbSides, 1, 1, 0] _
							, [$eRootR, $nbSides, 1, 1, 0] _
							, [$eThrower, $nbSides, 1, 1, 0] _
							, [$eBarb, $nbSides, 1, 1, 0] _
							, [$eSBarb, $nbSides, 1, 1, 0] _
							, [$eWall, $nbSides, 1, 1, 1] _
							, [$eSWall, $nbSides, 1, 1, 1] _
							, [$eArch, $nbSides, 1, 1, 0] _
							, [$eSArch, $nbSides, 1, 1, 0] _
							, [$eWiza, $nbSides, 1, 1, 0] _
							, [$eSWiza, $nbSides, 1, 1, 0] _
							, [$eMini, $nbSides, 1, 1, 0] _
							, [$eSMini, $nbSides, 1, 1, 0] _
							, [$eWitc, $nbSides, 1, 1, 1] _
							, [$eSWitc, $nbSides, 1, 1, 1] _
							, [$eGobl, $nbSides, 1, 1, 0] _
							, [$eSGobl, $nbSides, 1, 1, 0] _
							, [$eHeal, $nbSides, 1, 1, 1] _
							, [$ePekk, $nbSides, 1, 1, 1] _
							, ["HEROES", 1, 2, 1, 1]]
				EndIf
			Case 1
				Local $listInfoDeploy[10][5] = [[$eBarb, $nbSides, 1, 1, 0] _
						, [$eSBarb, $nbSides, 1, 1, 0] _
						, [$eArch, $nbSides, 1, 1, 0] _
						, [$eSArch, $nbSides, 1, 1, 0] _
						, [$eGobl, $nbSides, 1, 1, 0] _
						, [$eSGobl, $nbSides, 1, 1, 0] _
						, [$eMini, $nbSides, 1, 1, 0] _
						, [$eSMini, $nbSides, 1, 1, 0] _
						, ["CC", 1, 1, 1, 1] _
						, ["HEROES", 1, 2, 1, 1]]
			Case 2
				Local $listInfoDeploy[23][5] = [[$eGiant, $nbSides, 1, 1, $g_iSlotsGiants] _
						, [$eSGiant, $nbSides, 1, 1, $g_iSlotsGiants] _
						, ["CC", 1, 1, 1, 1] _
						, [$eWall, $nbSides, 1, 1, 2] _
						, [$eSWall, $nbSides, 1, 1, 2] _
						, [$eBarb, $nbSides, 1, 2, 2] _
						, [$eSBarb, $nbSides, 1, 2, 2] _
						, [$eArch, $nbSides, 1, 3, 3] _
						, [$eSArch, $nbSides, 1, 3, 3] _
						, [$eBarb, $nbSides, 2, 2, 2] _
						, [$eSBarb, $nbSides, 2, 2, 2] _
						, [$eArch, $nbSides, 2, 3, 3] _
						, [$eSArch, $nbSides, 2, 3, 3] _
						, ["HEROES", 1, 2, 1, 0] _
						, [$eHogs, $nbSides, 1, 1, 1] _
						, [$eWiza, $nbSides, 1, 1, 0] _
						, [$eSWiza, $nbSides, 1, 1, 0] _
						, [$eMini, $nbSides, 1, 1, 0] _
						, [$eSMini, $nbSides, 1, 1, 0] _
						, [$eArch, $nbSides, 3, 3, 2] _
						, [$eSArch, $nbSides, 3, 3, 2] _
						, [$eGobl, $nbSides, 1, 1, 1] _
						, [$eSGobl, $nbSides, 1, 1, 1]]
		EndSwitch
	Else
		If $g_bDebugSetLog Then SetDebugLog("listdeploy standard for attack", $COLOR_DEBUG)
		Switch $g_aiAttackStdDropOrder[$g_iMatchMode]
			Case 0
				If $g_bCustomDropOrderEnable Then
					Local $listInfoDeploy[48][5] = [[MatchTroopDropName(0), MatchSidesDrop(0), MatchTroopWaveNb(0), 1, MatchSlotsPerEdge(0)], _
							[MatchTroopDropName(1), MatchSidesDrop(1), MatchTroopWaveNb(1), 1, MatchSlotsPerEdge(1)], _
							[MatchTroopDropName(2), MatchSidesDrop(2), MatchTroopWaveNb(2), 1, MatchSlotsPerEdge(2)], _
							[MatchTroopDropName(3), MatchSidesDrop(3), MatchTroopWaveNb(3), 1, MatchSlotsPerEdge(3)], _
							[MatchTroopDropName(4), MatchSidesDrop(4), MatchTroopWaveNb(4), 1, MatchSlotsPerEdge(4)], _
							[MatchTroopDropName(5), MatchSidesDrop(5), MatchTroopWaveNb(5), 1, MatchSlotsPerEdge(5)], _
							[MatchTroopDropName(6), MatchSidesDrop(6), MatchTroopWaveNb(6), 1, MatchSlotsPerEdge(6)], _
							[MatchTroopDropName(7), MatchSidesDrop(7), MatchTroopWaveNb(7), 1, MatchSlotsPerEdge(7)], _
							[MatchTroopDropName(8), MatchSidesDrop(8), MatchTroopWaveNb(8), 1, MatchSlotsPerEdge(8)], _
							[MatchTroopDropName(9), MatchSidesDrop(9), MatchTroopWaveNb(9), 1, MatchSlotsPerEdge(9)], _
							[MatchTroopDropName(10), MatchSidesDrop(10), MatchTroopWaveNb(10), 1, MatchSlotsPerEdge(10)], _
							[MatchTroopDropName(11), MatchSidesDrop(11), MatchTroopWaveNb(11), 1, MatchSlotsPerEdge(11)], _
							[MatchTroopDropName(12), MatchSidesDrop(12), MatchTroopWaveNb(12), 1, MatchSlotsPerEdge(12)], _
							[MatchTroopDropName(13), MatchSidesDrop(13), MatchTroopWaveNb(13), 1, MatchSlotsPerEdge(13)], _
							[MatchTroopDropName(14), MatchSidesDrop(14), MatchTroopWaveNb(14), 1, MatchSlotsPerEdge(14)], _
							[MatchTroopDropName(15), MatchSidesDrop(15), MatchTroopWaveNb(15), 1, MatchSlotsPerEdge(15)], _
							[MatchTroopDropName(16), MatchSidesDrop(16), MatchTroopWaveNb(16), 1, MatchSlotsPerEdge(16)], _
							[MatchTroopDropName(17), MatchSidesDrop(17), MatchTroopWaveNb(17), 1, MatchSlotsPerEdge(17)], _
							[MatchTroopDropName(18), MatchSidesDrop(18), MatchTroopWaveNb(18), 1, MatchSlotsPerEdge(18)], _
							[MatchTroopDropName(19), MatchSidesDrop(19), MatchTroopWaveNb(19), 1, MatchSlotsPerEdge(19)], _
							[MatchTroopDropName(20), MatchSidesDrop(20), MatchTroopWaveNb(20), 1, MatchSlotsPerEdge(20)], _
							[MatchTroopDropName(21), MatchSidesDrop(21), MatchTroopWaveNb(21), 1, MatchSlotsPerEdge(21)], _
							[MatchTroopDropName(22), MatchSidesDrop(22), MatchTroopWaveNb(22), 1, MatchSlotsPerEdge(22)], _
							[MatchTroopDropName(23), MatchSidesDrop(23), MatchTroopWaveNb(23), 1, MatchSlotsPerEdge(23)], _
							[MatchTroopDropName(24), MatchSidesDrop(24), MatchTroopWaveNb(24), 1, MatchSlotsPerEdge(24)], _
							[MatchTroopDropName(25), MatchSidesDrop(25), MatchTroopWaveNb(25), 1, MatchSlotsPerEdge(25)], _
							[MatchTroopDropName(26), MatchSidesDrop(26), MatchTroopWaveNb(26), 1, MatchSlotsPerEdge(26)], _
							[MatchTroopDropName(27), MatchSidesDrop(27), MatchTroopWaveNb(27), 1, MatchSlotsPerEdge(27)], _
							[MatchTroopDropName(28), MatchSidesDrop(28), MatchTroopWaveNb(28), 1, MatchSlotsPerEdge(28)], _
							[MatchTroopDropName(29), MatchSidesDrop(29), MatchTroopWaveNb(29), 1, MatchSlotsPerEdge(29)], _
							[MatchTroopDropName(30), MatchSidesDrop(30), MatchTroopWaveNb(30), 1, MatchSlotsPerEdge(30)], _
							[MatchTroopDropName(31), MatchSidesDrop(31), MatchTroopWaveNb(31), 1, MatchSlotsPerEdge(31)], _
							[MatchTroopDropName(32), MatchSidesDrop(32), MatchTroopWaveNb(32), 1, MatchSlotsPerEdge(32)], _
							[MatchTroopDropName(33), MatchSidesDrop(33), MatchTroopWaveNb(33), 1, MatchSlotsPerEdge(33)], _
							[MatchTroopDropName(34), MatchSidesDrop(34), MatchTroopWaveNb(34), 1, MatchSlotsPerEdge(34)], _
							[MatchTroopDropName(35), MatchSidesDrop(35), MatchTroopWaveNb(35), 1, MatchSlotsPerEdge(35)], _
							[MatchTroopDropName(36), MatchSidesDrop(36), MatchTroopWaveNb(36), 1, MatchSlotsPerEdge(36)], _
							[MatchTroopDropName(37), MatchSidesDrop(37), MatchTroopWaveNb(37), 1, MatchSlotsPerEdge(37)], _
							[MatchTroopDropName(38), MatchSidesDrop(38), MatchTroopWaveNb(38), 1, MatchSlotsPerEdge(38)], _
							[MatchTroopDropName(39), MatchSidesDrop(39), MatchTroopWaveNb(39), 1, MatchSlotsPerEdge(39)], _
							[MatchTroopDropName(40), MatchSidesDrop(40), MatchTroopWaveNb(40), 1, MatchSlotsPerEdge(40)], _
							[MatchTroopDropName(41), MatchSidesDrop(41), MatchTroopWaveNb(41), 1, MatchSlotsPerEdge(41)], _
							[MatchTroopDropName(42), MatchSidesDrop(42), MatchTroopWaveNb(42), 1, MatchSlotsPerEdge(42)], _
							[MatchTroopDropName(43), MatchSidesDrop(43), MatchTroopWaveNb(43), 1, MatchSlotsPerEdge(43)], _
							[MatchTroopDropName(44), MatchSidesDrop(44), MatchTroopWaveNb(44), 1, MatchSlotsPerEdge(44)], _
							[MatchTroopDropName(45), MatchSidesDrop(45), MatchTroopWaveNb(45), 1, MatchSlotsPerEdge(45)], _
							[MatchTroopDropName(46), MatchSidesDrop(46), MatchTroopWaveNb(46), 1, MatchSlotsPerEdge(46)], _
							[MatchTroopDropName(47), MatchSidesDrop(47), MatchTroopWaveNb(47), 1, MatchSlotsPerEdge(47)]]
				Else
					Local $listInfoDeploy[48][5] = [[$eGole, $nbSides, 1, 1, 2] _
							, [$eIceG, $nbSides, 1, 1, 2] _
							, [$eLava, $nbSides, 1, 1, 2] _
							, [$eYeti, $nbSides, 1, 1, 2] _
							, [$eIceH, $nbSides, 1, 1, 2] _
							, [$eGiant, $nbSides, 1, 1, $g_iSlotsGiants] _
							, [$eSGiant, $nbSides, 1, 1, $g_iSlotsGiants] _
							, [$eDrag, $nbSides, 1, 1, 0] _
							, [$eSDrag, $nbSides, 1, 1, 0] _
							, ["CC", 1, 1, 1, 1] _
							, [$eBall, $nbSides, 1, 1, 0] _
							, [$eRBall, $nbSides, 1, 1, 0] _
							, [$eBabyD, $nbSides, 1, 1, 1] _
							, [$eInfernoD, $nbSides, 1, 1, 1] _
							, [$eHogs, $nbSides, 1, 1, 1] _
							, [$eSHogs, $nbSides, 1, 1, 1] _
							, [$eValk, $nbSides, 1, 1, 0] _
							, [$eSValk, $nbSides, 1, 1, 0] _
							, [$eBowl, $nbSides, 1, 1, 0] _
							, [$eSBowl, $nbSides, 1, 1, 0] _
							, [$eHunt, $nbSides, 1, 1, 0] _
							, [$eAppWard, $nbSides, 1, 1, 0] _
							, [$eDruid, $nbSides, 1, 1, 0] _
							, [$eFurn, $nbSides, 1, 1, 0] _
							, [$eMine, $nbSides, 1, 1, 0] _
							, [$eSMine, $nbSides, 1, 1, 0] _
							, [$eEDrag, $nbSides, 1, 1, 0] _
							, [$eRDrag, $nbSides, 1, 1, 0] _
							, [$eETitan, $nbSides, 1, 1, 0] _
							, [$eRootR, $nbSides, 1, 1, 0] _
							, [$eThrower, $nbSides, 1, 1, 0] _
							, [$eBarb, $nbSides, 1, 1, 0] _
							, [$eSBarb, $nbSides, 1, 1, 0] _
							, [$eWall, $nbSides, 1, 1, 1] _
							, [$eSWall, $nbSides, 1, 1, 1] _
							, [$eArch, $nbSides, 1, 1, 0] _
							, [$eSArch, $nbSides, 1, 1, 0] _
							, [$eWiza, $nbSides, 1, 1, 0] _
							, [$eSWiza, $nbSides, 1, 1, 0] _
							, [$eMini, $nbSides, 1, 1, 0] _
							, [$eSMini, $nbSides, 1, 1, 0] _
							, [$eWitc, $nbSides, 1, 1, 1] _
							, [$eSWitc, $nbSides, 1, 1, 1] _
							, [$eGobl, $nbSides, 1, 1, 0] _
							, [$eSGobl, $nbSides, 1, 1, 0] _
							, [$eHeal, $nbSides, 1, 1, 1] _
							, [$ePekk, $nbSides, 1, 1, 1] _
							, ["HEROES", 1, 2, 1, 1]]
				EndIf
			Case 1
				Local $listInfoDeploy[10][5] = [[$eBarb, $nbSides, 1, 1, 0] _
						, [$eSBarb, $nbSides, 1, 1, 0] _
						, [$eArch, $nbSides, 1, 1, 0] _
						, [$eSArch, $nbSides, 1, 1, 0] _
						, [$eGobl, $nbSides, 1, 1, 0] _
						, [$eSGobl, $nbSides, 1, 1, 0] _
						, [$eMini, $nbSides, 1, 1, 0] _
						, [$eSMini, $nbSides, 1, 1, 0] _
						, ["CC", 1, 1, 1, 1] _
						, ["HEROES", 1, 2, 1, 1]]
			Case 2
				Local $listInfoDeploy[23][5] = [[$eGiant, $nbSides, 1, 1, $g_iSlotsGiants] _
						, [$eSGiant, $nbSides, 1, 1, $g_iSlotsGiants] _
						, ["CC", 1, 1, 1, 1] _
						, [$eBarb, $nbSides, 1, 2, 0] _
						, [$eSBarb, $nbSides, 1, 2, 0] _
						, [$eWall, $nbSides, 1, 1, 1] _
						, [$eSWall, $nbSides, 1, 1, 1] _
						, [$eArch, $nbSides, 1, 2, 0] _
						, [$eSArch, $nbSides, 1, 2, 0] _
						, [$eBarb, $nbSides, 2, 2, 0] _
						, [$eSBarb, $nbSides, 2, 2, 0] _
						, [$eGobl, $nbSides, 1, 2, 0] _
						, [$eSGobl, $nbSides, 1, 2, 0] _
						, [$eHogs, $nbSides, 1, 1, 1] _
						, [$eWiza, $nbSides, 1, 1, 0] _
						, [$eSWiza, $nbSides, 1, 1, 0] _
						, [$eMini, $nbSides, 1, 1, 0] _
						, [$eSMini, $nbSides, 1, 1, 0] _
						, [$eArch, $nbSides, 2, 2, 0] _
						, [$eSArch, $nbSides, 2, 2, 0] _
						, [$eGobl, $nbSides, 2, 2, 0] _
						, [$eSGobl, $nbSides, 2, 2, 0] _
						, ["HEROES", 1, 2, 1, 1]]
			Case Else
				SetLog("Algorithm type unavailable, defaulting to regular", $COLOR_ERROR)
				Local $listInfoDeploy[23][5] = [[$eGiant, $nbSides, 1, 1, $g_iSlotsGiants] _
						, [$eSGiant, $nbSides, 1, 1, $g_iSlotsGiants] _
						, ["CC", 1, 1, 1, 1] _
						, [$eBarb, $nbSides, 1, 2, 0] _
						, [$eSBarb, $nbSides, 1, 2, 0] _
						, [$eWall, $nbSides, 1, 1, 1] _
						, [$eSWall, $nbSides, 1, 1, 1] _
						, [$eArch, $nbSides, 1, 2, 0] _
						, [$eSArch, $nbSides, 1, 2, 0] _
						, [$eBarb, $nbSides, 2, 2, 0] _
						, [$eSBarb, $nbSides, 2, 2, 0] _
						, [$eGobl, $nbSides, 1, 2, 0] _
						, [$eSGobl, $nbSides, 1, 2, 0] _
						, [$eHogs, $nbSides, 1, 1, 1] _
						, [$eWiza, $nbSides, 1, 1, 0] _
						, [$eSWiza, $nbSides, 1, 1, 0] _
						, [$eMini, $nbSides, 1, 1, 0] _
						, [$eSMini, $nbSides, 1, 1, 0] _
						, [$eArch, $nbSides, 2, 2, 0] _
						, [$eSArch, $nbSides, 2, 2, 0] _
						, [$eGobl, $nbSides, 2, 2, 0] _
						, [$eSGobl, $nbSides, 2, 2, 0] _
						, ["HEROES", 1, 2, 1, 1]]
		EndSwitch
	EndIf

	$g_bIsCCDropped = False
	$g_aiDeployCCPosition[0] = -1
	$g_aiDeployCCPosition[1] = -1
	$g_bIsHeroesDropped = False
	$g_aiDeployHeroesPosition[0] = -1
	$g_aiDeployHeroesPosition[1] = -1

	LaunchTroop2($listInfoDeploy, $g_iClanCastleSlot, $g_iKingSlot, $g_iQueenSlot, $g_iPrinceSlot, $g_iWardenSlot, $g_iChampionSlot)
	If RunExecutionStandardDeploymentProofRequired() And Not _AttackEnsurePlannedActorsDeployed() Then Return
	CheckHeroesHealth()

	If _Sleep($DELAYALGORITHM_ALLTROOPS4) Then Return
	SetLog("Dropping left over troops", $COLOR_INFO)
	For $x = 0 To 1
		If PrepareAttack($g_iMatchMode, True) = 0 Then
			If $g_bDebugSetLog Then SetDebugLog("No Wast time... exit, no troops usable left", $COLOR_DEBUG)
			ExitLoop ;Check remaining quantities
		EndIf
		For $i = $eBarb To $eFurn ; launch all remaining troops
			If LaunchTroop($i, $nbSides, 1, 1, 1) Then
				CheckHeroesHealth()
				If _Sleep($DELAYALGORITHM_ALLTROOPS5) Then Return
			EndIf
		Next
	Next

	CheckHeroesHealth()

	; The old routine treated emitted click commands as success. On a wrong zoom those clicks can land
	; on buildings while the troop bar remains full. Require two independent, valid live-bar captures
	; after all bounded leftover passes; one OCR miss must never turn click logs into deployment proof.
	If RunExecutionStandardDeploymentProofRequired() Then
		If Not _AttackConfirmStandardDeploymentGone() Then Return
	EndIf
	; Smart clicks are allowed only after the final two-frame troop-bar proof. This keeps the entry
	; Rage and ability scheduler from running while a failed deployment still leaves the army full.
	If RunExecutionSmartAttackEnabled() Then
		Local $iSmartEntryX = $g_aiDeployHeroesPosition[0]
		Local $iSmartEntryY = $g_aiDeployHeroesPosition[1]
		If $iSmartEntryX < 0 Or $iSmartEntryY < 0 Then
			$iSmartEntryX = $g_aiDeployCCPosition[0]
			$iSmartEntryY = $g_aiDeployCCPosition[1]
		EndIf
		If ($iSmartEntryX < 0 Or $iSmartEntryY < 0) And UBound($g_aaiEdgeDropPoints) > 0 And IsArray($g_aaiEdgeDropPoints[0][2]) Then
			$iSmartEntryX = $g_aaiEdgeDropPoints[0][2][0]
			$iSmartEntryY = $g_aaiEdgeDropPoints[0][2][1]
		EndIf
		SmartAttackCombatStart($iSmartEntryX, $iSmartEntryY)
	EndIf

	SetLog("Finished Attacking, waiting for the battle to end")
EndFunc   ;==>algorithm_AllTroops

Func _AttackDeployableTroopCount()
	Local $iTotal = 0
	For $iSlot = 0 To UBound($g_avAttackTroops) - 1
		Local $iTroop = Int($g_avAttackTroops[$iSlot][0])
		If $iTroop >= $eBarb And $iTroop <= $eFurn Then $iTotal += Int($g_avAttackTroops[$iSlot][1])
	Next
	Return $iTotal
EndFunc   ;==>_AttackDeployableTroopCount

Func _AttackReadLiveDeployableTroopCount(ByRef $bReadValid)
	$bReadValid = False
	If Not $g_bRunState Or Not IsAttackPage() Then
		SetLog("Run Planner deployment verification failed: the live attack screen is no longer visible", $COLOR_ERROR)
		Return -1
	EndIf

	; GetAttackBar(Remaining=True) reuses the slots proven by the initial attack-bar scan, but reads
	; their current deployed-state pixels and quantities from this fresh framebuffer. A non-array is
	; a recognition failure; it is never equivalent to a legitimately empty troop bar.
	ForceCaptureRegion()
	_CaptureRegion2()
	Local $aLiveAttackBar = GetAttackBar(True, $g_iMatchMode)
	If Not IsArray($aLiveAttackBar) Then
		SetLog("Run Planner deployment verification failed: the live attack bar could not be read", $COLOR_ERROR)
		Return -1
	EndIf

	Local $iTotal = 0
	For $iSlot = 0 To UBound($aLiveAttackBar, 1) - 1
		Local $iTroop = Int($aLiveAttackBar[$iSlot][0])
		If $iTroop >= $eBarb And $iTroop <= $eFurn Then $iTotal += Int($aLiveAttackBar[$iSlot][2])
	Next
	$bReadValid = True
	Return $iTotal
EndFunc   ;==>_AttackReadLiveDeployableTroopCount

Func _AttackConfirmStandardDeploymentGone()
	For $iRead = 1 To 2
		Local $bReadValid = False
		Local $iDeployableAfter = _AttackReadLiveDeployableTroopCount($bReadValid)
		If Not $bReadValid Or $iDeployableAfter <> 0 Then
			RunExecutionRecordDeploymentProof($iDeployableAfter)
			Return False
		EndIf
		SetDebugLog("Run Planner deployment proof: live attack bar read " & $iRead & "/2 contains zero deployable troops")
		If $iRead = 1 And _Sleep(350) Then Return False
	Next
	Return RunExecutionRecordDeploymentProof(0)
EndFunc   ;==>_AttackConfirmStandardDeploymentGone

; The legacy smart dispatcher may mark its HEROES/CC wave handled even when no actor click was
; accepted. A planned run treats the selected Hero mask and a present siege/CC slot as authority,
; proves their live-bar state, retries them once at the same dynamic red-line point that accepted
; the main army, then proves the live-bar state again. Emitted clicks are never deployment proof.
Func _AttackEnsurePlannedActorsDeployed()
	Local $iHeroMask = $g_aiAttackUseHeroes[$g_iMatchMode]
	Local $iDropX = $g_aiDeployHeroesPosition[0]
	Local $iDropY = $g_aiDeployHeroesPosition[1]
	If $iDropX < 0 Or $iDropY < 0 Then
		$iDropX = $g_aiDeployCCPosition[0]
		$iDropY = $g_aiDeployCCPosition[1]
	EndIf
	If $iDropX < 0 Or $iDropY < 0 Then
		Local $aSafePoint = $g_aaiEdgeDropPoints[0][2]
		$iDropX = $aSafePoint[0]
		$iDropY = $aSafePoint[1]
	EndIf
	SetLog("Run Planner actors: hero mask " & $iHeroMask & "; slots K=" & $g_iKingSlot & ", Q=" & $g_iQueenSlot & _
			", P=" & $g_iPrinceSlot & ", W=" & $g_iWardenSlot & ", C=" & $g_iChampionSlot & ", CC=" & $g_iClanCastleSlot & _
			"; red-line point=" & $iDropX & "," & $iDropY, $COLOR_INFO)

	If (BitAND($iHeroMask, $eHeroKing) = $eHeroKing And $g_iKingSlot = -1) Or _
			(BitAND($iHeroMask, $eHeroQueen) = $eHeroQueen And $g_iQueenSlot = -1) Or _
			(BitAND($iHeroMask, $eHeroPrince) = $eHeroPrince And $g_iPrinceSlot = -1) Or _
			(BitAND($iHeroMask, $eHeroWarden) = $eHeroWarden And $g_iWardenSlot = -1) Or _
			(BitAND($iHeroMask, $eHeroChampion) = $eHeroChampion And $g_iChampionSlot = -1) Then
		SetLog("Run Planner could not find every selected Hero on the live attack bar; refusing to claim deployment", $COLOR_ERROR)
		Return False
	EndIf

	Local $bProofValid = False
	Local $aActorBaseline = 0
	If _AttackRefreshPlannedActorProof($iHeroMask, $bProofValid) Then Return True
	If Not $bProofValid Then
		SetLog("Run Planner could not read the live actor bar before its bounded retry", $COLOR_ERROR)
		Return False
	EndIf

	If Not _AttackSelectedHeroesDropped($iHeroMask) Or ($g_iClanCastleSlot <> -1 And $g_abAttackDropCC[$g_iMatchMode] And Not $g_bIsCCDropped) Then
		; Main troops disappear from the compact current-client bar after deployment. Slot indexes and
		; inherited slot coordinates are therefore not authoritative for the remaining actors. Read the
		; live bar again and select each requested actor by its freshly detected portrait coordinates.
		$aActorBaseline = _AttackReadLiveActorBar(True)
		If Not IsArray($aActorBaseline) Then
			SetLog("Run Planner could not read fresh actor coordinates for its bounded deployment retry", $COLOR_ERROR)
			Return False
		EndIf
		If Not _AttackSelectedHeroesDropped($iHeroMask) Then
			SetLog("Run Planner: deploying the selected Heroes from fresh live-bar coordinates", $COLOR_ACTION)
			If Not _AttackDeploySelectedHeroesAtPoint($aActorBaseline, $iHeroMask, $iDropX, $iDropY) Then Return False
		EndIf
		If $g_iClanCastleSlot <> -1 And $g_abAttackDropCC[$g_iMatchMode] And Not $g_bIsCCDropped Then
			SetLog("Run Planner: deploying the detected siege/Clan Castle from its fresh live-bar coordinate", $COLOR_ACTION)
			If Not _AttackDeployLiveSiegeAtPoint($aActorBaseline, $iDropX, $iDropY) Then Return False
		EndIf
	EndIf
	If _Sleep(650) Then Return False

	$bProofValid = False
	If Not _AttackRefreshPlannedActorProof($iHeroMask, $bProofValid, $aActorBaseline) Then
		SetLog("Run Planner failed live-bar proof for one or more selected Heroes or the siege/Clan Castle", $COLOR_ERROR)
		Return False
	EndIf
	Return $bProofValid
EndFunc   ;==>_AttackEnsurePlannedActorsDeployed

Func _AttackDeploySelectedHeroesAtPoint(ByRef $aLiveActors, $iHeroMask, $iDropX, $iDropY)
	; Current-army mode deliberately skips the Hero Hall/config scan. The plan mask is the authority,
	; while the fresh live-bar image supplies the only safe portrait coordinates after the bar shifts.
	; A deployed Hero remains visible as its ability button. Never click an already-proven active Hero,
	; because that would spend the ability instead of repairing a missing deployment.
	If BitAND($iHeroMask, $eHeroKing) = $eHeroKing And Not $g_bDropKing And Not _AttackDeployLiveActorAtPoint($aLiveActors, $eKing, "King", $iDropX, $iDropY) Then Return False
	If BitAND($iHeroMask, $eHeroQueen) = $eHeroQueen And Not $g_bDropQueen And Not _AttackDeployLiveActorAtPoint($aLiveActors, $eQueen, "Queen", $iDropX, $iDropY) Then Return False
	If BitAND($iHeroMask, $eHeroPrince) = $eHeroPrince And Not $g_bDropPrince And Not _AttackDeployLiveActorAtPoint($aLiveActors, $ePrince, "Minion Prince", $iDropX, $iDropY) Then Return False
	If BitAND($iHeroMask, $eHeroWarden) = $eHeroWarden And Not $g_bDropWarden And Not _AttackDeployLiveActorAtPoint($aLiveActors, $eWarden, "Grand Warden", $iDropX, $iDropY) Then Return False
	If BitAND($iHeroMask, $eHeroChampion) = $eHeroChampion And Not $g_bDropChampion And Not _AttackDeployLiveActorAtPoint($aLiveActors, $eChampion, "Royal Champion", $iDropX, $iDropY) Then Return False
	Return True
EndFunc   ;==>_AttackDeploySelectedHeroesAtPoint

Func _AttackDeployLiveSiegeAtPoint(ByRef $aLiveActors, $iDropX, $iDropY)
	For $i = 0 To UBound($aLiveActors, 1) - 1
		Local $iTroop = Int($aLiveActors[$i][0])
		If $iTroop = $eCastle Or $iTroop = $eWallW Or $iTroop = $eBattleB Or $iTroop = $eStoneS Or _
				$iTroop = $eSiegeB Or $iTroop = $eLogL Or $iTroop = $eFlameF Or $iTroop = $eBattleD Or $iTroop = $eTroopL Then
			Local $bDeployed = _AttackDeployLiveActorAtPoint($aLiveActors, $iTroop, "Siege/Clan Castle", $iDropX, $iDropY)
			If $bDeployed Then $g_bIsCCDropped = True
			Return $bDeployed
		EndIf
	Next
	; The inherited dispatcher can deploy the siege before this bounded repair. A full fresh scan that
	; no longer contains any siege/CC portrait is positive post-deployment evidence, not a retry error.
	$g_bIsCCDropped = True
	SetLog("Run Planner: siege/Clan Castle is absent from the fresh live bar; deployment proved", $COLOR_SUCCESS1)
	Return True
EndFunc   ;==>_AttackDeployLiveSiegeAtPoint

Func _AttackDeployLiveActorAtPoint(ByRef $aLiveActors, $iActorType, $sActorName, $iDropX, $iDropY)
	For $i = 0 To UBound($aLiveActors, 1) - 1
		If Int($aLiveActors[$i][0]) <> $iActorType Or Int($aLiveActors[$i][2]) <= 0 Then ContinueLoop
		Local $iPortraitX = Int($aLiveActors[$i][3])
		Local $iPortraitY = Int($aLiveActors[$i][4])
		If $iPortraitX <= 0 Or $iPortraitY <= 0 Then ExitLoop
		SetLog("Dropping " & $sActorName & " from live portrait " & $iPortraitX & "," & $iPortraitY & " at " & $iDropX & "," & $iDropY, $COLOR_INFO)
		Click($iPortraitX, $iPortraitY, 1, 120, "LiveActor-" & $sActorName)
		If _Sleep($DELAYDROPHEROES2) Then Return False
		AttackClick($iDropX, $iDropY, 1, 50, 0, "LiveActorDrop-" & $sActorName)
		If _Sleep($DELAYDROPHEROES1) Then Return False
		Return True
	Next
	SetLog("Run Planner could not find selected " & $sActorName & " on the fresh live attack bar", $COLOR_ERROR)
	Return False
EndFunc   ;==>_AttackDeployLiveActorAtPoint

Func _AttackReadLiveActorBar($bFreshCoordinates = False)
	If Not $g_bRunState Or Not IsAttackPage() Then Return
	ForceCaptureRegion()
	_CaptureRegion2()
	; Remaining-mode intentionally reuses the initial attack-bar model to prove troops/siege gone.
	; A deployment retry needs a new image search because the compact bar shifts after the army drops.
	Return GetAttackBar(Not $bFreshCoordinates, $g_iMatchMode)
EndFunc   ;==>_AttackReadLiveActorBar

Func _AttackRefreshPlannedActorProof($iHeroMask, ByRef $bProofValid, $aActorBaseline = Default)
	$bProofValid = False
	; The final read is a fresh image search so the proof observes the current compact-bar geometry.
	; The pre-retry read remains the inherited remaining-mode scan.
	Local $bHasBaseline = IsArray($aActorBaseline)
	Local $aLiveAttackBar = _AttackReadLiveActorBar($bHasBaseline)
	If Not IsArray($aLiveAttackBar) Then Return False

	; Current clients keep a Hero portrait on the bar after deployment so the portrait can activate
	; that Hero's ability. The old AmountX/deployed-marker test therefore reports every deployed Hero
	; as still available. Prove deployment from the Hero-specific battlefield health bar used by the
	; inherited ability controller; that bar does not exist on an undeployed portrait.
	Local $bKing = BitAND($iHeroMask, $eHeroKing) <> $eHeroKing Or _AttackProveActiveHero("King", $g_sImgKingBar, $aKingHealth)
	Local $bQueen = BitAND($iHeroMask, $eHeroQueen) <> $eHeroQueen Or _AttackProveActiveHero("Queen", $g_sImgQueenBar, $aQueenHealth)
	Local $bPrince = BitAND($iHeroMask, $eHeroPrince) <> $eHeroPrince Or _AttackProveActiveHero("Minion Prince", $g_sImgPrinceBar, $aPrinceHealth)
	Local $bWarden = BitAND($iHeroMask, $eHeroWarden) <> $eHeroWarden Or _AttackProveActiveHero("Grand Warden", $g_sImgWardenBar, $aWardenHealth)
	Local $bChampion = BitAND($iHeroMask, $eHeroChampion) <> $eHeroChampion Or _AttackProveActiveHero("Royal Champion", $g_sImgChampionBar, $aChampionHealth)
	If $bHasBaseline Then
		If Not $bKing Then $bKing = _AttackProveRaisedHero($aActorBaseline, $aLiveAttackBar, $eKing, "King")
		If Not $bQueen Then $bQueen = _AttackProveRaisedHero($aActorBaseline, $aLiveAttackBar, $eQueen, "Queen")
		If Not $bPrince Then $bPrince = _AttackProveRaisedHero($aActorBaseline, $aLiveAttackBar, $ePrince, "Minion Prince")
		If Not $bWarden Then $bWarden = _AttackProveRaisedHero($aActorBaseline, $aLiveAttackBar, $eWarden, "Grand Warden")
		If Not $bChampion Then $bChampion = _AttackProveRaisedHero($aActorBaseline, $aLiveAttackBar, $eChampion, "Royal Champion")
	EndIf
	Local $bCC = $g_bIsCCDropped Or $g_iClanCastleSlot = -1 Or Not $g_abAttackDropCC[$g_iMatchMode]
	For $iSlot = 0 To UBound($aLiveAttackBar, 1) - 1
		Local $iLiveTroop = Int($aLiveAttackBar[$iSlot][0])
		Local $bGone = Int($aLiveAttackBar[$iSlot][2]) <= 0
		Switch $iLiveTroop
			Case $eCastle, $eWallW, $eBattleB, $eStoneS, $eSiegeB, $eLogL, $eFlameF, $eBattleD, $eTroopL
				$bCC = $bGone
		EndSwitch
	Next

	$g_bDropKing = $bKing
	$g_bDropQueen = $bQueen
	$g_bDropPrince = $bPrince
	$g_bDropWarden = $bWarden
	$g_bDropChampion = $bChampion
	$g_bIsCCDropped = $bCC
	$bProofValid = True
	SetDebugLog("Run Planner live actor proof: K=" & $bKing & ", Q=" & $bQueen & ", P=" & $bPrince & ", W=" & $bWarden & ", C=" & $bChampion & ", CC=" & $bCC)
	Return _AttackSelectedHeroesDropped($iHeroMask) And $bCC
EndFunc   ;==>_AttackRefreshPlannedActorProof

Func _AttackProveActiveHero($sHeroName, $sHeroImagePath, ByRef $aHealthTemplate)
	Local $aHero = decodeSingleCoord(FindImageInPlace2($sHeroName & "Active", $sHeroImagePath, _
			0, 570 + $g_iBottomOffsetY, 858, 638 + $g_iBottomOffsetY, True))
	If Not IsArray($aHero) Or UBound($aHero) <> 2 Then
		SetDebugLog("Run Planner active-Hero proof: " & $sHeroName & " portrait not found")
		Return False
	EndIf

	Local $aHealth = $aHealthTemplate
	$aHealth[0] = $aHero[0] - $aHealth[4]
	Local $sHealthColor = _GetPixelColor($aHealth[0], $aHealth[1], False)
	; Do not reuse the inherited Red+Blue mask here: with this DIB channel ordering that mask accepts
	; a black undeployed background as 0x00D500. Exact all-channel tolerance is the deployment proof.
	Local $bActive = _ColorCheck($sHealthColor, Hex($aHealth[2], 6), $aHealth[3])
	SetDebugLog("Run Planner active-Hero proof: " & $sHeroName & " at " & $aHero[0] & "," & $aHero[1] & _
			" health=" & $sHealthColor & ", active=" & $bActive)
	Return $bActive
EndFunc   ;==>_AttackProveActiveHero

Func _AttackProveRaisedHero(ByRef $aBefore, ByRef $aAfter, $iHeroType, $sHeroName)
	Local $iBeforeX = -1, $iBeforeY = -1, $iAfterX = -1, $iAfterY = -1
	For $i = 0 To UBound($aBefore, 1) - 1
		If Int($aBefore[$i][0]) = $iHeroType And Int($aBefore[$i][2]) > 0 Then
			$iBeforeX = Int($aBefore[$i][3])
			$iBeforeY = Int($aBefore[$i][4])
			ExitLoop
		EndIf
	Next
	For $i = 0 To UBound($aAfter, 1) - 1
		If Int($aAfter[$i][0]) = $iHeroType And Int($aAfter[$i][2]) > 0 Then
			$iAfterX = Int($aAfter[$i][3])
			$iAfterY = Int($aAfter[$i][4])
			ExitLoop
		EndIf
	Next
	If $iBeforeX <= 0 Or $iBeforeY <= 0 Or $iAfterX <= 0 Or $iAfterY <= 0 Then Return False

	; On the 860x732 current-client bar, a successfully deployed Hero becomes its raised ability
	; button. Live evidence showed a stable 12-15px upward transition with unchanged X. Bound both
	; axes so animation noise cannot turn an unrelated/misclassified portrait into deployment proof.
	Local $iRise = $iBeforeY - $iAfterY
	Local $bRaised = Abs($iAfterX - $iBeforeX) <= 12 And $iRise >= 8 And $iRise <= 30
	SetDebugLog("Run Planner raised-Hero proof: " & $sHeroName & " before=" & $iBeforeX & "," & $iBeforeY & _
			" after=" & $iAfterX & "," & $iAfterY & ", rise=" & $iRise & ", active=" & $bRaised)
	Return $bRaised
EndFunc   ;==>_AttackProveRaisedHero

Func _AttackSelectedHeroesDropped($iHeroMask)
	If BitAND($iHeroMask, $eHeroKing) = $eHeroKing And Not $g_bDropKing Then Return False
	If BitAND($iHeroMask, $eHeroQueen) = $eHeroQueen And Not $g_bDropQueen Then Return False
	If BitAND($iHeroMask, $eHeroPrince) = $eHeroPrince And Not $g_bDropPrince Then Return False
	If BitAND($iHeroMask, $eHeroWarden) = $eHeroWarden And Not $g_bDropWarden Then Return False
	If BitAND($iHeroMask, $eHeroChampion) = $eHeroChampion And Not $g_bDropChampion Then Return False
	Return True
EndFunc   ;==>_AttackSelectedHeroesDropped

Func SetSlotSpecialTroops()
	$g_iKingSlot = -1
	$g_iQueenSlot = -1
	$g_iPrinceSlot = -1
	$g_iWardenSlot = -1
	$g_iChampionSlot = -1
	$g_iClanCastleSlot = -1

	For $i = 0 To UBound($g_avAttackTroops) - 1
		If $g_avAttackTroops[$i][0] = $eCastle Or $g_avAttackTroops[$i][0] = $eWallW Or $g_avAttackTroops[$i][0] = $eBattleB Or $g_avAttackTroops[$i][0] = $eStoneS Or _
				$g_avAttackTroops[$i][0] = $eSiegeB Or $g_avAttackTroops[$i][0] = $eLogL Or $g_avAttackTroops[$i][0] = $eFlameF Or $g_avAttackTroops[$i][0] = $eBattleD Or $g_avAttackTroops[$i][0] = $eTroopL Then
			$g_iClanCastleSlot = $i
		ElseIf $g_avAttackTroops[$i][0] = $eKing Then
			$g_iKingSlot = $i
		ElseIf $g_avAttackTroops[$i][0] = $eQueen Then
			$g_iQueenSlot = $i
		ElseIf $g_avAttackTroops[$i][0] = $ePrince Then
			$g_iPrinceSlot = $i
		ElseIf $g_avAttackTroops[$i][0] = $eWarden Then
			$g_iWardenSlot = $i
		ElseIf $g_avAttackTroops[$i][0] = $eChampion Then
			$g_iChampionSlot = $i
		EndIf
	Next

	If $g_bDebugSetLog Then
		SetDebugLog("SetSlotSpecialTroops() King Slot: " & $g_iKingSlot, $COLOR_DEBUG)
		SetDebugLog("SetSlotSpecialTroops() Queen Slot: " & $g_iQueenSlot, $COLOR_DEBUG)
		SetDebugLog("SetSlotSpecialTroops() Prince Slot: " & $g_iPrinceSlot, $COLOR_DEBUG)
		SetDebugLog("SetSlotSpecialTroops() Warden Slot: " & $g_iWardenSlot, $COLOR_DEBUG)
		SetDebugLog("SetSlotSpecialTroops() Champion Slot: " & $g_iChampionSlot, $COLOR_DEBUG)
		SetDebugLog("SetSlotSpecialTroops() Clan Castle Slot: " & $g_iClanCastleSlot, $COLOR_DEBUG)
	EndIf

EndFunc   ;==>SetSlotSpecialTroops

Func CloseBattle()
	If IsAttackPage() Then
		For $i = 1 To 30
			;_CaptureRegion()
			If _ColorCheck(_GetPixelColor($aWonOneStar[0], $aWonOneStar[1], True), Hex($aWonOneStar[2], 6), $aWonOneStar[3]) = True Then ExitLoop ;exit if not 'no star'
			If _Sleep($DELAYALGORITHM_ALLTROOPS2) Then Return
		Next
	EndIf

	If IsAttackPage() Then ClickP($aSurrenderButton, 1, 0, "#0030") ;Click Surrender
	If _Sleep($DELAYALGORITHM_ALLTROOPS3) Then Return
	If IsEndBattlePage() Then
		ClickP($aConfirmSurrender, 1, 120, "#0031") ;Click Confirm
		If _Sleep($DELAYALGORITHM_ALLTROOPS1) Then Return
	EndIf

EndFunc   ;==>CloseBattle


Func SmartAttackStrategy($imode)
	RunExecutionConfigureSmartAttackForMode($imode)
	If ($g_abAttackStdSmartAttack[$imode]) Then
		SetLog("Calculating Smart Attack Strategy", $COLOR_INFO)
		Local $hTimer = __TimerInit()
			_CaptureRegion2()
			_GetRedArea()
			If RunExecutionSmartAttackEnabled() And Not SmartAttackCombatSelectDeploymentSide() Then Return False

		SetLog("Calculated  (in " & Round(__TimerDiff($hTimer) / 1000, 2) & " seconds) :")

		If ($g_abAttackStdSmartNearCollectors[$imode][0] Or $g_abAttackStdSmartNearCollectors[$imode][1] Or $g_abAttackStdSmartNearCollectors[$imode][2]) Then
			SetLog("Locating Mines, Collectors & Drills", $COLOR_INFO)
			$hTimer = __TimerInit()
			Global $g_aiPixelMine[0]
			Global $g_aiPixelElixir[0]
			Global $g_aiPixelDarkElixir[0]
			Global $g_aiPixelNearCollector[0]
			; If drop troop near gold mine
			If $g_abAttackStdSmartNearCollectors[$imode][0] Then
				$g_aiPixelMine = GetLocationMine()
				If (IsArray($g_aiPixelMine)) Then
					_ArrayAdd($g_aiPixelNearCollector, $g_aiPixelMine, 0, "|", @CRLF, $ARRAYFILL_FORCE_STRING)
				EndIf
			EndIf
			; If drop troop near elixir collector
			If $g_abAttackStdSmartNearCollectors[$imode][1] Then
				$g_aiPixelElixir = GetLocationElixir()
				If (IsArray($g_aiPixelElixir)) Then
					_ArrayAdd($g_aiPixelNearCollector, $g_aiPixelElixir, 0, "|", @CRLF, $ARRAYFILL_FORCE_STRING)
				EndIf
			EndIf
			; If drop troop near dark elixir drill
			If $g_abAttackStdSmartNearCollectors[$imode][2] Then
				$g_aiPixelDarkElixir = GetLocationDarkElixir()
				If (IsArray($g_aiPixelDarkElixir)) Then
					_ArrayAdd($g_aiPixelNearCollector, $g_aiPixelDarkElixir, 0, "|", @CRLF, $ARRAYFILL_FORCE_STRING)
				EndIf
			EndIf
			SetLog("Located  (in " & Round(__TimerDiff($hTimer) / 1000, 2) & " seconds) :")
			SetLog("[" & UBound($g_aiPixelMine) & "] Gold Mines")
			SetLog("[" & UBound($g_aiPixelElixir) & "] Elixir Collectors")
			SetLog("[" & UBound($g_aiPixelDarkElixir) & "] Dark Elixir Drill/s")
			$g_aiNbrOfDetectedMines[$imode] += UBound($g_aiPixelMine)
			$g_aiNbrOfDetectedCollectors[$imode] += UBound($g_aiPixelElixir)
			$g_aiNbrOfDetectedDrills[$imode] += UBound($g_aiPixelDarkElixir)
			UpdateStats()
		EndIf

	EndIf
	Return True
EndFunc   ;==>SmartAttackStrategy
