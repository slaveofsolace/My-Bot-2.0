#NoTrayIcon
#include <StringConstants.au3>
#include "..\..\COCBot\functions\Run\LootCartRoute.au3"

Global $g_iAssertions = 0
Global $g_sCartState = $LOOT_CART_STATE_AVAILABLE
Global $g_sCollectState = $LOOT_CART_STATE_COLLECT_READY
Global $g_iStopCalls = 0
Global $g_iStopAt = 0
Global $g_iDetectCartCalls = 0
Global $g_iCartCalls = 0
Global $g_iDetectCollectCalls = 0
Global $g_iCollectCalls = 0
Global $g_iHomeCalls = 0
Global $g_bCartAccepted = True
Global $g_bCollectAccepted = True
Global $g_bHomeProven = True

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc   ;==>AssertTrue

Func FixtureReset($sCart = $LOOT_CART_STATE_AVAILABLE, $sCollect = $LOOT_CART_STATE_COLLECT_READY, _
		$iStopAt = 0, $bCartAccepted = True, $bCollectAccepted = True, $bHomeProven = True)
	$g_sCartState = $sCart
	$g_sCollectState = $sCollect
	$g_iStopCalls = 0
	$g_iStopAt = $iStopAt
	$g_iDetectCartCalls = 0
	$g_iCartCalls = 0
	$g_iDetectCollectCalls = 0
	$g_iCollectCalls = 0
	$g_iHomeCalls = 0
	$g_bCartAccepted = $bCartAccepted
	$g_bCollectAccepted = $bCollectAccepted
	$g_bHomeProven = $bHomeProven
EndFunc   ;==>FixtureReset

Func FixtureStopRequested()
	$g_iStopCalls += 1
	Return $g_iStopAt > 0 And $g_iStopCalls >= $g_iStopAt
EndFunc   ;==>FixtureStopRequested

Func FixtureDetectCart()
	$g_iDetectCartCalls += 1
	If $g_sCartState = $LOOT_CART_STATE_AVAILABLE Then Return LootCartObservationCreate($g_sCartState, 420, 360)
	Return LootCartObservationCreate($g_sCartState)
EndFunc   ;==>FixtureDetectCart

Func FixtureIssueCart($iX, $iY)
	$g_iCartCalls += 1
	Return $g_bCartAccepted And $iX = 420 And $iY = 360
EndFunc   ;==>FixtureIssueCart

Func FixtureDetectCollect()
	$g_iDetectCollectCalls += 1
	If $g_sCollectState = $LOOT_CART_STATE_COLLECT_READY Then Return LootCartObservationCreate($g_sCollectState, 500, 640)
	Return LootCartObservationCreate($g_sCollectState)
EndFunc   ;==>FixtureDetectCollect

Func FixtureIssueCollect($iX, $iY)
	$g_iCollectCalls += 1
	Return $g_bCollectAccepted And $iX = 500 And $iY = 640
EndFunc   ;==>FixtureIssueCollect

Func FixtureProveHome()
	$g_iHomeCalls += 1
	Return $g_bHomeProven
EndFunc   ;==>FixtureProveHome

Func FixtureRun()
	Return LootCartRouteRunAdapter("FixtureDetectCart", "FixtureIssueCart", "FixtureDetectCollect", _
			"FixtureIssueCollect", "FixtureStopRequested", "FixtureProveHome")
EndFunc   ;==>FixtureRun

Local $oInvalid = LootCartObservationCreate($LOOT_CART_STATE_AVAILABLE, 900, 400)
AssertTrue(Not LootCartObservationValid($oInvalid), "coordinates outside the exact viewport are rejected")

FixtureReset()
Local $oCollected = FixtureRun()
AssertTrue(IsObj($oCollected), "successful fixture returns an outcome")
AssertTrue($oCollected.Item("state") = $LOOT_CART_OUTCOME_COLLECT_ISSUED, "one exact Collect is truthfully reported as issued")
AssertTrue($oCollected.Item("cart_attempts") = 1 And $oCollected.Item("cart_issued"), "cart open is attempted and accepted once")
AssertTrue($oCollected.Item("collect_attempts") = 1 And $oCollected.Item("collect_issued"), "Collect is attempted and accepted once")
AssertTrue($g_iCartCalls = 1 And $g_iCollectCalls = 1, "successful route invokes each input callback exactly once")
AssertTrue($g_iStopCalls = 5, "successful route polls Stop at every input boundary")
AssertTrue($g_iHomeCalls = 1 And $oCollected.Item("home_proven"), "successful route passively re-proves Home once")

FixtureReset($LOOT_CART_STATE_ABSENT)
Local $oUnavailable = FixtureRun()
AssertTrue($oUnavailable.Item("state") = $LOOT_CART_OUTCOME_UNAVAILABLE, "absent cart is unavailable")
AssertTrue($g_iCartCalls = 0 And $g_iCollectCalls = 0, "unavailable route issues no input")
AssertTrue($g_iHomeCalls = 1 And $oUnavailable.Item("home_proven"), "unavailable route still passively proves Home")

FixtureReset($LOOT_CART_STATE_AVAILABLE, $LOOT_CART_STATE_COLLECT_MISSING)
Local $oMissingCollect = FixtureRun()
AssertTrue($oMissingCollect.Item("state") = $LOOT_CART_OUTCOME_UNCONFIRMED, "missing Collect button is unconfirmed")
AssertTrue($oMissingCollect.Item("cart_issued") And Not $oMissingCollect.Item("collect_issued"), "missing Collect preserves exact input truth")
AssertTrue($g_iCartCalls = 1 And $g_iCollectCalls = 0, "missing Collect never uses a fallback input")
AssertTrue($g_iHomeCalls = 1, "missing Collect uses only passive Home proof after the cart input")

FixtureReset($LOOT_CART_STATE_AVAILABLE, $LOOT_CART_STATE_COLLECT_READY, 0, False)
Local $oCartRejected = FixtureRun()
AssertTrue($oCartRejected.Item("state") = $LOOT_CART_OUTCOME_UNCONFIRMED, "rejected cart input is unconfirmed")
AssertTrue($oCartRejected.Item("cart_attempts") = 1 And Not $oCartRejected.Item("cart_issued"), "rejected cart input consumes its one attempt without an issued receipt")
AssertTrue($g_iCollectCalls = 0, "rejected cart input cannot reach Collect")

FixtureReset($LOOT_CART_STATE_AVAILABLE, $LOOT_CART_STATE_COLLECT_READY, 0, True, False)
Local $oCollectRejected = FixtureRun()
AssertTrue($oCollectRejected.Item("state") = $LOOT_CART_OUTCOME_UNCONFIRMED, "rejected Collect input is unconfirmed")
AssertTrue($oCollectRejected.Item("collect_attempts") = 1 And Not $oCollectRejected.Item("collect_issued"), "rejected Collect consumes one attempt without an issued receipt")
AssertTrue($g_iCollectCalls = 1, "rejected Collect is never retried")

FixtureReset($LOOT_CART_STATE_AVAILABLE, $LOOT_CART_STATE_COLLECT_READY, 0, True, True, False)
Local $oHomeFailed = FixtureRun()
AssertTrue($oHomeFailed.Item("state") = $LOOT_CART_OUTCOME_UNCONFIRMED, "accepted Collect without Home proof remains unconfirmed")
AssertTrue($oHomeFailed.Item("collect_issued") And Not $oHomeFailed.Item("home_proven"), "Home failure preserves irreversible Collect truth")

For $iStopPoint = 1 To 2
	FixtureReset($LOOT_CART_STATE_AVAILABLE, $LOOT_CART_STATE_COLLECT_READY, $iStopPoint)
	Local $oCancelled = FixtureRun()
	AssertTrue($oCancelled.Item("state") = $LOOT_CART_OUTCOME_CANCELLED, "pre-input Stop point " & $iStopPoint & " cancels")
	AssertTrue($g_iCartCalls = 0 And $g_iCollectCalls = 0, "pre-input Stop point " & $iStopPoint & " issues no input")
	AssertTrue($g_iHomeCalls = 0, "pre-input Stop point " & $iStopPoint & " invokes no post-Stop callback")
Next

For $iStopPoint = 3 To 5
	FixtureReset($LOOT_CART_STATE_AVAILABLE, $LOOT_CART_STATE_COLLECT_READY, $iStopPoint)
	Local $oStopped = FixtureRun()
	AssertTrue($oStopped.Item("state") = $LOOT_CART_OUTCOME_UNCONFIRMED, "post-input Stop point " & $iStopPoint & " is unconfirmed")
	AssertTrue($oStopped.Item("cart_issued"), "post-input Stop point " & $iStopPoint & " preserves cart input truth")
	AssertTrue($g_iHomeCalls = 0, "post-input Stop point " & $iStopPoint & " invokes no capture or cleanup callback")
Next

ConsoleWrite("Loot Cart route tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
