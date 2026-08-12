#include <WinAPISysWin.au3>
#include "..\..\COCBot\functions\Other\ManualViewportMapping.au3"

Opt("MustDeclareVars", 1)

Global $g_iAssertions = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 1
	EndIf
EndFunc   ;==>AssertTrue

Local $aViewport[4] = [220, 196, 858, 730]
Local $iX = 220, $iY = 196
AssertTrue(Not IsArray(ManualViewportFindBlueStacks5Surface(0, 860, 732)), "invalid window cannot produce a viewport")
AssertTrue(ManualViewportMapToFramebuffer($iX, $iY, $aViewport, 860, 732), "top-left maps")
AssertTrue($iX = 0 And $iY = 0, "top-left maps to framebuffer origin")

$iX = 1077
$iY = 925
AssertTrue(ManualViewportMapToFramebuffer($iX, $iY, $aViewport, 860, 732), "bottom-right maps")
AssertTrue($iX = 859 And $iY = 731, "bottom-right maps to the final framebuffer pixel")

; The live TH17 raw point (430,345) projects to desktop (649,540) on the verified
; 858x730 BlueStacksApp child and must round-trip exactly.
$iX = 649
$iY = 540
AssertTrue(ManualViewportMapToFramebuffer($iX, $iY, $aViewport, 860, 732), "live interior point maps")
AssertTrue($iX = 430 And $iY = 345, "live interior point round-trips exactly")

$iX = 219
$iY = 540
AssertTrue(Not ManualViewportMapToFramebuffer($iX, $iY, $aViewport, 860, 732), "left advertisement rail is rejected")
AssertTrue($iX = 219 And $iY = 540, "rejected point is not mutated")

$iX = 1078
$iY = 540
AssertTrue(Not ManualViewportMapToFramebuffer($iX, $iY, $aViewport, 860, 732), "right edge outside viewport is rejected")
Local $aInvalid[3] = [0, 0, 10]
AssertTrue(Not ManualViewportMapToFramebuffer($iX, $iY, $aInvalid, 860, 732), "incomplete viewport is rejected")
AssertTrue(Not ManualViewportMapToFramebuffer($iX, $iY, $aViewport, 0, 732), "invalid framebuffer is rejected")

ConsoleWrite("ManualViewportMappingTest passed " & $g_iAssertions & " assertions" & @CRLF)
