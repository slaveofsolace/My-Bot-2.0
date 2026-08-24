#NoTrayIcon
#include "..\..\COCBot\functions\Run\NoPremiumPermitPolicy.au3"

Global $g_iAssertions = 0

Func AssertEqual($vExpected, $vActual, $sMessage)
	$g_iAssertions += 1
	If $vExpected <> $vActual Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & "; expected=" & $vExpected & "; actual=" & $vActual & @CRLF)
		Exit 10
	EndIf
EndFunc   ;==>AssertEqual

AssertEqual(True, NoPremiumPermitActionKnown($NO_PREMIUM_ACTION_COLLECTOR_GOLD), "reviewed collector action is known")
AssertEqual(True, NoPremiumPermitActionKnown($NO_PREMIUM_ACTION_DAILY_REWARD_CLAIM), "reviewed reward action is known")
AssertEqual(True, NoPremiumPermitActionKnown($NO_PREMIUM_ACTION_CLAN_REQUEST_ARMY), "reviewed Clan Request Army action is known")
AssertEqual(True, NoPremiumPermitActionKnown($NO_PREMIUM_ACTION_CLAN_REQUEST_REQUEST), "reviewed Clan Request button action is known")
AssertEqual(True, NoPremiumPermitActionKnown($NO_PREMIUM_ACTION_CLAN_REQUEST_SEND), "reviewed Clan Request Send action is known")
AssertEqual(True, NoPremiumPermitActionKnown($NO_PREMIUM_ACTION_CLAN_REQUEST_CANCEL), "reviewed Clan Request Cancel action is known")
AssertEqual(True, NoPremiumPermitActionKnown($NO_PREMIUM_ACTION_CLAN_REQUEST_CLOSE), "reviewed Clan Request close action is known")
AssertEqual(False, NoPremiumPermitActionKnown("home"), "generic Home route is unavailable")
AssertEqual(False, NoPremiumPermitActionKnown("builder-home"), "generic Builder Home route is unavailable")
AssertEqual(False, NoPremiumPermitActionKnown("home.treasury.confirm"), "Treasury confirmation is unavailable")

AssertEqual(True, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_COLLECTOR_DARK, 70, 100), "collector lower bound is admitted")
AssertEqual(True, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_COLLECTOR_DARK, 790, 600), "collector upper bound is admitted")
AssertEqual(False, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_COLLECTOR_DARK, 69, 100), "collector x below scan is rejected")
AssertEqual(False, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_COLLECTOR_DARK, 790, 601), "collector y beyond scan is rejected")
AssertEqual(True, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_LOOT_CART_OPEN, 15, 106), "left Loot Cart region is admitted")
AssertEqual(True, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_LOOT_CART_OPEN, 845, 541), "right Loot Cart region is admitted")
AssertEqual(True, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_LOOT_CART_OPEN, 430, 626), "bottom Loot Cart region is admitted")
AssertEqual(False, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_LOOT_CART_OPEN, 430, 300), "unscanned central Loot Cart point is rejected")
AssertEqual(True, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_LOOT_CART_COLLECT, 431, 608), "exact Loot Cart Collect point is admitted")
AssertEqual(False, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_LOOT_CART_COLLECT, 432, 608), "wrong Loot Cart Collect x is rejected")
AssertEqual(True, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_DAILY_REWARD_CLAIM, 592, 485), "reviewed Daily Reward candidate is admitted")
AssertEqual(False, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_DAILY_REWARD_CLAIM, 593, 485), "wrong Daily Reward candidate is rejected")
AssertEqual(True, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_TREASURY_CLOSE, 699, 182), "exact Treasury close point is admitted")
AssertEqual(False, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_TREASURY_CLOSE, 699, 183), "wrong Treasury close point is rejected")
AssertEqual(True, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_CLAN_REQUEST_ARMY, 39, 585), "exact Clan Request Army point is admitted")
AssertEqual(False, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_CLAN_REQUEST_ARMY, 40, 585), "wrong Clan Request Army point is rejected")
AssertEqual(True, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_CLAN_REQUEST_REQUEST, 761, 498), "exact Clan Request button point is admitted")
AssertEqual(False, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_CLAN_REQUEST_REQUEST, 761, 497), "wrong Clan Request button point is rejected")
AssertEqual(True, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_CLAN_REQUEST_SEND, 545, 478), "exact Clan Request Send point is admitted")
AssertEqual(False, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_CLAN_REQUEST_SEND, 546, 478), "wrong Clan Request Send point is rejected")
AssertEqual(True, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_CLAN_REQUEST_CANCEL, 316, 478), "exact Clan Request Cancel point is admitted")
AssertEqual(False, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_CLAN_REQUEST_CANCEL, 316, 479), "wrong Clan Request Cancel point is rejected")
AssertEqual(True, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_CLAN_REQUEST_CLOSE, 792, 187), "exact Clan Request close point is admitted")
AssertEqual(False, NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_CLAN_REQUEST_CLOSE, 791, 187), "wrong Clan Request close point is rejected")

AssertEqual(True, NoPremiumPermitPointMatches(431, 608, 431, 608), "exact egress point matches")
AssertEqual(False, NoPremiumPermitPointMatches(431, 608, 432, 608), "changed egress x fails closed")
AssertEqual(False, NoPremiumPermitPointMatches(431, 608, 431, 607), "changed egress y fails closed")
AssertEqual(True, NoPremiumPermitAgeValid(0), "new permit is fresh")
AssertEqual(True, NoPremiumPermitAgeValid($NO_PREMIUM_INPUT_PERMIT_MAX_AGE_MS), "age boundary is fresh")
AssertEqual(False, NoPremiumPermitAgeValid($NO_PREMIUM_INPUT_PERMIT_MAX_AGE_MS + 1), "stale permit fails closed")
AssertEqual(False, NoPremiumPermitAgeValid(-1), "negative age fails closed")

ConsoleWrite("No-premium point permit policy tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
