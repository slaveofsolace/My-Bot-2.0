#NoTrayIcon
#include "..\..\COCBot\functions\Run\OpenHomeCollectorPolicy.au3"

Global $g_iAssertions = 0

Func AssertEqual($vExpected, $vActual, $sMessage)
	$g_iAssertions += 1
	If $vExpected <> $vActual Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & "; expected=" & $vExpected & "; actual=" & $vActual & @CRLF)
		Exit 10
	EndIf
EndFunc   ;==>AssertEqual

; Exact center samples from the supervised 2026-08-14 MyVillage Home pass.
AssertEqual($OPEN_HOME_COLLECTOR_GOLD, OpenHomeCollectorClassify(0xFFCC0C, 0), "live gold center is classified")
AssertEqual($OPEN_HOME_COLLECTOR_ELIXIR, OpenHomeCollectorClassify(0xE35AD8, 0), "live elixir center is classified")
AssertEqual($OPEN_HOME_COLLECTOR_DARK, OpenHomeCollectorClassify(0x89768F, 0x707070), "live dark-elixir center is classified")
AssertEqual($OPEN_HOME_COLLECTOR_NONE, OpenHomeCollectorClassify(0x7ABDE3, 0x7ABDE3), "Home sky signature is not a collector")
AssertEqual($OPEN_HOME_COLLECTOR_NONE, OpenHomeCollectorClassify(0x89768F, 0xFFE0FF), "dark center requires its bounded glyph context")

AssertEqual(0, OpenHomeCollectorGeometryScore(0xD7DCB9, 0xD7DCB9, 0xC8CEA0, 0xB4BC7B), "ideal current-client bubble has zero distance")
AssertEqual(-1, OpenHomeCollectorGeometryScore(0x000000, 0xD7DCB9, 0xC8CEA0, 0xB4BC7B), "missing pale edge fails closed")
AssertEqual(-1, OpenHomeCollectorGeometryScore(0xD7DCB9, 0xD7DCB9, 0xFFFFFF, 0xB4BC7B), "unbounded right edge fails closed")

ConsoleWrite("Open Home collector policy tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
