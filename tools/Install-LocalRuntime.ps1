[CmdletBinding()]
param(
    [string]$InstallDirectory,
    [switch]$Uninstall,
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

$startMenuDirectory = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\My Bot 2.0"
$shortcutPath = Join-Path $startMenuDirectory "My Bot 2.0.lnk"
$uninstallShortcutPath = Join-Path $startMenuDirectory "Uninstall My Bot 2.0.lnk"
$uninstallRegistryPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MyBot2.0"

function Get-Sha256Lower {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-LocalRuntimePackage {
    $required = @(
        "release-manifest.json",
        "config\binary-provenance.json",
        "My Bot 2.0.exe",
        "MyBot.run.exe",
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
    if ([string]$manifest.mode -cne "LocalRuntime" -or $manifest.source_tree_clean -ne $true) {
        throw "The package manifest is not a clean LocalRuntime release."
    }
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

function Remove-Registration {
    if (Test-Path -LiteralPath $shortcutPath) { Remove-Item -LiteralPath $shortcutPath -Force }
    if (Test-Path -LiteralPath $uninstallShortcutPath) { Remove-Item -LiteralPath $uninstallShortcutPath -Force }
    if (Test-Path -LiteralPath $startMenuDirectory) {
        $remaining = @(Get-ChildItem -LiteralPath $startMenuDirectory -Force)
        if ($remaining.Count -eq 0) { Remove-Item -LiteralPath $startMenuDirectory -Force }
    }
    if (Test-Path -LiteralPath $uninstallRegistryPath) { Remove-Item -LiteralPath $uninstallRegistryPath -Recurse -Force }
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
    exit 0
}

Assert-LocalRuntimePackage
$running = @(Get-OwnedRunningProcesses)
if ($running.Count -gt 0) {
    throw "Close the installed My Bot 2.0 before updating it. Running PID(s): $($running.Id -join ', ')"
}

$parent = Split-Path -Parent $installRoot
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$stage = Join-Path $parent (".My Bot 2.0.install-" + [System.Guid]::NewGuid().ToString("N"))
$backup = Join-Path $parent ".My Bot 2.0.previous"
try {
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    Get-ChildItem -LiteralPath $packageRoot -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $stage -Recurse -Force
    }
    if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Recurse -Force }
    if (Test-Path -LiteralPath $installRoot) { Move-Item -LiteralPath $installRoot -Destination $backup }
    Move-Item -LiteralPath $stage -Destination $installRoot
    if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Recurse -Force }
}
catch {
    if (-not (Test-Path -LiteralPath $installRoot) -and (Test-Path -LiteralPath $backup)) {
        Move-Item -LiteralPath $backup -Destination $installRoot
    }
    throw
}
finally {
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
}

New-Item -ItemType Directory -Path $startMenuDirectory -Force | Out-Null
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $installRoot "My Bot 2.0.exe"
$shortcut.WorkingDirectory = $installRoot
$shortcut.IconLocation = (Join-Path $installRoot "My Bot 2.0.exe") + ",0"
$shortcut.Description = "Launch My Bot 2.0"
$shortcut.Save()

$uninstallShortcut = $shell.CreateShortcut($uninstallShortcutPath)
$uninstallShortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
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
$uninstallCommand = '"' + "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" +
    '" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "' +
    (Join-Path $installRoot "tools\Install-LocalRuntime.ps1") + '" -Uninstall'
New-ItemProperty -Path $uninstallRegistryPath -Name UninstallString -Value $uninstallCommand -PropertyType String -Force | Out-Null
New-ItemProperty -Path $uninstallRegistryPath -Name NoModify -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $uninstallRegistryPath -Name NoRepair -Value 1 -PropertyType DWord -Force | Out-Null

Write-Host "$productName $productVersion installed at $installRoot"
Write-Host "Open Start and type: My Bot 2.0"
if (-not $NoLaunch) {
    Start-Process -FilePath (Join-Path $installRoot "My Bot 2.0.exe") -WorkingDirectory $installRoot
}

