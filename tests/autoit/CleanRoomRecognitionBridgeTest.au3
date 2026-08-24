#NoTrayIcon
Opt("MustDeclareVars", 1)

#include "..\..\COCBot\functions\Run\CleanRoomRecognitionBridge.au3"

Global $g_iAssertions = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc   ;==>AssertTrue

AssertTrue(CleanRoomRecognitionRuntimeStatus("GetOffSetRedline") = $CLEANROOM_RECOGNITION_STATUS_READ_ONLY_PURE, _
		"offset transform is explicitly read-only")
AssertTrue(CleanRoomRecognitionRuntimeStatus("GetDeployableNextTo") = $CLEANROOM_RECOGNITION_STATUS_READ_ONLY_PURE, _
		"deployable transform is explicitly read-only")
AssertTrue(CleanRoomRecognitionRuntimeStatus("FindTile") = $CLEANROOM_RECOGNITION_STATUS_FIXTURE_REPLAY_ONLY, _
		"FindTile is fixture-replay-only")
AssertTrue(Not CleanRoomRecognitionRuntimeAvailable("FindTile"), "fixture replay is never advertised runtime-ready")
AssertTrue(CleanRoomRecognitionRuntimeStatus("getoffsetredline") = $CLEANROOM_RECOGNITION_STATUS_REJECTED, _
		"export enums are case-sensitive")

Local $aUnavailable = StringSplit($CLEANROOM_RECOGNITION_UNAVAILABLE_EXPORTS, "|", 2)
AssertTrue(UBound($aUnavailable) = 14, "exactly fourteen exports remain unavailable")
Local $sUnavailable
For $sUnavailable In $aUnavailable
	AssertTrue(CleanRoomRecognitionRuntimeStatus($sUnavailable) = $CLEANROOM_RECOGNITION_STATUS_UNAVAILABLE, _
			"unavailable export remains explicit: " & $sUnavailable)
Next

AssertTrue(CleanRoomRecognitionFixtureReplayAttested($CLEANROOM_RECOGNITION_FIXTURE_ASSET_ID, _
		$CLEANROOM_RECOGNITION_FIXTURE_ID, $CLEANROOM_RECOGNITION_FIXTURE_IMAGE_SHA256, _
		$CLEANROOM_RECOGNITION_FIXTURE_METADATA_SHA256, $CLEANROOM_RECOGNITION_FIXTURE_WIDTH, _
		$CLEANROOM_RECOGNITION_FIXTURE_HEIGHT), "exact reviewed fixture receipt attests")
AssertTrue(Not CleanRoomRecognitionFixtureReplayAttested($CLEANROOM_RECOGNITION_FIXTURE_ASSET_ID, _
		$CLEANROOM_RECOGNITION_FIXTURE_ID, "0000000000000000000000000000000000000000000000000000000000000000", _
		$CLEANROOM_RECOGNITION_FIXTURE_METADATA_SHA256, $CLEANROOM_RECOGNITION_FIXTURE_WIDTH, _
		$CLEANROOM_RECOGNITION_FIXTURE_HEIGHT) And @error = 3, "fixture hash drift fails closed")

Local $aPoints[3][2] = [[100, 100], [760, 100], [100, 650]]
Local $aOffsetOutput = 0
Local $iOffsetCount = CleanRoomRecognitionGetOffsetRedline($aPoints, "TL", 10, 860, 732, $aOffsetOutput, 8)
AssertTrue(@error = 0 And $iOffsetCount = 1, "offset transform returns one bounded point")
AssertTrue(IsArray($aOffsetOutput) And $aOffsetOutput[0][0] < 100 And $aOffsetOutput[0][1] < 100, _
		"offset transform moves the TL point away from center")

Local $aOffsetAgain = 0
Local $iOffsetAgain = CleanRoomRecognitionGetOffsetRedline($aPoints, "TL", 10, 860, 732, $aOffsetAgain, 8)
AssertTrue($iOffsetAgain = $iOffsetCount And $aOffsetAgain[0][0] = $aOffsetOutput[0][0] And _
		$aOffsetAgain[0][1] = $aOffsetOutput[0][1], "offset transform is deterministic")

Local $aTargets[1][2] = [[300, 300]]
Local $aRedline[2][2] = [[280, 300], [500, 500]]
Local $aDeployableOutput = 0
Local $iDeployableCount = CleanRoomRecognitionGetDeployableNextTo($aTargets, $aRedline, 5, 860, 732, $aDeployableOutput, 8)
AssertTrue(@error = 0 And $iDeployableCount = 1, "deployable transform returns one bounded point")
AssertTrue($aDeployableOutput[0][0] = 275 And $aDeployableOutput[0][1] = 300, _
		"deployable transform matches the reviewed pure-coordinate contract")

Local $aInvalidOutput = 0
AssertTrue(CleanRoomRecognitionGetOffsetRedline($aPoints, "tl", 10, 860, 732, $aInvalidOutput, 8) = 0 And @error = 3, _
		"invalid area enum fails closed")
AssertTrue(CleanRoomRecognitionGetOffsetRedline($aPoints, "TL", 10, 860, 732, $aInvalidOutput, 33) = 0 And @error = 1, _
		"oversized result request fails closed")

Local $aSamePoint[1][2] = [[300, 300]]
AssertTrue(CleanRoomRecognitionGetDeployableNextTo($aTargets, $aSamePoint, 5, 860, 732, $aInvalidOutput, 8) = 0 And @error = 4, _
		"zero-vector deployable transform fails closed")

ConsoleWrite("Clean-room recognition bridge tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
