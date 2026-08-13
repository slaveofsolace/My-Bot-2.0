[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$AutoItRoot,

    [Parameter(Mandatory = $true)]
    [string]$Version,

    [string]$ReportPath = "autoit-validation.json"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$autoItRootPath = (Resolve-Path $AutoItRoot).Path
$autoItExe = Get-ChildItem -Path $autoItRootPath -Recurse -File -Filter "AutoIt3.exe" |
    Where-Object { $_.Name -eq "AutoIt3.exe" } |
    Select-Object -First 1
$au3CheckExe = Get-ChildItem -Path $autoItRootPath -Recurse -File -Filter "Au3Check.exe" |
    Select-Object -First 1

if (-not $autoItExe) {
    throw "AutoIt3.exe was not found under $autoItRootPath"
}
if (-not $au3CheckExe) {
    throw "Au3Check.exe was not found under $autoItRootPath"
}

$signature = Get-AuthenticodeSignature -FilePath $autoItExe.FullName
if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    throw "AutoIt executable signature is not valid: $($signature.Status)"
}

$includeDirectory = Join-Path $autoItExe.Directory.FullName "Include"
if (-not (Test-Path $includeDirectory)) {
    $includeDirectory = (Get-ChildItem -Path $autoItRootPath -Recurse -Directory -Filter "Include" | Select-Object -First 1).FullName
}
if (-not $includeDirectory -or -not (Test-Path $includeDirectory)) {
    throw "AutoIt standard include directory was not found"
}

$results = [System.Collections.Generic.List[object]]::new()
$logsDirectory = Join-Path $repositoryRoot "artifacts\autoit-$Version"
New-Item -ItemType Directory -Path $logsDirectory -Force | Out-Null

function Invoke-Au3Check {
    param([Parameter(Mandatory = $true)][string]$RelativePath)

    $scriptPath = (Resolve-Path (Join-Path $repositoryRoot $RelativePath)).Path
    $arguments = @(
        "-q",
        "-w", "2",
        "-w", "7",
        "-I", $includeDirectory,
        $scriptPath
    )
    $output = & $au3CheckExe.FullName @arguments 2>&1
    $exitCode = $LASTEXITCODE
    $safeName = ($RelativePath -replace '[^A-Za-z0-9_.-]', '_') + ".log"
    $logPath = Join-Path $logsDirectory $safeName
    @($output) | Set-Content -Path $logPath -Encoding UTF8

    $results.Add([pscustomobject]@{
        kind = "au3check"
        path = $RelativePath
        exit_code = $exitCode
        log = $logPath.Substring($repositoryRoot.Length + 1)
    })

    # Official Au3Check exit codes: 0 success, 1 warnings, 2 syntax errors, 3 usage/input error.
    if ($exitCode -ge 2) {
        Write-Host ($output -join [Environment]::NewLine)
        throw "Au3Check failed for $RelativePath with exit code $exitCode"
    }
}

$testScripts = @(
    "tests\autoit\RunContractsTest.au3",
    "tests\autoit\GameCatalogTest.au3",
    "tests\autoit\RunEngineTest.au3",
    "tests\autoit\RunVillageReadinessTest.au3",
    "tests\autoit\PassiveCurrentArmyReadinessTest.au3",
    "tests\autoit\HomeMaintenanceRouteTest.au3",
    "tests\autoit\ClanRequestRouteTest.au3",
    "tests\autoit\ManualViewportMappingTest.au3",
    "tests\autoit\SmartAttackPolicyTest.au3",
    "tests\autoit\EngineProbeLifecycleTest.au3"
)

Push-Location $repositoryRoot
try {
    $entryPoints = @(
        "My Bot 2.0.au3",
        "MyBot.run.au3",
        "MyBot.run.MiniGui.au3",
        "MyBot.run.Watchdog.au3",
        "MyBot.run.Wmi.au3",
        "MyBot.run.EngineProbe.au3"
    ) + $testScripts

    foreach ($entryPoint in $entryPoints) {
        Invoke-Au3Check -RelativePath $entryPoint
    }

    foreach ($relativeTest in $testScripts) {
        $testScript = (Resolve-Path (Join-Path $repositoryRoot $relativeTest)).Path
        $testName = [System.IO.Path]::GetFileNameWithoutExtension($relativeTest)
        $runtimeOutput = & $autoItExe.FullName "/ErrorStdOut" $testScript 2>&1
        $runtimeExitCode = $LASTEXITCODE
        $runtimeLog = Join-Path $logsDirectory "$testName.runtime.log"
        @($runtimeOutput) | Set-Content -Path $runtimeLog -Encoding UTF8
        $results.Add([pscustomobject]@{
            kind = "runtime"
            path = $relativeTest
            exit_code = $runtimeExitCode
            log = $runtimeLog.Substring($repositoryRoot.Length + 1)
        })
        if ($runtimeExitCode -ne 0) {
            Write-Host ($runtimeOutput -join [Environment]::NewLine)
            throw "AutoIt test $relativeTest failed with exit code $runtimeExitCode"
        }
    }
}
finally {
    Pop-Location
}

$report = [ordered]@{
    schema_version = 1
    autoit_version = $Version
    autoit_executable = $autoItExe.FullName
    signer = $signature.SignerCertificate.Subject
    checks = $results.Count
    results = $results
}
$report | ConvertTo-Json -Depth 6 | Set-Content -Path $ReportPath -Encoding UTF8
Write-Host "AutoIt $Version validation passed with $($results.Count) checks."
