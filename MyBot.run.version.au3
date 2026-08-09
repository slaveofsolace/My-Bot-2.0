; #FUNCTION# ====================================================================================================================
; Name ..........: MBR Bot Version
; Description ...: This file contains the initialization and main loop sequences f0r the MBR Bot
; Author ........:  (2014)
; Modified ......:
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; Related .......:
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......: No
; ===============================================================================================================================

; AutoIt version pragmas
#Au3Stripper_Off
#pragma compile(Icon, "Images\MyBot.ico")
; MyBot.run.dll validates these native-host resources before enabling image recognition.
; Product branding remains separate below and in the native/browser window titles.
#pragma compile(FileDescription, Clash of Clans Bot - A Free Clash of Clans bot - https://mybot.run)
#pragma compile(ProductVersion, 8.2.0)
#pragma compile(FileVersion, 8.2.0)
#pragma compile(LegalCopyright, © https://mybot.run)
#Au3Stripper_On

Global Const $g_sProductName = "My Bot 2.0"
Global Const $g_sProductVersion = "v2.0.0"
Global Const $g_sEngineVersion = "v8.2.0"
Global $g_sBotVersion = "v8.2.0" ;~ Don't add more here, but below. Version can't be longer than vX.y.z because it is also used in Checkversion()

