[CmdletBinding()]
param(
    [string]$InstallDirectory,
    [string]$ProfileSourceDirectory,
    [switch]$Uninstall,
    [switch]$ValidateOnly,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$productName = "My Bot 2.0"
$productVersion = "2.0.0"
$packageRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$programsRoot = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA "Programs"))
if ([string]::IsNullOrWhiteSpace($InstallDirectory)) {
    $InstallDirectory = Join-Path $programsRoot $productName
}
$installRoot = [System.IO.Path]::GetFullPath($InstallDirectory).TrimEnd('\')
if (-not $installRoot.StartsWith($programsRoot.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "InstallDirectory must be below $programsRoot"
}
$userDataRoot = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA $productName)).TrimEnd('\')
$profilesRoot = Join-Path $userDataRoot "Profiles"

$startMenuDirectory = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\My Bot 2.0"
$shortcutPath = Join-Path $startMenuDirectory "My Bot 2.0.lnk"
$uninstallShortcutPath = Join-Path $startMenuDirectory "Uninstall My Bot 2.0.lnk"
$uninstallRegistryPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MyBot2.0"
$windowsPowerShellPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$integrationTestEnabled = [string]$env:MYBOT_RUN_POWERSHELL_INTEGRATION -ceq "1"
$integrationFailurePoint = [string]$env:MYBOT_TEST_INSTALL_FAILURE_POINT
$integrationRegistryPath = [string]$env:MYBOT_TEST_UNINSTALL_REGISTRY_PATH
$integrationMutationRequested = $integrationFailurePoint -ne "" -or $integrationRegistryPath -ne ""

if ($integrationMutationRequested) {
    if (-not $integrationTestEnabled) {
        throw "Installer test overrides require MYBOT_RUN_POWERSHELL_INTEGRATION=1."
    }
    if ([string]::IsNullOrWhiteSpace($env:MYBOT_INSTALL_TEST_ROOT)) {
        throw "Installer mutation tests require an isolated MYBOT_INSTALL_TEST_ROOT."
    }
    $integrationTestRoot = [System.IO.Path]::GetFullPath($env:MYBOT_INSTALL_TEST_ROOT).TrimEnd('\')
    $integrationTestPrefix = $integrationTestRoot + '\'
    foreach ($testScopedPath in @($env:LOCALAPPDATA, $env:APPDATA)) {
        $resolvedTestPath = [System.IO.Path]::GetFullPath([string]$testScopedPath)
        if (-not $resolvedTestPath.StartsWith($integrationTestPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Installer mutation tests require APPDATA and LOCALAPPDATA below MYBOT_INSTALL_TEST_ROOT."
        }
    }
    if ($integrationRegistryPath -notmatch '^HKCU:\\Software\\MyBot2\.0\.Tests\\[A-Fa-f0-9-]{32,36}$') {
        throw "Installer mutation tests require a GUID-scoped HKCU:\Software\MyBot2.0.Tests registry path."
    }
    if ($integrationFailurePoint -notin @("", "after-registration")) {
        throw "Unknown installer integration failure point: $integrationFailurePoint"
    }
    $uninstallRegistryPath = $integrationRegistryPath
}

function Get-Sha256Lower {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-ManifestFileSet {
    param([Parameter(Mandatory = $true)]$Manifest)

    $records = @($Manifest.files)
    if ($records.Count -eq 0) { throw "The package manifest contains no file records." }

    $manifestPaths = @{}
    foreach ($record in $records) {
        $relativePath = ([string]$record.path).Replace('\', '/')
        if ([string]::IsNullOrWhiteSpace($relativePath) -or
                [System.IO.Path]::IsPathRooted($relativePath) -or
                $relativePath.StartsWith('/') -or
                $relativePath -match '(^|/)\.\.(/|$)') {
            throw "The package manifest contains an unsafe path: $relativePath"
        }
        $key = $relativePath.ToLowerInvariant()
        if ($manifestPaths.ContainsKey($key)) {
            throw "The package manifest contains a duplicate path: $relativePath"
        }
        $bytes = 0L
        if (-not [int64]::TryParse([string]$record.bytes, [ref]$bytes) -or $bytes -lt 0) {
            throw "The package manifest contains an invalid byte count: $relativePath"
        }
        $sha256 = ([string]$record.sha256).ToLowerInvariant()
        if ($sha256 -notmatch '^[0-9a-f]{64}$') {
            throw "The package manifest contains an invalid SHA-256: $relativePath"
        }
        $manifestPaths[$key] = [pscustomobject]@{
            Path = $relativePath
            Bytes = $bytes
            Sha256 = $sha256
        }
    }

    $actualPaths = @{}
    $rootPrefix = $packageRoot.TrimEnd('\') + '\'
    foreach ($file in @(Get-ChildItem -LiteralPath $packageRoot -Recurse -File -Force)) {
        if (($file.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "The package contains a reparse-point file: $($file.FullName)"
        }
        $fullPath = [System.IO.Path]::GetFullPath($file.FullName)
        if (-not $fullPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "The package contains a file outside its root: $fullPath"
        }
        $relativePath = $fullPath.Substring($rootPrefix.Length).Replace('\', '/')
        if ($relativePath -ieq 'release-manifest.json') { continue }
        $key = $relativePath.ToLowerInvariant()
        if ($actualPaths.ContainsKey($key)) { throw "The package contains a duplicate path: $relativePath" }
        $actualPaths[$key] = $file
    }

    foreach ($key in $manifestPaths.Keys) {
        if (-not $actualPaths.ContainsKey($key)) {
            throw "A package file recorded by the manifest is missing: $($manifestPaths[$key].Path)"
        }
        $record = $manifestPaths[$key]
        $file = $actualPaths[$key]
        if ([int64]$file.Length -ne [int64]$record.Bytes) {
            throw "Package file byte count mismatch: $($record.Path)"
        }
        if ((Get-Sha256Lower -Path $file.FullName) -cne [string]$record.Sha256) {
            throw "Package file SHA-256 mismatch: $($record.Path)"
        }
    }
    foreach ($key in $actualPaths.Keys) {
        if (-not $manifestPaths.ContainsKey($key)) {
            $fullPath = $actualPaths[$key].FullName
            $relativePath = [System.IO.Path]::GetFullPath($fullPath).Substring($rootPrefix.Length).Replace('\', '/')
            throw "The package contains a file not recorded by the manifest: $relativePath"
        }
    }
}

function Assert-LocalRuntimePackage {
    $required = @(
        "release-manifest.json",
        "config\binary-provenance.json",
        "My Bot 2.0.exe",
        "MyBot.run.exe",
        "MyBot.run.EngineProbe.exe",
        "MyBot.run.EngineProbe.exe.config",
        "MyBot.run.MiniGui.exe",
        "MyBot.run.txt"
    )
    foreach ($relativePath in $required) {
        if (-not (Test-Path -LiteralPath (Join-Path $packageRoot $relativePath) -PathType Leaf)) {
            throw "This installer must be run from an extracted reviewed LocalRuntime package. Missing: $relativePath"
        }
    }
    if ((Get-Item -LiteralPath (Join-Path $packageRoot "MyBot.run.txt")).Length -ne 0) {
        throw "MyBot.run.txt must remain exactly zero bytes."
    }

    $manifest = Get-Content -LiteralPath (Join-Path $packageRoot "release-manifest.json") -Raw | ConvertFrom-Json
    if ([string]$manifest.mode -cne "LocalRuntime" -or
            -not ($manifest.source_tree_clean -is [bool]) -or
            $manifest.source_tree_clean -ne $true) {
        throw "The package manifest is not a clean LocalRuntime release."
    }
    Assert-ManifestFileSet -Manifest $manifest
    $provenance = Get-Content -LiteralPath (Join-Path $packageRoot "config\binary-provenance.json") -Raw | ConvertFrom-Json
    $launcherRecord = @($provenance.artifacts | Where-Object { ([string]$_.path).Replace('\', '/') -ieq "My Bot 2.0.exe" }) | Select-Object -First 1
    if ($null -eq $launcherRecord) { throw "Binary provenance does not contain My Bot 2.0.exe." }
    $launcherPath = Join-Path $packageRoot "My Bot 2.0.exe"
    if ((Get-Item -LiteralPath $launcherPath).Length -ne [long]$launcherRecord.bytes -or
            (Get-Sha256Lower -Path $launcherPath) -cne ([string]$launcherRecord.sha256).ToLowerInvariant()) {
        throw "My Bot 2.0.exe does not match binary provenance."
    }
}

function Get-OwnedRunningProcesses {
    if (-not (Test-Path -LiteralPath $installRoot -PathType Container)) { return @() }
    $prefix = $installRoot + '\'
    return @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
        try {
            $path = $_.Path
            -not [string]::IsNullOrWhiteSpace($path) -and
                [System.IO.Path]::GetFullPath($path).StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
        }
        catch { $false }
    })
}

function Test-SafeProfileName {
    param([AllowNull()][string]$Name)
    return -not [string]::IsNullOrWhiteSpace($Name) -and
        $Name -cmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$'
}

function Get-DefaultProfileName {
    param([Parameter(Mandatory = $true)][string]$IniPath)
    $section = ""
    foreach ($line in Get-Content -LiteralPath $IniPath) {
        $trimmed = ([string]$line).Trim()
        if ($trimmed -match '^\[([^\]]+)\]$') {
            $section = $Matches[1]
            continue
        }
        if ($section -ieq "general" -and $trimmed -match '^defaultprofile\s*=(.*)$') {
            return $Matches[1].Trim()
        }
    }
    return $null
}

function Assert-ProfileDirectory {
    param([Parameter(Mandatory = $true)][string]$Root)
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "Profiles directory does not exist: $Root"
    }
    $iniPath = Join-Path $Root "profile.ini"
    if (-not (Test-Path -LiteralPath $iniPath -PathType Leaf)) {
        throw "Profiles directory is missing profile.ini: $Root"
    }
    $profileName = Get-DefaultProfileName -IniPath $iniPath
    if (-not (Test-SafeProfileName -Name $profileName)) {
        throw "profile.ini must select a simple defaultprofile using only letters, numbers, dot, underscore, or hyphen."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $Root $profileName) -PathType Container)) {
        throw "profile.ini selects '$profileName', but that profile directory is missing."
    }
    return $profileName
}

function Initialize-UserProfiles {
    New-Item -ItemType Directory -Path $userDataRoot -Force | Out-Null

    if (-not [string]::IsNullOrWhiteSpace($ProfileSourceDirectory)) {
        $sourceRoot = [System.IO.Path]::GetFullPath($ProfileSourceDirectory).TrimEnd('\')
        if ($sourceRoot -ieq ([System.IO.Path]::GetFullPath($profilesRoot).TrimEnd('\'))) {
            throw "ProfileSourceDirectory already points to the installed per-user profiles directory."
        }
        $null = Assert-ProfileDirectory -Root $sourceRoot
        if (Test-Path -LiteralPath $profilesRoot) {
            $existing = @(Get-ChildItem -LiteralPath $profilesRoot -Force)
            if ($existing.Count -gt 0) {
                throw "Profile migration will not overwrite existing per-user data at $profilesRoot"
            }
        }

        $profileStage = Join-Path $userDataRoot (".Profiles.migration-" + [System.Guid]::NewGuid().ToString("N"))
        try {
            New-Item -ItemType Directory -Path $profileStage | Out-Null
            Get-ChildItem -LiteralPath $sourceRoot -Force | ForEach-Object {
                Copy-Item -LiteralPath $_.FullName -Destination $profileStage -Recurse
            }
            $null = Assert-ProfileDirectory -Root $profileStage
            if (Test-Path -LiteralPath $profilesRoot) {
                Remove-Item -LiteralPath $profilesRoot -Force
            }
            Move-Item -LiteralPath $profileStage -Destination $profilesRoot
        }
        finally {
            if (Test-Path -LiteralPath $profileStage) {
                Remove-Item -LiteralPath $profileStage -Recurse -Force
            }
        }
        return
    }

    if (-not (Test-Path -LiteralPath $profilesRoot)) {
        New-Item -ItemType Directory -Path $profilesRoot | Out-Null
    }
    $profileEntries = @(Get-ChildItem -LiteralPath $profilesRoot -Force)
    if ($profileEntries.Count -eq 0) {
        New-Item -ItemType Directory -Path (Join-Path $profilesRoot "MyVillage") | Out-Null
        $profileIni = "[general]`r`ndefaultprofile=MyVillage`r`n"
        [System.IO.File]::WriteAllText(
            (Join-Path $profilesRoot "profile.ini"),
            $profileIni,
            ([System.Text.UTF8Encoding]::new($false))
        )
    }
    $null = Assert-ProfileDirectory -Root $profilesRoot
}

function Remove-Registration {
    if (Test-Path -LiteralPath $shortcutPath) { Remove-Item -LiteralPath $shortcutPath -Force }
    if (Test-Path -LiteralPath $uninstallShortcutPath) { Remove-Item -LiteralPath $uninstallShortcutPath -Force }
    if (Test-Path -LiteralPath $startMenuDirectory) {
        $remaining = @(Get-ChildItem -LiteralPath $startMenuDirectory -Force)
        if ($remaining.Count -eq 0) { Remove-Item -LiteralPath $startMenuDirectory -Force }
    }
    if (Test-Path -LiteralPath $uninstallRegistryPath) { Remove-Item -LiteralPath $uninstallRegistryPath -Recurse -Force }
}

function Save-RegistrationSnapshot {
    param([Parameter(Mandatory = $true)][string]$BackupDirectory)

    try {
        New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null
        $snapshot = [ordered]@{
            StartMenuDirectoryExists = (Test-Path -LiteralPath $startMenuDirectory -PathType Container)
            ShortcutExists = (Test-Path -LiteralPath $shortcutPath -PathType Leaf)
            UninstallShortcutExists = (Test-Path -LiteralPath $uninstallShortcutPath -PathType Leaf)
            RegistryExists = (Test-Path -LiteralPath $uninstallRegistryPath)
            RegistryValues = @()
        }
        if ($snapshot.ShortcutExists) {
            Copy-Item -LiteralPath $shortcutPath -Destination (Join-Path $BackupDirectory "My Bot 2.0.lnk")
        }
        if ($snapshot.UninstallShortcutExists) {
            Copy-Item -LiteralPath $uninstallShortcutPath -Destination (Join-Path $BackupDirectory "Uninstall My Bot 2.0.lnk")
        }
        if ($snapshot.RegistryExists) {
            $registryKey = Get-Item -LiteralPath $uninstallRegistryPath
            $snapshot.RegistryValues = @($registryKey.GetValueNames() | ForEach-Object {
                [pscustomobject]@{
                    Name = [string]$_
                    Value = $registryKey.GetValue($_, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
                    Kind = [string]$registryKey.GetValueKind($_)
                }
            })
        }
        return [pscustomobject]$snapshot
    }
    catch {
        if (Test-Path -LiteralPath $BackupDirectory) {
            Remove-Item -LiteralPath $BackupDirectory -Recurse -Force -ErrorAction SilentlyContinue
        }
        throw
    }
}

function Restore-RegistrationSnapshot {
    param(
        [Parameter(Mandatory = $true)]$Snapshot,
        [Parameter(Mandatory = $true)][string]$BackupDirectory
    )

    Remove-Registration
    if ($Snapshot.StartMenuDirectoryExists -or $Snapshot.ShortcutExists -or $Snapshot.UninstallShortcutExists) {
        New-Item -ItemType Directory -Path $startMenuDirectory -Force | Out-Null
    }
    if ($Snapshot.ShortcutExists) {
        Copy-Item -LiteralPath (Join-Path $BackupDirectory "My Bot 2.0.lnk") -Destination $shortcutPath
    }
    if ($Snapshot.UninstallShortcutExists) {
        Copy-Item -LiteralPath (Join-Path $BackupDirectory "Uninstall My Bot 2.0.lnk") -Destination $uninstallShortcutPath
    }
    if ($Snapshot.RegistryExists) {
        New-Item -Path $uninstallRegistryPath -Force | Out-Null
        $registryKey = Get-Item -LiteralPath $uninstallRegistryPath
        foreach ($value in @($Snapshot.RegistryValues)) {
            $kind = [System.Enum]::Parse([Microsoft.Win32.RegistryValueKind], [string]$value.Kind)
            $registryKey.SetValue([string]$value.Name, $value.Value, $kind)
        }
    }
}

function Install-Registration {
    New-Item -ItemType Directory -Path $startMenuDirectory -Force | Out-Null
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $installRoot "My Bot 2.0.exe"
    $shortcut.WorkingDirectory = $installRoot
    $shortcut.IconLocation = (Join-Path $installRoot "My Bot 2.0.exe") + ",0"
    $shortcut.Description = "Launch My Bot 2.0"
    $shortcut.Save()

    $uninstallShortcut = $shell.CreateShortcut($uninstallShortcutPath)
    $uninstallShortcut.TargetPath = $windowsPowerShellPath
    $uninstallShortcut.Arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' +
        (Join-Path $installRoot "tools\Install-LocalRuntime.ps1") + '" -Uninstall'
    $uninstallShortcut.WorkingDirectory = $installRoot
    $uninstallShortcut.IconLocation = (Join-Path $installRoot "My Bot 2.0.exe") + ",0"
    $uninstallShortcut.Description = "Remove My Bot 2.0 for this Windows user"
    $uninstallShortcut.Save()

    New-Item -Path $uninstallRegistryPath -Force | Out-Null
    New-ItemProperty -Path $uninstallRegistryPath -Name DisplayName -Value $productName -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $uninstallRegistryPath -Name DisplayVersion -Value $productVersion -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $uninstallRegistryPath -Name Publisher -Value "My Bot 2.0 contributors" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $uninstallRegistryPath -Name InstallLocation -Value $installRoot -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $uninstallRegistryPath -Name DisplayIcon -Value ((Join-Path $installRoot "My Bot 2.0.exe") + ",0") -PropertyType String -Force | Out-Null
    $uninstallCommand = '"' + $windowsPowerShellPath +
        '" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "' +
        (Join-Path $installRoot "tools\Install-LocalRuntime.ps1") + '" -Uninstall'
    New-ItemProperty -Path $uninstallRegistryPath -Name UninstallString -Value $uninstallCommand -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $uninstallRegistryPath -Name NoModify -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path $uninstallRegistryPath -Name NoRepair -Value 1 -PropertyType DWord -Force | Out-Null
    if ($integrationTestEnabled -and $integrationFailurePoint -ceq "after-registration") {
        throw "Injected installer integration failure after registration mutation."
    }
}

function Assert-Registration {
    $expectedLauncher = [System.IO.Path]::GetFullPath((Join-Path $installRoot "My Bot 2.0.exe"))
    $expectedInstaller = [System.IO.Path]::GetFullPath((Join-Path $installRoot "tools\Install-LocalRuntime.ps1"))
    $expectedUninstallArguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + $expectedInstaller + '" -Uninstall'
    $expectedUninstallCommand = '"' + $windowsPowerShellPath + '" ' + $expectedUninstallArguments
    $shell = New-Object -ComObject WScript.Shell
    if (-not (Test-Path -LiteralPath $shortcutPath -PathType Leaf)) { throw "The Start Menu shortcut was not created." }
    $installedShortcut = $shell.CreateShortcut($shortcutPath)
    $installedShortcutTarget = [System.IO.Path]::GetFullPath($installedShortcut.TargetPath)
    $installedShortcutWorkingDirectory = [System.IO.Path]::GetFullPath($installedShortcut.WorkingDirectory)
    if (-not $installedShortcutTarget.Equals($expectedLauncher, [System.StringComparison]::OrdinalIgnoreCase) -or
            -not $installedShortcutWorkingDirectory.Equals($installRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "The Start Menu shortcut target or working directory is incorrect."
    }
    if (-not (Test-Path -LiteralPath $uninstallShortcutPath -PathType Leaf)) { throw "The uninstall shortcut was not created." }
    $installedUninstallShortcut = $shell.CreateShortcut($uninstallShortcutPath)
    $installedUninstallTarget = [System.IO.Path]::GetFullPath($installedUninstallShortcut.TargetPath)
    $installedUninstallWorkingDirectory = [System.IO.Path]::GetFullPath($installedUninstallShortcut.WorkingDirectory)
    if (-not $installedUninstallTarget.Equals([System.IO.Path]::GetFullPath($windowsPowerShellPath), [System.StringComparison]::OrdinalIgnoreCase) -or
            -not $installedUninstallWorkingDirectory.Equals($installRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
            [string]$installedUninstallShortcut.Arguments -cne $expectedUninstallArguments) {
        throw "The uninstall shortcut target, working directory, or command is incorrect."
    }
    if (-not (Test-Path -LiteralPath $uninstallRegistryPath)) { throw "The per-user uninstall key was not created." }
    $registration = Get-ItemProperty -LiteralPath $uninstallRegistryPath
    $registeredInstallLocation = [System.IO.Path]::GetFullPath([string]$registration.InstallLocation)
    if ([string]$registration.DisplayName -cne $productName -or
            [string]$registration.DisplayVersion -cne $productVersion -or
            -not $registeredInstallLocation.Equals($installRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
            [string]$registration.UninstallString -cne $expectedUninstallCommand) {
        throw "The per-user uninstall registration is incomplete or points at another installation."
    }
}

if ($Uninstall) {
    $running = @(Get-OwnedRunningProcesses)
    if ($running.Count -gt 0) {
        throw "Close My Bot 2.0 before uninstalling. Running PID(s): $($running.Id -join ', ')"
    }
    Remove-Registration
    if (Test-Path -LiteralPath $installRoot -PathType Container) {
        if ($packageRoot.StartsWith($installRoot + '\', [System.StringComparison]::OrdinalIgnoreCase) -or
                $packageRoot -ieq $installRoot) {
            $escapedRoot = $installRoot.Replace("'", "''")
            $cleanup = "Start-Sleep -Milliseconds 750; Remove-Item -LiteralPath '$escapedRoot' -Recurse -Force"
            Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
                -ArgumentList @("-NoLogo", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", $cleanup) `
                -WindowStyle Hidden | Out-Null
        }
        else {
            Remove-Item -LiteralPath $installRoot -Recurse -Force
        }
    }
    Write-Host "$productName was removed for the current Windows user."
    Write-Host "Profiles were retained at $profilesRoot"
    exit 0
}

Assert-LocalRuntimePackage
if ($ValidateOnly) {
    Write-Host "LocalRuntime package integrity verified."
    exit 0
}
$running = @(Get-OwnedRunningProcesses)
if ($running.Count -gt 0) {
    throw "Close the installed My Bot 2.0 before updating it. Running PID(s): $($running.Id -join ', ')"
}
Initialize-UserProfiles

$parent = Split-Path -Parent $installRoot
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$stage = Join-Path $parent (".My Bot 2.0.install-" + [System.Guid]::NewGuid().ToString("N"))
$backup = Join-Path $parent ".My Bot 2.0.previous"
$registrationBackup = Join-Path $parent (".My Bot 2.0.registration-" + [System.Guid]::NewGuid().ToString("N"))
$repairStatePath = Join-Path $parent ".My Bot 2.0.repair-required.json"
$registrationSnapshot = $null
$priorPayloadMoved = $false
$newPayloadInstalled = $false
$registrationTouched = $false
try {
    if (Test-Path -LiteralPath $backup) {
        throw "A preserved installer backup already exists at $backup. Repair or remove it before retrying."
    }
    if (Test-Path -LiteralPath $repairStatePath) {
        throw "A previous installer repair state exists at $repairStatePath. Resolve it before retrying."
    }
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    Get-ChildItem -LiteralPath $packageRoot -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $stage -Recurse -Force
    }
    $registrationSnapshot = Save-RegistrationSnapshot -BackupDirectory $registrationBackup
    if (Test-Path -LiteralPath $installRoot) {
        Move-Item -LiteralPath $installRoot -Destination $backup
        $priorPayloadMoved = $true
    }
    Move-Item -LiteralPath $stage -Destination $installRoot
    $newPayloadInstalled = $true

    $registrationTouched = $true
    Install-Registration
    Assert-Registration

    # The prior payload remains recoverable until both shortcuts and the HKCU uninstall key have
    # been read back and proven to point at the newly installed payload.
    if (Test-Path -LiteralPath $backup) {
        try { Remove-Item -LiteralPath $backup -Recurse -Force }
        catch { Write-Warning "Installation committed, but the verified prior-payload backup could not be removed: $backup" }
    }
    if (Test-Path -LiteralPath $registrationBackup) {
        Remove-Item -LiteralPath $registrationBackup -Recurse -Force -ErrorAction SilentlyContinue
    }
}
catch {
    $installFailure = $_
    $rollbackErrors = [System.Collections.Generic.List[string]]::new()
    if (-not $priorPayloadMoved -and
            (Test-Path -LiteralPath $backup -PathType Container) -and
            -not (Test-Path -LiteralPath $installRoot)) {
        $priorPayloadMoved = $true
    }
    if ($registrationTouched -and $null -ne $registrationSnapshot) {
        try {
            Restore-RegistrationSnapshot -Snapshot $registrationSnapshot -BackupDirectory $registrationBackup
        }
        catch {
            $rollbackErrors.Add("Registration rollback failed: $($_.Exception.Message)")
        }
    }
    if ($newPayloadInstalled) {
        try {
            if (Test-Path -LiteralPath $installRoot) { Remove-Item -LiteralPath $installRoot -Recurse -Force }
        }
        catch {
            $rollbackErrors.Add("New payload removal failed: $($_.Exception.Message)")
        }
    }
    if ($priorPayloadMoved) {
        try {
            if (Test-Path -LiteralPath $installRoot) {
                throw "The install directory is occupied; the preserved backup was not overwritten."
            }
            if (-not (Test-Path -LiteralPath $backup -PathType Container)) {
                throw "The preserved payload backup is missing."
            }
            Move-Item -LiteralPath $backup -Destination $installRoot
        }
        catch {
            $rollbackErrors.Add("Prior payload restore failed: $($_.Exception.Message)")
        }
    }

    if ($rollbackErrors.Count -gt 0) {
        $repairState = [ordered]@{
            schema_version = 1
            product = $productName
            install_root = $installRoot
            preserved_payload_backup = $backup
            registration_snapshot = $registrationBackup
            original_error = $installFailure.Exception.Message
            rollback_errors = @($rollbackErrors)
            created_utc = [DateTime]::UtcNow.ToString("o")
        }
        try {
            $repairState | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $repairStatePath -Encoding UTF8
        }
        catch {
            $rollbackErrors.Add("Repair-state write failed: $($_.Exception.Message)")
        }
        throw "Installation failed and rollback needs repair. Recovery state: $repairStatePath. $($rollbackErrors -join ' ')"
    }
    if (Test-Path -LiteralPath $registrationBackup) {
        Remove-Item -LiteralPath $registrationBackup -Recurse -Force -ErrorAction SilentlyContinue
    }
    throw $installFailure
}
finally {
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
}

Write-Host "$productName $productVersion installed at $installRoot"
Write-Host "Profiles: $profilesRoot"
Write-Host "Open Start and type: My Bot 2.0"
if (-not $NoLaunch) {
    Start-Process -FilePath (Join-Path $installRoot "My Bot 2.0.exe") -WorkingDirectory $installRoot
}
