#include-once

; Exact, source-owned one-shot input actions. There is deliberately no generic Home,
; Builder Home, dialog, confirmation, or full-profile action in this allowlist.
Global Const $NO_PREMIUM_ACTION_COLLECTOR_GOLD = "home.collector.gold"
Global Const $NO_PREMIUM_ACTION_COLLECTOR_ELIXIR = "home.collector.elixir"
Global Const $NO_PREMIUM_ACTION_COLLECTOR_DARK = "home.collector.dark-elixir"
Global Const $NO_PREMIUM_ACTION_LOOT_CART_OPEN = "home.loot-cart.open"
Global Const $NO_PREMIUM_ACTION_LOOT_CART_COLLECT = "home.loot-cart.collect"
Global Const $NO_PREMIUM_ACTION_DAILY_REWARD_CLAIM = "home.daily-reward.claim"
Global Const $NO_PREMIUM_ACTION_DAILY_REWARD_CLOSE = "home.daily-reward.close"
Global Const $NO_PREMIUM_ACTION_RECOVERY_RELOAD_GAME = "recovery.inactivity.reload-game"
Global Const $NO_PREMIUM_ACTION_TREASURY_CASTLE = "home.treasury.castle"
Global Const $NO_PREMIUM_ACTION_TREASURY_ENTRY = "home.treasury.entry"
Global Const $NO_PREMIUM_ACTION_TREASURY_CLOSE = "home.treasury.close"
Global Const $NO_PREMIUM_ACTION_CLAN_REQUEST_ARMY = "home.clan-request.army-overview"
Global Const $NO_PREMIUM_ACTION_CLAN_REQUEST_REQUEST = "home.clan-request.request"
Global Const $NO_PREMIUM_ACTION_CLAN_REQUEST_SEND = "home.clan-request.send"
Global Const $NO_PREMIUM_ACTION_CLAN_REQUEST_CANCEL = "home.clan-request.cancel"
Global Const $NO_PREMIUM_ACTION_CLAN_REQUEST_CLOSE = "home.clan-request.close"
Global Const $NO_PREMIUM_ACTION_EXACT_TRAINING_ARMY = "army.exact-recipe.army-overview"
Global Const $NO_PREMIUM_ACTION_BUILDER_SWITCH = "builder-base.switch"
Global Const $NO_PREMIUM_ACTION_BUILDER_COLLECT_GOLD = "builder-base.collect-gold"
Global Const $NO_PREMIUM_ACTION_BUILDER_COLLECT_ELIXIR = "builder-base.collect-elixir"
Global Const $NO_PREMIUM_ACTION_BUILDER_RETURN_HOME = "builder-base.return-home"
Global Const $NO_PREMIUM_ACTION_REGULAR_BATTLE_ENTRY_OPEN = "regular.battle-entry.open"
Global Const $NO_PREMIUM_ACTION_REGULAR_BATTLE_ENTRY_CLOSE = "regular.battle-entry.close"
Global Const $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_FIND_MATCH = "regular.battle-scout.find-match"
Global Const $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_CONFIRM_ARMY = "regular.battle-scout.confirm-army"
Global Const $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_END_BATTLE = "regular.battle-scout.end-battle"
Global Const $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_CONFIRM_SURRENDER = "regular.battle-scout.confirm-surrender"
Global Const $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_RETURN_HOME = "regular.battle-scout.return-home"
Global Const $NO_PREMIUM_ACTION_BUILDER_BATTLE_ENTRY_OPEN = "builder-base.battle-entry.open"
Global Const $NO_PREMIUM_ACTION_BUILDER_BATTLE_ENTRY_CLOSE = "builder-base.battle-entry.close"
Global Const $NO_PREMIUM_ACTION_HOME_CLEAR_SCREEN = "home.clear-screen"
Global Const $NO_PREMIUM_ACTION_STARTUP_POPUP_CLOSE = "startup.popup.close"
Global Const $NO_PREMIUM_ACTION_HOME_CLEAR_SELECTION = "home.clear-selection"

Global Const $NO_PREMIUM_INPUT_PERMIT_MAX_AGE_MS = 5000

Func NoPremiumPermitActionKnown($sAction)
	Switch StringLower(String($sAction))
		Case $NO_PREMIUM_ACTION_COLLECTOR_GOLD, $NO_PREMIUM_ACTION_COLLECTOR_ELIXIR, $NO_PREMIUM_ACTION_COLLECTOR_DARK, _
				$NO_PREMIUM_ACTION_LOOT_CART_OPEN, $NO_PREMIUM_ACTION_LOOT_CART_COLLECT, _
				$NO_PREMIUM_ACTION_DAILY_REWARD_CLAIM, $NO_PREMIUM_ACTION_DAILY_REWARD_CLOSE, _
			$NO_PREMIUM_ACTION_RECOVERY_RELOAD_GAME, _
                        $NO_PREMIUM_ACTION_TREASURY_CASTLE, $NO_PREMIUM_ACTION_TREASURY_ENTRY, $NO_PREMIUM_ACTION_TREASURY_CLOSE, _
                        $NO_PREMIUM_ACTION_CLAN_REQUEST_ARMY, $NO_PREMIUM_ACTION_CLAN_REQUEST_REQUEST, _
                        $NO_PREMIUM_ACTION_CLAN_REQUEST_SEND, $NO_PREMIUM_ACTION_CLAN_REQUEST_CANCEL, $NO_PREMIUM_ACTION_CLAN_REQUEST_CLOSE, _
                        $NO_PREMIUM_ACTION_EXACT_TRAINING_ARMY, _
                        $NO_PREMIUM_ACTION_BUILDER_SWITCH, $NO_PREMIUM_ACTION_BUILDER_COLLECT_GOLD, _
                        $NO_PREMIUM_ACTION_BUILDER_COLLECT_ELIXIR, $NO_PREMIUM_ACTION_BUILDER_RETURN_HOME, _
                        $NO_PREMIUM_ACTION_REGULAR_BATTLE_ENTRY_OPEN, $NO_PREMIUM_ACTION_REGULAR_BATTLE_ENTRY_CLOSE, _
                        $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_FIND_MATCH, $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_CONFIRM_ARMY, _
                        $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_END_BATTLE, $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_CONFIRM_SURRENDER, _
                        $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_RETURN_HOME, _
                        $NO_PREMIUM_ACTION_BUILDER_BATTLE_ENTRY_OPEN, $NO_PREMIUM_ACTION_BUILDER_BATTLE_ENTRY_CLOSE, _
                        $NO_PREMIUM_ACTION_HOME_CLEAR_SCREEN, $NO_PREMIUM_ACTION_STARTUP_POPUP_CLOSE, _
                        $NO_PREMIUM_ACTION_HOME_CLEAR_SELECTION
                        Return True
	EndSwitch
	Return False
EndFunc   ;==>NoPremiumPermitActionKnown

Func _NoPremiumPermitIntegerPoint($iX, $iY)
	If Not IsNumber($iX) Or Not IsNumber($iY) Then Return False
	Return Int($iX) = $iX And Int($iY) = $iY
EndFunc   ;==>_NoPremiumPermitIntegerPoint

Func _NoPremiumPermitMidOffsetY()
	If IsDeclared("g_iMidOffsetY") Then Return Int(Eval("g_iMidOffsetY"))
	Return 0
EndFunc   ;==>_NoPremiumPermitMidOffsetY

Func _NoPremiumPermitBottomOffsetY()
	If IsDeclared("g_iBottomOffsetY") Then Return Int(Eval("g_iBottomOffsetY"))
	Return 0
EndFunc   ;==>_NoPremiumPermitBottomOffsetY

; This validates only the canonical 860x732 action geometry. The current framebuffer
; predicate for the named action is independently required when the permit is granted
; and again when it is consumed immediately before the input transport.
Func NoPremiumPermitTargetValid($sAction, $iX, $iY)
	If Not _NoPremiumPermitIntegerPoint($iX, $iY) Then Return False
	$iX = Int($iX)
	$iY = Int($iY)
	Switch StringLower(String($sAction))
		Case $NO_PREMIUM_ACTION_COLLECTOR_GOLD, $NO_PREMIUM_ACTION_COLLECTOR_ELIXIR, $NO_PREMIUM_ACTION_COLLECTOR_DARK
			Return $iX >= 70 And $iX <= 790 And $iY >= 100 And $iY <= 600
		Case $NO_PREMIUM_ACTION_LOOT_CART_OPEN
			Return ($iX >= 15 And $iX <= 165 And $iY >= 106 And $iY <= 541) Or _
					($iX >= 695 And $iX <= 845 And $iY >= 106 And $iY <= 541) Or _
					($iX >= 165 And $iX <= 695 And $iY >= 541 And $iY <= 626)
		Case $NO_PREMIUM_ACTION_LOOT_CART_COLLECT
			Return $iX = 431 And $iY = 608
		Case $NO_PREMIUM_ACTION_DAILY_REWARD_CLAIM
			Return ($iY = 326 And ($iX = 149 Or $iX = 297 Or $iX = 445)) Or _
					($iY = 485 And ($iX = 149 Or $iX = 297 Or $iX = 445)) Or _
					($iX = 628 And $iY = 483)
		Case $NO_PREMIUM_ACTION_DAILY_REWARD_CLOSE
			Return $iX = 759 And $iY = 173
		Case $NO_PREMIUM_ACTION_RECOVERY_RELOAD_GAME
			Return $iX = 281 And $iY = 418
		Case $NO_PREMIUM_ACTION_TREASURY_CASTLE
			Return $iX >= 0 And $iX < 860 And $iY >= 0 And $iY < 732
		Case $NO_PREMIUM_ACTION_TREASURY_ENTRY
			Return $iX = 574 And $iY = 608
		Case $NO_PREMIUM_ACTION_TREASURY_CLOSE
			Return $iX = 699 And $iY = 182
		Case $NO_PREMIUM_ACTION_CLAN_REQUEST_ARMY
			Return $iX = 39 And $iY = 585
		Case $NO_PREMIUM_ACTION_CLAN_REQUEST_REQUEST
			Return $iX = 761 And $iY = 498
		Case $NO_PREMIUM_ACTION_CLAN_REQUEST_SEND
			Return $iX = 545 And $iY = 478
		Case $NO_PREMIUM_ACTION_CLAN_REQUEST_CANCEL
			Return $iX = 316 And $iY = 478
		Case $NO_PREMIUM_ACTION_CLAN_REQUEST_CLOSE
			Return $iX = 792 And $iY = 187
		Case $NO_PREMIUM_ACTION_EXACT_TRAINING_ARMY
			Return $iX = 39 And $iY = 585
                Case $NO_PREMIUM_ACTION_BUILDER_SWITCH
                        Return $iX = 145 And $iY = 620
                Case $NO_PREMIUM_ACTION_BUILDER_COLLECT_GOLD
			Return $iX >= 500 And $iX <= 530 And $iY >= 405 And $iY <= 435
		Case $NO_PREMIUM_ACTION_BUILDER_COLLECT_ELIXIR
			Return $iX >= 320 And $iX <= 350 And $iY >= 395 And $iY <= 420
                Case $NO_PREMIUM_ACTION_BUILDER_RETURN_HOME
                        Return $iX = 821 And $iY = 465
                Case $NO_PREMIUM_ACTION_REGULAR_BATTLE_ENTRY_OPEN
                        Return $iX = 62 And $iY = 685
                Case $NO_PREMIUM_ACTION_REGULAR_BATTLE_ENTRY_CLOSE
                        Return $iX = 820 And $iY = 42
                Case $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_FIND_MATCH
                        Return $iX = 160 And $iY = 470
                Case $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_CONFIRM_ARMY
                        Return $iX = 735 And $iY = 508 + _NoPremiumPermitMidOffsetY()
                Case $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_END_BATTLE
                        Return $iX = 70 And $iY = 545 + _NoPremiumPermitBottomOffsetY()
                Case $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_CONFIRM_SURRENDER
                        Return $iX = 535 And $iY = 435 + _NoPremiumPermitMidOffsetY()
                Case $NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_RETURN_HOME
                        Return $iX = 430 And $iY = 566 + _NoPremiumPermitMidOffsetY()
                Case $NO_PREMIUM_ACTION_BUILDER_BATTLE_ENTRY_OPEN
                        Return $iX = 62 And $iY = 685
                Case $NO_PREMIUM_ACTION_BUILDER_BATTLE_ENTRY_CLOSE
                        Return $iX = 748 And $iY = 204
                Case $NO_PREMIUM_ACTION_HOME_CLEAR_SCREEN
			Return ($iX >= 235 And $iX <= 245 And $iY >= 10 And $iY <= 30) Or _
					($iX >= 640 And $iX <= 650 And $iY >= 10 And $iY <= 30)
                Case $NO_PREMIUM_ACTION_STARTUP_POPUP_CLOSE
                        Return $iX >= 360 And $iX <= 510 And $iY >= 450 And $iY <= 540
                Case $NO_PREMIUM_ACTION_HOME_CLEAR_SELECTION
                        Return $iX = 175 And $iY = 10
	EndSwitch
	Return False
EndFunc   ;==>NoPremiumPermitTargetValid

Func NoPremiumPermitPointMatches($iExpectedX, $iExpectedY, $iActualX, $iActualY)
	If Not _NoPremiumPermitIntegerPoint($iExpectedX, $iExpectedY) Or _
			Not _NoPremiumPermitIntegerPoint($iActualX, $iActualY) Then Return False
	Return Int($iExpectedX) = Int($iActualX) And Int($iExpectedY) = Int($iActualY)
EndFunc   ;==>NoPremiumPermitPointMatches

Func NoPremiumPermitAgeValid($iAgeMs)
	If Not IsNumber($iAgeMs) Then Return False
	Return $iAgeMs >= 0 And $iAgeMs <= $NO_PREMIUM_INPUT_PERMIT_MAX_AGE_MS
EndFunc   ;==>NoPremiumPermitAgeValid
