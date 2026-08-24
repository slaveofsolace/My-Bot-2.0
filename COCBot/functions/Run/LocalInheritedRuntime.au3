; #FUNCTION# ====================================================================================================================
; Name ..........: LocalInheritedRuntime
; Description ...: Attests one exact owner-local pinned inherited runtime without launching it.
; Remarks .......: Exact OG startup performs host/emulator discovery, profile/private-folder migration, TCP startup,
;                  authentication/update work, and emulator-version checks before the user presses Start. That cannot
;                  satisfy a no-input, no-network, no-account proof. Product automation and passive executable launch
;                  therefore remain unavailable. Static tuple/profile validation never executes inherited code.
; ===============================================================================================================================
#include-once

Global Const $LOCAL_INHERITED_RUNTIME_SOURCE_COMMIT = "8ad6e5a552347acc2fcb8048d30262e2735a0c33"
Global Const $LOCAL_INHERITED_RUNTIME_SOURCE_TREE = "3e621065821be85d5932bd7e1f69ef7f22bc5b3d"
Global Const $LOCAL_INHERITED_RUNTIME_ATTESTATION_SHA256 = "5bb1f1c99260a431b19611d2f647b0e9dec243a6255e5c33d0f868016b9b72af"
Global Const $LOCAL_INHERITED_RUNTIME_TREE_FILE_COUNT = 2506
Global Const $LOCAL_INHERITED_RUNTIME_TREE_SHA256 = "0a807845216b84fe2f703f9c5a4f6a2f9a7c5547bb27875bfd886e7df0f77757"
Global Const $LOCAL_INHERITED_RUNTIME_ROOT = @LocalAppDataDir & "\My Bot 2.0\LocalInheritedRuntime\pinned-" & $LOCAL_INHERITED_RUNTIME_SOURCE_COMMIT
Global Const $LOCAL_INHERITED_RUNTIME_ATTESTATION = $LOCAL_INHERITED_RUNTIME_ROOT & "\local-inherited-runtime.local.json"
Global Const $LOCAL_INHERITED_RUNTIME_SAFETY = @ScriptDir & "\config\local-inherited-runtime-safety.json"
Global Const $LOCAL_INHERITED_RUNTIME_PROOF_PARENT = @LocalAppDataDir & "\My Bot 2.0\LocalInheritedRuntime\ProofProfiles"
Global Const $LOCAL_INHERITED_RUNTIME_PROOF_RECEIPT = "proof-profile.local.json"
Global Const $LOCAL_INHERITED_RUNTIME_PROOF_SCHEMA = "my-bot-local-inherited-proof-profile-v2"
Global Const $LOCAL_INHERITED_RUNTIME_PROOF_PROFILE = "Proof"
Global Const $LOCAL_INHERITED_RUNTIME_PROOF_MODE = "unlaunched-static-only"
Global Const $LOCAL_INHERITED_RUNTIME_SOURCE_DATA_POLICY = "hash-source-copy-zero-files"
Global Const $LOCAL_INHERITED_RUNTIME_PROOF_CONFIG_SHA256 = "66fb27b395bbac645c825410a383053786aeb1f2194d51b6b7a6d6e3df993a45"
Global Const $LOCAL_INHERITED_RUNTIME_PROFILE_SELECTOR_SHA256 = "8290b2a419da32531c29ec1068dbc7f4c6761adf6f85c1a9f2b7c11d68991ba1"
Global Const $LOCAL_INHERITED_RUNTIME_OWNER_RECEIPT = @LocalAppDataDir & "\My Bot 2.0\local-inherited-runtime-owner-v2.local.json"
Global Const $LOCAL_INHERITED_RUNTIME_AUTOMATION_ERROR = _
		"Full-profile inherited automation is unavailable: its API 1.1 command channel is unauthenticated, " & _
		"internal restart paths are not contained by /nwd, and reviewed GEM-confirm click sinks do not have a hard runtime interlock."
Global Const $LOCAL_INHERITED_RUNTIME_LAUNCH_ERROR = _
		"Inherited executable launch is unavailable: exact OG startup performs host/emulator discovery, private-profile migration, " & _
		"TCP and authentication/update work, and emulator-version checks before user Start."

Global $g_sLocalInheritedRuntimeProofRoot = ""
Global $g_sLocalInheritedRuntimeProofTreeHash = ""
Global $g_sLocalInheritedRuntimeSourceProfileRoot = ""
Global $g_sLocalInheritedRuntimeSourceProfile = ""
Global $g_sLocalInheritedRuntimeSourceProfileHash = ""
Global $g_sLocalInheritedRuntimeState = "unavailable"
Global $g_sLocalInheritedRuntimeMessage = $LOCAL_INHERITED_RUNTIME_LAUNCH_ERROR

Func LocalInheritedRuntimeRoot()
	Return $LOCAL_INHERITED_RUNTIME_ROOT
EndFunc

Func LocalInheritedRuntimeOwnerReceiptPath()
	Return $LOCAL_INHERITED_RUNTIME_OWNER_RECEIPT
EndFunc

Func LocalInheritedRuntimeSourceCommit()
	Return $LOCAL_INHERITED_RUNTIME_SOURCE_COMMIT
EndFunc

Func LocalInheritedRuntimeSourceTree()
	Return $LOCAL_INHERITED_RUNTIME_SOURCE_TREE
EndFunc

Func LocalInheritedRuntimeAutomationAvailable()
	Return False
EndFunc

Func LocalInheritedRuntimeExecutableLaunchAvailable()
	Return False
EndFunc

Func LocalInheritedRuntimeAutomationError()
	Return $LOCAL_INHERITED_RUNTIME_AUTOMATION_ERROR
EndFunc

Func LocalInheritedRuntimeLaunchError()
	Return $LOCAL_INHERITED_RUNTIME_LAUNCH_ERROR
EndFunc

Func LocalInheritedRuntimeState()
	Return $g_sLocalInheritedRuntimeState
EndFunc

Func LocalInheritedRuntimeMessage()
	Return $g_sLocalInheritedRuntimeMessage
EndFunc

; These status hooks remain stable for callers but can never report an inherited child.
Func LocalInheritedRuntimePid()
	Return 0
EndFunc

Func LocalInheritedRuntimeCreated()
	Return ""
EndFunc

Func LocalInheritedRuntimePath()
	Return ""
EndFunc

Func LocalInheritedRuntimeParentPid()
	Return 0
EndFunc

Func LocalInheritedRuntimeWindow()
	Return 0
EndFunc

Func _LocalInheritedRuntimeFileHash($sPath)
	If Not FileExists($sPath) Then Return ""
	Local $vHash = _Crypt_HashFile($sPath, $CALG_SHA_256)
	If @error Or Not IsBinary($vHash) Then Return ""
	Local $sHash = StringLower(StringTrimLeft(String($vHash), 2))
	If Not StringRegExp($sHash, "^[0-9a-f]{64}$") Then Return ""
	Return $sHash
EndFunc

Func _LocalInheritedRuntimeRegularFile($sPath)
	If Not FileExists($sPath) Then Return False
	Local $sAttributes = FileGetAttrib($sPath)
	If @error Or StringInStr($sAttributes, "D") Or StringInStr($sAttributes, "L") Then Return False
	Return True
EndFunc

Func _LocalInheritedRuntimeCheckFile($sRelative, $iExpectedSize, $sExpectedHash, ByRef $sError)
	Local $sPath = $LOCAL_INHERITED_RUNTIME_ROOT & "\" & StringReplace($sRelative, "/", "\")
	If Not _LocalInheritedRuntimeRegularFile($sPath) Then
		$sError = "Required owner-local inherited runtime file is missing or redirected: " & $sRelative
		Return False
	EndIf
	If FileGetSize($sPath) <> $iExpectedSize Or _LocalInheritedRuntimeFileHash($sPath) <> $sExpectedHash Then
		$sError = "Owner-local inherited runtime tuple mismatch: " & $sRelative
		Return False
	EndIf
	Return True
EndFunc

Func _LocalInheritedRuntimeDirectoryDigest($sRoot, $sExcludedRelative, ByRef $iFileCount, ByRef $sError)
	$iFileCount = 0
	$sError = ""
	Local $sRootAttributes = FileGetAttrib($sRoot)
	If @error Or Not StringInStr($sRootAttributes, "D") Or StringInStr($sRootAttributes, "L") Then
		$sError = "Directory digest root is missing or redirected"
		Return ""
	EndIf
	Local $aDirectories = _FileListToArrayRec($sRoot, "*", $FLTAR_FOLDERS, $FLTAR_RECUR, $FLTAR_NOSORT, $FLTAR_FULLPATH)
	If IsArray($aDirectories) Then
		For $i = 1 To $aDirectories[0]
			Local $sDirectoryAttributes = FileGetAttrib($aDirectories[$i])
			If @error Or StringInStr($sDirectoryAttributes, "L") Then
				$sError = "Directory digest tree contains a redirected directory"
				Return ""
			EndIf
		Next
	EndIf
	Local $aFiles = _FileListToArrayRec($sRoot, "*", $FLTAR_FILES, $FLTAR_RECUR, $FLTAR_NOSORT, $FLTAR_FULLPATH)
	If @error Or Not IsArray($aFiles) Then
		$sError = "The complete directory file set could not be enumerated"
		Return ""
	EndIf
	Local $aRows[$aFiles[0]]
	For $i = 1 To $aFiles[0]
		Local $sPath = $aFiles[$i]
		If Not _LocalInheritedRuntimeRegularFile($sPath) Then
			$sError = "Directory digest tree contains a redirected or non-file entry"
			Return ""
		EndIf
		Local $sRelative = StringLower(StringReplace(StringTrimLeft($sPath, StringLen($sRoot) + 1), "\", "/"))
		If $sExcludedRelative <> "" And $sRelative = StringLower(StringReplace($sExcludedRelative, "\", "/")) Then ContinueLoop
		If StringRegExp($sRelative, "[\x00-\x1f]") Then
			$sError = "Directory digest tree contains an unsafe file name"
			Return ""
		EndIf
		Local $sHash = _LocalInheritedRuntimeFileHash($sPath)
		If $sHash = "" Then
			$sError = "Directory digest tree contains an unreadable file: " & $sRelative
			Return ""
		EndIf
		$aRows[$iFileCount] = $sRelative & @TAB & FileGetSize($sPath) & @TAB & $sHash & @LF
		$iFileCount += 1
	Next
	If $iFileCount <= 0 Then
		$sError = "Directory digest tree is empty"
		Return ""
	EndIf
	ReDim $aRows[$iFileCount]
	_ArraySort($aRows)
	Local $sManifest = ""
	For $i = 0 To $iFileCount - 1
		$sManifest &= $aRows[$i]
	Next
	Local $vHash = _Crypt_HashData(StringToBinary($sManifest, 4), $CALG_SHA_256)
	If @error Or Not IsBinary($vHash) Then
		$sError = "The complete directory manifest could not be hashed"
		Return ""
	EndIf
	Return StringLower(StringTrimLeft(String($vHash), 2))
EndFunc

Func _LocalInheritedRuntimeTreeDigest(ByRef $iFileCount, ByRef $sError)
	Return _LocalInheritedRuntimeDirectoryDigest($LOCAL_INHERITED_RUNTIME_ROOT, "local-inherited-runtime.local.json", $iFileCount, $sError)
EndFunc

Func _LocalInheritedRuntimeWarningHtml(ByRef $sFoundPath)
	$sFoundPath = ""
	Local $aPatterns[2] = [$LOCAL_INHERITED_RUNTIME_ROOT & "\*.html", $LOCAL_INHERITED_RUNTIME_ROOT & "\lib\*.html"]
	For $i = 0 To UBound($aPatterns) - 1
		Local $hFind = FileFindFirstFile($aPatterns[$i])
		If $hFind = -1 Then ContinueLoop
		Local $sName = FileFindNextFile($hFind)
		FileClose($hFind)
		If $sName <> "" Then
			$sFoundPath = StringLeft($aPatterns[$i], StringInStr($aPatterns[$i], "\", 0, -1)) & $sName
			Return True
		EndIf
	Next
	Return False
EndFunc

Func LocalInheritedRuntimeValidateIsland(ByRef $sError)
	$sError = ""
	Local $sRootAttributes = FileGetAttrib($LOCAL_INHERITED_RUNTIME_ROOT)
	If @error Or Not StringInStr($sRootAttributes, "D") Or StringInStr($sRootAttributes, "L") Then
		$sError = "The fixed owner-local inherited runtime island is missing or redirected"
		Return False
	EndIf
	Local $sWarningPath = ""
	If _LocalInheritedRuntimeWarningHtml($sWarningPath) Then
		$sError = "An unauthorized-use HTML artifact exists inside the owner-local runtime island: " & $sWarningPath
		Return False
	EndIf
	Local $iTreeFiles = 0
	Local $sTreeHash = _LocalInheritedRuntimeTreeDigest($iTreeFiles, $sError)
	If $sTreeHash = "" Then Return False
	If $iTreeFiles <> $LOCAL_INHERITED_RUNTIME_TREE_FILE_COUNT Or $sTreeHash <> $LOCAL_INHERITED_RUNTIME_TREE_SHA256 Then
		$sError = "The complete owner-local inherited runtime tree has an extra, missing, or modified file"
		Return False
	EndIf
	Local $aPaths[6] = ["MyBot.run.exe", "MyBot.run.MiniGui.exe", "MyBot.run.Watchdog.exe", "MyBot.run.Wmi.exe", "lib/MyBot.run.dll", "MyBot.run.txt"]
	Local $aSizes[6] = [2957312, 1634304, 1159168, 1154048, 2761728, 0]
	Local $aHashes[6] = [ _
			"06eaa33280b7cfbba6efdbbf89a7796e2996b706e0a1dd1cb53b8e4c07353eb2", _
			"ae26c098ceb3c74e3d7f567834d9135257e094172e32140f4a5b615eaf90ceda", _
			"d4fa5bce748de1fd6f85ef85207c51433cb29af6204ae369145821a664f6612e", _
			"4beb637917e5303a92d59fcdfef176e8e568cfb450635a0941268e6336a35207", _
			"347b204a15fd56800130740aff639c7608621206482f07298c595a363e328699", _
			"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"]
	For $i = 0 To UBound($aPaths) - 1
		If Not _LocalInheritedRuntimeCheckFile($aPaths[$i], $aSizes[$i], $aHashes[$i], $sError) Then Return False
	Next
	If Not _LocalInheritedRuntimeRegularFile($LOCAL_INHERITED_RUNTIME_ATTESTATION) Or FileGetSize($LOCAL_INHERITED_RUNTIME_ATTESTATION) <> 1404 Or _
			_LocalInheritedRuntimeFileHash($LOCAL_INHERITED_RUNTIME_ATTESTATION) <> $LOCAL_INHERITED_RUNTIME_ATTESTATION_SHA256 Then
		$sError = "The owner-local inherited runtime attestation does not match the complete pinned tuple"
		Return False
	EndIf
	Return True
EndFunc

Func _LocalInheritedRuntimeVerifyStaticProfile($sProfileRoot, ByRef $sError)
	Local $sConfig = $sProfileRoot & "\" & $LOCAL_INHERITED_RUNTIME_PROOF_PROFILE & "\config.ini"
	If Not _LocalInheritedRuntimeRegularFile($sConfig) Or FileGetSize($sConfig) <= 0 Or FileGetSize($sConfig) > 64 * 1024 Then
		$sError = "The static proof config is missing, redirected, empty, or unexpectedly large"
		Return False
	EndIf
	If _LocalInheritedRuntimeFileHash($sConfig) <> $LOCAL_INHERITED_RUNTIME_PROOF_CONFIG_SHA256 Then
		$sError = "The static proof config contains an owner value or unreviewed setting"
		Return False
	EndIf
	Local $sContractError = ""
	Local $oContract = RunPlanFileLoad($LOCAL_INHERITED_RUNTIME_SAFETY, $sContractError)
	If @error Or Not IsObj($oContract) Or $oContract.Count <> 7 Or Not $oContract.Exists("schema") Or _
			String($oContract.Item("schema")) <> "my-bot-local-inherited-profile-safety-v2" Or _
			String($oContract.Item("profile_copy_policy")) <> $LOCAL_INHERITED_RUNTIME_SOURCE_DATA_POLICY Or _
			String($oContract.Item("proof_config_sha256")) <> $LOCAL_INHERITED_RUNTIME_PROOF_CONFIG_SHA256 Or _
			String($oContract.Item("profile_selector_sha256")) <> $LOCAL_INHERITED_RUNTIME_PROFILE_SELECTOR_SHA256 Or _
			String($oContract.Item("proof_mode")) <> $LOCAL_INHERITED_RUNTIME_PROOF_MODE Then
		$sError = "The unlaunched static-proof safety contract is invalid: " & $sContractError
		Return False
	EndIf
	Local $aAllowed = $oContract.Item("allowed_proof_relative_paths")
	If Not IsArray($aAllowed) Or UBound($aAllowed) <> 2 Or String($aAllowed[0]) <> "Profiles/profile.ini" Or _
			String($aAllowed[1]) <> "Profiles/Proof/config.ini" Then
		$sError = "The static-proof allowed file set changed without adapter review"
		Return False
	EndIf
	Local $aRequired = $oContract.Item("required_profile_values")
	Local $aExpected[18] = [ _
			"general|AutoStart|0", "general|Restarted|0", "general|ChkVersion|0", "general|AutoStartDelay|0", _
			"general|DisposeWindows|0", "other|ChkSellRewards|0", "other|ChkAutoResume|0", "other|ChkDisableNotifications|1", _
			"SuperTroopsBoost|SuperTroopsEnable|0", "android|shared_prefs.update|0", "android|emulator|", "android|instance|", _
			"notify|TGEnabled|0", "notify|TGToken|", "notify|PBRemote|0", "notify|Origin|", _
			"ProfileSCID|OnlySCIDAccounts|0", "ProfileSCID|WhatSCIDAccount2Use|0"]
	If Not IsArray($aRequired) Or UBound($aRequired) <> UBound($aExpected) Then
		$sError = "The static-proof safety contract is missing reviewed boundaries"
		Return False
	EndIf
	For $i = 0 To UBound($aExpected) - 1
		If String($aRequired[$i]) <> $aExpected[$i] Then
			$sError = "The static-proof safety contract order or value changed without adapter review"
			Return False
		EndIf
		Local $iFirstSeparator = StringInStr($aExpected[$i], "|")
		Local $iSecondSeparator = StringInStr($aExpected[$i], "|", 0, 2)
		If $iFirstSeparator <= 1 Or $iSecondSeparator <= $iFirstSeparator + 1 Then
			$sError = "The static-proof safety contract contains an invalid required key"
			Return False
		EndIf
		Local $sSection = StringLeft($aExpected[$i], $iFirstSeparator - 1)
		Local $sKey = StringMid($aExpected[$i], $iFirstSeparator + 1, $iSecondSeparator - $iFirstSeparator - 1)
		Local $sExpectedValue = StringTrimLeft($aExpected[$i], $iSecondSeparator)
		Local $sMissing = "__MYBOT_REQUIRED_VALUE_MISSING__"
		Local $sActual = IniRead($sConfig, $sSection, $sKey, $sMissing)
		If $sActual = $sMissing Or StringStripWS($sActual, $STR_STRIPALL) <> StringStripWS($sExpectedValue, $STR_STRIPALL) Then
			$sError = "Static proof requires [" & $sSection & "] " & $sKey & "=" & $sExpectedValue
			Return False
		EndIf
	Next
	Return True
EndFunc

Func LocalInheritedRuntimeValidateProofRoot($sProofRoot, ByRef $sError)
	$sError = ""
	Local $sProofAttributes = FileGetAttrib($sProofRoot)
	If @error Or Not StringInStr($sProofAttributes, "D") Or StringInStr($sProofAttributes, "L") Then
		$sError = "The static proof root is missing or redirected"
		Return False
	EndIf
	Local $sCanonicalParent = _CanonicalDirectoryPath($LOCAL_INHERITED_RUNTIME_PROOF_PARENT)
	Local $iParentError = @error
	Local $sCanonicalProof = _CanonicalDirectoryPath($sProofRoot)
	If $iParentError Or @error Or $sCanonicalParent = "" Or $sCanonicalProof = "" Then
		$sError = "The fixed static proof root could not be resolved"
		Return False
	EndIf
	Local $sExpectedPrefix = StringLower($sCanonicalParent & "\")
	If StringLeft(StringLower($sCanonicalProof), StringLen($sExpectedPrefix)) <> $sExpectedPrefix Then
		$sError = "The static proof root is outside the fixed owner-local proof parent"
		Return False
	EndIf
	Local $sProofName = StringTrimLeft($sCanonicalProof, StringLen($sCanonicalParent) + 1)
	If StringInStr($sProofName, "\") Or Not StringRegExp($sProofName, "^proof-[0-9a-f]{16}-[0-9a-f]{16}-[0-9a-f]{8}$") Then
		$sError = "The static proof root is not one exact prepared proof child"
		Return False
	EndIf
	Local $sReceipt = $sCanonicalProof & "\" & $LOCAL_INHERITED_RUNTIME_PROOF_RECEIPT
	If Not _LocalInheritedRuntimeRegularFile($sReceipt) Or FileGetSize($sReceipt) <= 0 Or FileGetSize($sReceipt) > 64 * 1024 Then
		$sError = "The static proof receipt is missing, redirected, empty, or unexpectedly large"
		Return False
	EndIf
	Local $sReceiptError = ""
	Local $oReceipt = RunPlanFileLoad($sReceipt, $sReceiptError)
	If @error Or Not IsObj($oReceipt) Or $oReceipt.Count <> 13 Then
		$sError = "The static proof receipt is invalid: " & $sReceiptError
		Return False
	EndIf
	Local $aReceiptKeys[13] = ["proof_mode", "proof_profile_name", "proof_tree_file_count", "proof_tree_sha256", _
			"safety_contract_sha256", "schema", "source_data_policy", "source_files_copied", "source_profile_file_count", _
			"source_profile_name", "source_profile_root", "source_profile_sha256", "source_verified_unchanged"]
	For $i = 0 To UBound($aReceiptKeys) - 1
		If Not $oReceipt.Exists($aReceiptKeys[$i]) Then
			$sError = "The static proof receipt is missing required field: " & $aReceiptKeys[$i]
			Return False
		EndIf
	Next
	If String($oReceipt.Item("schema")) <> $LOCAL_INHERITED_RUNTIME_PROOF_SCHEMA Or _
			String($oReceipt.Item("proof_mode")) <> $LOCAL_INHERITED_RUNTIME_PROOF_MODE Or _
			String($oReceipt.Item("proof_profile_name")) <> $LOCAL_INHERITED_RUNTIME_PROOF_PROFILE Or _
			String($oReceipt.Item("source_data_policy")) <> $LOCAL_INHERITED_RUNTIME_SOURCE_DATA_POLICY Or _
			Number($oReceipt.Item("source_files_copied")) <> 0 Or _
			Not IsBool($oReceipt.Item("source_verified_unchanged")) Or $oReceipt.Item("source_verified_unchanged") <> True Then
		$sError = "The static proof receipt schema or zero-copy claim is invalid"
		Return False
	EndIf
	Local $iProofFiles = Number($oReceipt.Item("proof_tree_file_count"))
	Local $iSourceFiles = Number($oReceipt.Item("source_profile_file_count"))
	Local $sProofHash = StringLower(String($oReceipt.Item("proof_tree_sha256")))
	Local $sSourceHash = StringLower(String($oReceipt.Item("source_profile_sha256")))
	Local $sSafetyHash = StringLower(String($oReceipt.Item("safety_contract_sha256")))
	If $iProofFiles <> 2 Or $iSourceFiles <= 0 Or Not StringRegExp($sProofHash, "^[0-9a-f]{64}$") Or _
			Not StringRegExp($sSourceHash, "^[0-9a-f]{64}$") Or Not StringRegExp($sSafetyHash, "^[0-9a-f]{64}$") Then
		$sError = "The static proof receipt counts or hashes are invalid"
		Return False
	EndIf
	Local $iProofActualFiles = 0
	Local $sProofActualHash = _LocalInheritedRuntimeDirectoryDigest($sCanonicalProof, $LOCAL_INHERITED_RUNTIME_PROOF_RECEIPT, $iProofActualFiles, $sError)
	If $sProofActualHash = "" Then Return False
	If $iProofActualFiles <> 2 Or $sProofActualHash <> $sProofHash Then
		$sError = "The static proof contains a source, credential, cache, log, or unknown file"
		Return False
	EndIf
	If _LocalInheritedRuntimeFileHash($LOCAL_INHERITED_RUNTIME_SAFETY) <> $sSafetyHash Then
		$sError = "The static proof safety contract changed after preparation"
		Return False
	EndIf
	Local $sProofProfiles = $sCanonicalProof & "\Profiles"
	Local $sSelector = $sProofProfiles & "\profile.ini"
	If Not _LocalInheritedRuntimeRegularFile($sSelector) Or _LocalInheritedRuntimeFileHash($sSelector) <> $LOCAL_INHERITED_RUNTIME_PROFILE_SELECTOR_SHA256 Then
		$sError = "The static proof profile selector is invalid"
		Return False
	EndIf
	If Not _LocalInheritedRuntimeVerifyStaticProfile($sProofProfiles, $sError) Then Return False
	Local $sSourceProfileRoot = String($oReceipt.Item("source_profile_root"))
	Local $sSourceProfile = String($oReceipt.Item("source_profile_name"))
	If $sSourceProfile = "" Or $sSourceProfile = "." Or $sSourceProfile = ".." Or StringRegExp($sSourceProfile, '[\/:*?"<>|]') Then
		$sError = "The source profile identity in the static proof receipt is invalid"
		Return False
	EndIf
	Local $sSourceAttributes = FileGetAttrib($sSourceProfileRoot)
	If @error Or Not StringInStr($sSourceAttributes, "D") Or StringInStr($sSourceAttributes, "L") Then
		$sError = "The source profile root is missing or redirected"
		Return False
	EndIf
	Local $sCanonicalSourceRoot = _CanonicalDirectoryPath($sSourceProfileRoot)
	Local $sCanonicalSourceProfile = _CanonicalDirectoryPath($sSourceProfileRoot & "\" & $sSourceProfile)
	If @error Or $sCanonicalSourceRoot = "" Or $sCanonicalSourceProfile = "" Or _
			StringLower($sCanonicalSourceProfile) <> StringLower($sCanonicalSourceRoot & "\" & $sSourceProfile) Then
		$sError = "The source profile no longer resolves to one exact child"
		Return False
	EndIf
	Local $iSourceActualFiles = 0
	Local $sSourceActualHash = _LocalInheritedRuntimeDirectoryDigest($sCanonicalSourceProfile, "", $iSourceActualFiles, $sError)
	If $sSourceActualHash = "" Then Return False
	If $iSourceActualFiles <> $iSourceFiles Or $sSourceActualHash <> $sSourceHash Then
		$sError = "The source profile changed after the zero-copy static proof was prepared"
		Return False
	EndIf
	$g_sLocalInheritedRuntimeProofRoot = $sCanonicalProof
	$g_sLocalInheritedRuntimeProofTreeHash = $sProofHash
	$g_sLocalInheritedRuntimeSourceProfileRoot = $sCanonicalSourceRoot
	$g_sLocalInheritedRuntimeSourceProfile = $sSourceProfile
	$g_sLocalInheritedRuntimeSourceProfileHash = $sSourceHash
	Return True
EndFunc

Func _LocalInheritedRuntimeWriteStaticReceipt($sOutcome, $sMessage)
	Local $sTemporary = $LOCAL_INHERITED_RUNTIME_OWNER_RECEIPT & "." & @AutoItPID & ".tmp"
	Local $sJson = "{"
	$sJson &= _RunEventJsonString("schema") & ":" & _RunEventJsonString("my-bot-local-inherited-runtime-owner-v2") & ","
	$sJson &= _RunEventJsonString("source_commit") & ":" & _RunEventJsonString($LOCAL_INHERITED_RUNTIME_SOURCE_COMMIT) & ","
	$sJson &= _RunEventJsonString("source_tree") & ":" & _RunEventJsonString($LOCAL_INHERITED_RUNTIME_SOURCE_TREE) & ","
	$sJson &= _RunEventJsonString("attestation_sha256") & ":" & _RunEventJsonString($LOCAL_INHERITED_RUNTIME_ATTESTATION_SHA256) & ","
	$sJson &= _RunEventJsonString("automation_available") & ":false,"
	$sJson &= _RunEventJsonString("executable_launch_available") & ":false,"
	$sJson &= _RunEventJsonString("automation_error") & ":" & _RunEventJsonString($LOCAL_INHERITED_RUNTIME_AUTOMATION_ERROR) & ","
	$sJson &= _RunEventJsonString("launch_error") & ":" & _RunEventJsonString($LOCAL_INHERITED_RUNTIME_LAUNCH_ERROR) & ","
	$sJson &= _RunEventJsonString("proof_mode") & ":" & _RunEventJsonString($LOCAL_INHERITED_RUNTIME_PROOF_MODE) & ","
	$sJson &= _RunEventJsonString("proof_root") & ":" & _RunEventJsonString($g_sLocalInheritedRuntimeProofRoot) & ","
	$sJson &= _RunEventJsonString("proof_tree_sha256") & ":" & _RunEventJsonString($g_sLocalInheritedRuntimeProofTreeHash) & ","
	$sJson &= _RunEventJsonString("source_profile_root") & ":" & _RunEventJsonString($g_sLocalInheritedRuntimeSourceProfileRoot) & ","
	$sJson &= _RunEventJsonString("source_profile") & ":" & _RunEventJsonString($g_sLocalInheritedRuntimeSourceProfile) & ","
	$sJson &= _RunEventJsonString("source_profile_sha256") & ":" & _RunEventJsonString($g_sLocalInheritedRuntimeSourceProfileHash) & ","
	$sJson &= _RunEventJsonString("state") & ":" & _RunEventJsonString($g_sLocalInheritedRuntimeState) & ","
	$sJson &= _RunEventJsonString("outcome") & ":" & _RunEventJsonString($sOutcome) & ","
	$sJson &= _RunEventJsonString("message") & ":" & _RunEventJsonString($sMessage) & "}"
	Local $hFile = FileOpen($sTemporary, BitOR($FO_OVERWRITE, $FO_CREATEPATH, $FO_UTF8_NOBOM))
	If $hFile = -1 Then Return False
	Local $bWritten = FileWrite($hFile, $sJson & @LF)
	Local $bFlushed = FileFlush($hFile)
	FileClose($hFile)
	If Not $bWritten Or Not $bFlushed Or Not FileMove($sTemporary, $LOCAL_INHERITED_RUNTIME_OWNER_RECEIPT, $FC_OVERWRITE) Then
		FileDelete($sTemporary)
		Return False
	EndIf
	Return True
EndFunc

Func LocalInheritedRuntimeValidateUnlaunchedReference($sProofRoot, ByRef $sError)
	If Not LocalInheritedRuntimeValidateIsland($sError) Or Not LocalInheritedRuntimeValidateProofRoot($sProofRoot, $sError) Then
		$g_sLocalInheritedRuntimeState = "static-reference-rejected"
		$g_sLocalInheritedRuntimeMessage = $sError
		Return False
	EndIf
	$g_sLocalInheritedRuntimeState = "static-reference-validated"
	$g_sLocalInheritedRuntimeMessage = "Exact local tuple and zero-copy proof profile validated; inherited code was not executed"
	If Not _LocalInheritedRuntimeWriteStaticReceipt("validated-unlaunched", $g_sLocalInheritedRuntimeMessage) Then
		$sError = "Static reference validation succeeded, but its durable owner receipt could not be written"
		$g_sLocalInheritedRuntimeState = "static-reference-receipt-failed"
		$g_sLocalInheritedRuntimeMessage = $sError
		Return False
	EndIf
	$sError = ""
	Return True
EndFunc

; Compatibility entry points fail closed. No inherited process is ever started or signalled.
Func LocalInheritedRuntimeLaunchPassiveReference($sProofRoot, $bExplicitPassiveProof, ByRef $sError)
	#forceref $sProofRoot, $bExplicitPassiveProof
	$sError = $LOCAL_INHERITED_RUNTIME_LAUNCH_ERROR
	Return False
EndFunc

Func LocalInheritedRuntimePassiveReferenceActive()
	Return False
EndFunc

Func LocalInheritedRuntimeRefreshPassiveReference()
	Return False
EndFunc

Func LocalInheritedRuntimeClosePassiveReference(ByRef $sError)
	$sError = $LOCAL_INHERITED_RUNTIME_LAUNCH_ERROR
	Return False
EndFunc

Func LocalInheritedRuntimeStart($sProfileRoot, $sProfile, ByRef $sError)
	#forceref $sProfileRoot, $sProfile
	$sError = $LOCAL_INHERITED_RUNTIME_AUTOMATION_ERROR
	Return False
EndFunc

Func LocalInheritedRuntimePause(ByRef $sError)
	$sError = $LOCAL_INHERITED_RUNTIME_AUTOMATION_ERROR
	Return False
EndFunc

Func LocalInheritedRuntimeResume(ByRef $sError)
	$sError = $LOCAL_INHERITED_RUNTIME_AUTOMATION_ERROR
	Return False
EndFunc

Func LocalInheritedRuntimeStop(ByRef $sError)
	$sError = $LOCAL_INHERITED_RUNTIME_AUTOMATION_ERROR
	Return False
EndFunc

Func LocalInheritedRuntimeClose(ByRef $sError)
	$sError = $LOCAL_INHERITED_RUNTIME_AUTOMATION_ERROR
	Return False
EndFunc
