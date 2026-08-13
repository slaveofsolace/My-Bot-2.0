[CmdletBinding()]
param(
    [string]$InstallDirectory,
    [string]$ProfileSourceDirectory,
    [switch]$Uninstall,
    [switch]$ValidateOnly,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$pythonInstaller = Join-Path $PSScriptRoot "install_local_runtime.py"
if (-not (Test-Path -LiteralPath $pythonInstaller -PathType Leaf)) {
    throw "The standard-library Python LocalRuntime installer is missing: $pythonInstaller"
}

$python = $null
$prefix = @()
$pyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
if ($null -ne $pyLauncher) {
    $python = $pyLauncher.Source
    $prefix = @("-3")
}
else {
    $pythonCommand = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($null -ne $pythonCommand) { $python = $pythonCommand.Source }
}
if ([string]::IsNullOrWhiteSpace($python)) {
    throw "Python 3 is required to install or remove My Bot 2.0."
}

if ([string]$env:MYBOT_RUN_POWERSHELL_INTEGRATION -ceq "1") {
    $env:MYBOT_RUN_PYTHON_INTEGRATION = "1"
}

$arguments = [System.Collections.Generic.List[string]]::new()
foreach ($item in $prefix) { $arguments.Add($item) }
$arguments.Add($pythonInstaller)
if (-not [string]::IsNullOrWhiteSpace($InstallDirectory)) {
    $arguments.Add("--install-directory")
    $arguments.Add($InstallDirectory)
}
if (-not [string]::IsNullOrWhiteSpace($ProfileSourceDirectory)) {
    $arguments.Add("--profile-source-directory")
    $arguments.Add($ProfileSourceDirectory)
}
if ($Uninstall) { $arguments.Add("--uninstall") }
if ($ValidateOnly) { $arguments.Add("--validate-only") }
if ($NoLaunch) { $arguments.Add("--no-launch") }

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "The Python LocalRuntime installer failed with exit code $LASTEXITCODE."
}
