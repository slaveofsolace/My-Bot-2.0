[CmdletBinding()]
param(
    [ValidateSet("BuildAndPackage", "CompileForReview", "PackageReviewed")]
    [string]$Action = "BuildAndPackage",

    [string]$AutoItRoot,

    [string]$ReviewedBinaryDirectory,

    [ValidateSet("LocalRuntime", "PublicDistribution")]
    [string]$Mode = "LocalRuntime",

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$')]
    [string]$Version,

    [string]$OutputDirectory,

    [string]$ExpectedAutoItVersion = "3.3.16.1",

    [string]$ImgLocRedistributionAcknowledgement,

    [switch]$AllowDirtySource,

    [switch]$KeepWorkDirectory
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $repositoryRoot "artifacts\release"
}
$outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory).TrimEnd('\')
$repositoryRootWithSeparator = $repositoryRoot.TrimEnd('\') + '\'
if ($outputRoot -eq $repositoryRoot -or $repositoryRoot.StartsWith($outputRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDirectory must not be the repository root or one of its parents."
}

$publicAcknowledgement = "WRITTEN_PERMISSION_CONFIRMED_OR_LICENSED_REPLACEMENT_VALIDATED"
$pinnedMiniPath = "MyBot.run.MiniGui.exe"
$pinnedMiniSha256 = "ae26c098ceb3c74e3d7f567834d9135257e094172e32140f4a5b615eaf90ceda"
$pinnedMiniBytes = 1634304
$expectedCompilerSha256 = "921e51d0d9f94c05c5ed10d2d2a80620c8ed930cc48d71e2ce0a5bab4a4f8158"
$expectedCompilerSigner = "CN=AutoIt Consulting Ltd, O=AutoIt Consulting Ltd, L=Birmingham, C=GB"
$expectedCompilerThumbprint = "B64DDF46C16DEECAA165BB0EC1D640F51588CBEF"
$deterministicZipTimestamp = [System.DateTimeOffset]::new(1980, 1, 1, 0, 0, 0, [System.TimeSpan]::Zero)

# Every locally built executable is x86, un-packed, and compiled at level 2. The GUI/CUI choice is
# explicit rather than inherited from a developer workstation or wrapper default.
$compileTargets = @(
    [ordered]@{ Source = "My Bot 2.0.au3"; Output = "My Bot 2.0.exe"; Subsystem = "/gui" },
    [ordered]@{ Source = "MyBot.run.EngineProbe.au3"; Output = "MyBot.run.EngineProbe.exe"; Subsystem = "/gui" },
    [ordered]@{ Source = "MyBot.run.au3"; Output = "MyBot.run.exe"; Subsystem = "/gui" },
    [ordered]@{ Source = "MyBot.run.Watchdog.au3"; Output = "MyBot.run.Watchdog.exe"; Subsystem = "/gui" },
    [ordered]@{ Source = "MyBot.run.Wmi.au3"; Output = "MyBot.run.Wmi.exe"; Subsystem = "/console" }
)

$runtimeDirectories = @(
    "COCBot",
    "CSV",
    "Help",
    "images",
    "imgxml",
    "Languages",
    "lib",
    "Strategies",
    "ui"
)

$runtimeFiles = @(
    "Install My Bot 2.0.cmd",
    "Uninstall My Bot 2.0.cmd",
    "My Bot 2.0.au3",
    "MyBot.run.au3",
    "MyBot.run.EngineProbe.au3",
    "MyBot.run.EngineProbe.exe.config",
    "MyBot.run.MiniGui.au3",
    "MyBot.run.Watchdog.au3",
    "MyBot.run.Wmi.au3",
    "MyBot.run.version.au3",
    "MyBot.run.exe.config",
    "MyBot.run Community Support Key.asc",
    "README.md",
    "SECURITY.md",
    "License.txt",
    "upstreams.lock.json",
    "docs\INSTALL.md",
    "packaging\README.md",
    "tools\planner_ui.py",
    "tools\Install-LocalRuntime.ps1",
    "tools\install_local_runtime.py",
    "config\account-queue.schema.json",
    "config\battle-route.schema.json",
    "config\binary-provenance.json",
    "config\current-client-capabilities.json",
    "config\run-event.schema.json",
    "config\run-plan.schema.json",
    "config\run-session.schema.json",
    "config\runtime-evidence.schema.json"
)

$runtimeConfigDirectories = @("config\game", "config\ui")
$publicSourceDirectories = @("docs", "tests", "tools", "packaging")
$publicSourceFiles = @(".gitattributes", ".gitignore", "CONTRIBUTING.md")
$trackedReleaseFiles = @{}
foreach ($trackedPath in @(& git -C $repositoryRoot ls-files 2>&1)) {
    if ($LASTEXITCODE -ne 0) { throw "Tracked release inputs could not be enumerated." }
    $trackedReleaseFiles[$trackedPath.Replace('\', '/').ToLowerInvariant()] = $true
}

function Get-NormalizedRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if (-not $pathFull.StartsWith($rootFull + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside its expected root: $pathFull"
    }
    return $pathFull.Substring($rootFull.Length + 1).Replace('\', '/')
}

function Test-IsExcludedReleasePath {
    param([Parameter(Mandatory = $true)][string]$RelativePath)

    $normalized = $RelativePath.Replace('\', '/')
    if ($normalized -ieq "Languages/English.ini") { return $true }
    if ($normalized -ieq "CLAUDE_HANDOFF_PROMPT.md") { return $true }
    if ($normalized -match '(?i)^lib/[^/]+\.html$') { return $true }
    if ($normalized -match '(?i)^tools/_[^/]*\.exe$') { return $true }
    if ($normalized -match '(^|/)(Profiles|logs|artifacts|__pycache__|\.pytest_cache|node_modules|temp|tmp|cache)(/|$)') { return $true }
    if ($normalized -match '(?i)(^|/)[^/]+\.local\.json$') { return $true }
    if ($normalized -match '(^|/)(control-command|control-status|run-plan)(?:\.[^/]*)?\.local\.json$') { return $true }
    if ($normalized -match '(^|/)(control-command|control-status|run-plan)\.local\.json$') { return $true }
    if ($normalized -match '(^|/)run-events(?:\.[^/]*)?\.jsonl$') { return $true }
    if ($normalized -match '\.(log|tmp|bak|cache|pyc|pyo)$') { return $true }
    return $false
}

function Test-IsForbiddenPayloadPath {
    param([Parameter(Mandatory = $true)][string]$RelativePath)

    $normalized = $RelativePath.Replace('\', '/')
    if ($normalized -ieq "Languages/English.ini") { return $false }
    return Test-IsExcludedReleasePath -RelativePath $normalized
}

function Copy-ReleaseFile {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$DestinationRoot
    )

	$normalized = $RelativePath.Replace('\', '/')
	if (Test-IsExcludedReleasePath -RelativePath $normalized) { return }
	if (-not $trackedReleaseFiles.ContainsKey($normalized.ToLowerInvariant())) {
		throw "Release input is not tracked by Git: $RelativePath"
	}
    $source = Join-Path $repositoryRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Allowlisted release file is missing: $RelativePath"
    }
    $destination = Join-Path $DestinationRoot $RelativePath
    $destinationParent = Split-Path -Parent $destination
    [System.IO.Directory]::CreateDirectory($destinationParent) | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination
}

function Copy-ReleaseDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$RelativeDirectory,
        [Parameter(Mandatory = $true)][string]$DestinationRoot
    )

    $sourceDirectory = Join-Path $repositoryRoot $RelativeDirectory
    if (-not (Test-Path -LiteralPath $sourceDirectory -PathType Container)) {
        throw "Allowlisted release directory is missing: $RelativeDirectory"
    }
    $files = Get-ChildItem -LiteralPath $sourceDirectory -Recurse -File | Sort-Object FullName
    foreach ($file in $files) {
        $relative = Get-NormalizedRelativePath -Root $repositoryRoot -Path $file.FullName
        if (-not (Test-IsExcludedReleasePath -RelativePath $relative)) {
            Copy-ReleaseFile -RelativePath $relative -DestinationRoot $DestinationRoot
        }
    }
}

function Export-TrackedFileAtCommit {
    param(
        [Parameter(Mandatory = $true)][string]$Commit,
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$DestinationRoot
    )

    $normalized = $RelativePath.Replace('\', '/')
    if ([System.IO.Path]::IsPathRooted($RelativePath) -or $normalized -match '(^|/)\.\.(/|$)') {
        throw "Tracked release file has an unsafe path: $RelativePath"
    }
    if ($Commit -notmatch '^[0-9a-fA-F]{40}$') {
        throw "Tracked release file requires a full source commit SHA."
    }

    $destination = Join-Path $DestinationRoot $RelativePath
    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $destination)) | Out-Null
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "git.exe"
    $startInfo.Arguments = '-C "' + $repositoryRoot.Replace('"', '\\"') + '" cat-file blob "' + $Commit + ':' + $normalized.Replace('"', '\\"') + '"'
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) { throw "Could not start git to export $RelativePath." }
    try {
        $output = [System.IO.File]::Open($destination, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        try { $process.StandardOutput.BaseStream.CopyTo($output) }
        finally { $output.Dispose() }
        $standardError = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) {
            Remove-Item -LiteralPath $destination -Force -ErrorAction SilentlyContinue
            throw "Could not export tracked $RelativePath at $Commit`: $standardError"
        }
    }
    finally { $process.Dispose() }
}

function Get-Sha256Lower {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Write-DeterministicJson {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $json = ($Value | ConvertTo-Json -Depth 10).Replace("`r`n", "`n") + "`n"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $json, $utf8NoBom)
}

function Get-Aut2Exe {
    if ([string]::IsNullOrWhiteSpace($AutoItRoot)) {
        throw "AutoItRoot is required for $Action."
    }
    $resolvedRoot = (Resolve-Path $AutoItRoot).Path
    $candidate = Get-ChildItem -LiteralPath $resolvedRoot -Recurse -File -Filter "Aut2Exe.exe" |
        Sort-Object @{ Expression = { $_.FullName -match '\\x64\\' } }, FullName |
        Select-Object -First 1
    if (-not $candidate) { throw "Aut2Exe.exe was not found under $resolvedRoot" }
	if ($candidate.FullName -match '\\x64\\') {
		throw "Only an x64 Aut2Exe executable was found. Supply the AutoIt root containing the x86 compiler."
	}
	$signature = Get-AuthenticodeSignature -LiteralPath $candidate.FullName
	$signatureValid = $signature.Status -eq [System.Management.Automation.SignatureStatus]::Valid
	$signerValid = $signature.SignerCertificate.Subject -ceq $expectedCompilerSigner
	$thumbprintValid = $signature.SignerCertificate.Thumbprint -ceq $expectedCompilerThumbprint
	$compilerHashValid = (Get-Sha256Lower -Path $candidate.FullName) -ceq $expectedCompilerSha256
	if (-not $signatureValid -or -not $signerValid -or -not $thumbprintValid -or -not $compilerHashValid) {
		throw "Aut2Exe does not match the pinned signed compiler identity."
	}
    $compilerVersion = $candidate.VersionInfo.FileVersionRaw.ToString()
    if ($compilerVersion -ne $ExpectedAutoItVersion) {
        throw "Aut2Exe version $compilerVersion does not match required version $ExpectedAutoItVersion."
    }
    return $candidate
}

function Invoke-ReleaseCompile {
    param(
        [Parameter(Mandatory = $true)][System.IO.FileInfo]$Compiler,
        [Parameter(Mandatory = $true)][string]$CompiledDirectory
    )

    [System.IO.Directory]::CreateDirectory($CompiledDirectory) | Out-Null
    Push-Location $repositoryRoot
    try {
        foreach ($target in $compileTargets) {
            $source = Join-Path $repositoryRoot $target.Source
            $output = Join-Path $CompiledDirectory $target.Output
			$pragmaOutput = Join-Path $repositoryRoot $target.Output
			$originalOutput = Join-Path $CompiledDirectory (".original-" + [System.Guid]::NewGuid().ToString("N") + ".exe")
			$hadOriginalOutput = Test-Path -LiteralPath $pragmaOutput -PathType Leaf
            if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
                throw "Compile source is missing: $($target.Source)"
            }
            $arguments = @(
                "/in", $source,
                "/out", $output,
                "/x86",
                $target.Subsystem,
                "/nopack",
                "/comp", "2"
            )
			if ($hadOriginalOutput) { Move-Item -LiteralPath $pragmaOutput -Destination $originalOutput }
			try {
				$compilerOutput = & $Compiler.FullName @arguments 2>&1
				$exitCode = $LASTEXITCODE
				if ($exitCode -ne 0) {
					if ($compilerOutput) { Write-Host ($compilerOutput -join [Environment]::NewLine) }
					throw "Aut2Exe failed for $($target.Source) with exit code $exitCode."
				}
				# Aut2Exe 3.3.16.1 returns before its worker finishes writing the pragma output. Wait for
				# exactly one bounded completion window, then require a non-zero stable file before promotion.
				$outputDeadline = [datetime]::UtcNow.AddSeconds(30)
				do {
					$outputExists = Test-Path -LiteralPath $output -PathType Leaf
					$pragmaExists = Test-Path -LiteralPath $pragmaOutput -PathType Leaf
					if ($outputExists -or $pragmaExists) { break }
					Start-Sleep -Milliseconds 100
				} while ([datetime]::UtcNow -lt $outputDeadline)
				# #pragma compile(Out, ...) takes precedence over /out in AutoIt 3.3.16.1. Accept the
				# requested isolated path when supported, otherwise promote the newly created pragma output.
				$producedPath = $output
				if (-not (Test-Path -LiteralPath $producedPath -PathType Leaf)) {
					$producedPath = $pragmaOutput
					if (-not (Test-Path -LiteralPath $producedPath -PathType Leaf)) {
						throw "Aut2Exe returned success but produced no output for $($target.Source)."
					}
				}
				$lastLength = -1L
				$stableSamples = 0
				do {
					$currentLength = (Get-Item -LiteralPath $producedPath).Length
					if ($currentLength -gt 0 -and $currentLength -eq $lastLength) { $stableSamples++ }
					else { $stableSamples = 0 }
					$lastLength = $currentLength
					if ($stableSamples -ge 2) { break }
					Start-Sleep -Milliseconds 100
				} while ([datetime]::UtcNow -lt $outputDeadline)
				if ($stableSamples -lt 2) {
					throw "Aut2Exe output did not become stable for $($target.Source)."
				}
				if ($producedPath -ieq $pragmaOutput) {
					Move-Item -LiteralPath $pragmaOutput -Destination $output
				}
			}
			finally {
				if (Test-Path -LiteralPath $pragmaOutput -PathType Leaf) {
					Remove-Item -LiteralPath $pragmaOutput -Force
				}
				if ($hadOriginalOutput -and (Test-Path -LiteralPath $originalOutput -PathType Leaf)) {
					Move-Item -LiteralPath $originalOutput -Destination $pragmaOutput
				}
			}
        }
    }
    finally { Pop-Location }
}

function Get-ProvenanceRecord {
    param(
        [Parameter(Mandatory = $true)]$Provenance,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )

    $normalized = $RelativePath.Replace('\', '/')
    return @($Provenance.artifacts | Where-Object { $_.path.Replace('\', '/') -ieq $normalized }) | Select-Object -First 1
}

function Assert-ProvenanceDocument {
    param([Parameter(Mandatory = $true)]$Provenance)

    if ([int]$Provenance.schema_version -ne 1) { throw "Unsupported binary provenance schema." }
    $reviewedAt = [datetime]::MinValue
    $reviewedAtValid = [datetime]::TryParseExact(
        [string]$Provenance.reviewed_at,
        "yyyy-MM-dd",
        [System.Globalization.CultureInfo]::InvariantCulture,
        [System.Globalization.DateTimeStyles]::None,
        [ref]$reviewedAt
    )
    if (-not $reviewedAtValid) {
        throw "Binary provenance reviewed_at must be an ISO calendar date."
    }
    $seen = @{}
    foreach ($record in @($Provenance.artifacts)) {
        $recordPath = [string]$record.path
        $normalized = $recordPath.Replace('\', '/')
        if ([string]::IsNullOrWhiteSpace($recordPath) -or [System.IO.Path]::IsPathRooted($recordPath) -or $normalized -match '(^|/)\.\.(/|$)') {
            throw "Binary provenance contains an unsafe path: $recordPath"
        }
        $key = $normalized.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { throw "Binary provenance contains a duplicate path: $recordPath" }
        $seen[$key] = $true
        if ([string]$record.sha256 -notmatch '^[0-9a-fA-F]{64}$') {
            throw "Binary provenance contains an invalid SHA-256 for $recordPath."
        }
        $parsedBytes = 0L
        if (-not [int64]::TryParse([string]$record.bytes, [ref]$parsedBytes) -or $parsedBytes -lt 0) {
            throw "Binary provenance contains an invalid byte count for $recordPath."
        }
    }
}

function Assert-BinaryMatchesProvenance {
    param(
        [Parameter(Mandatory = $true)]$Provenance,
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$ActualPath
    )

    $record = Get-ProvenanceRecord -Provenance $Provenance -RelativePath $RelativePath
    if (-not $record) { throw "Binary has no provenance record: $RelativePath" }
    $actualFile = Get-Item -LiteralPath $ActualPath
    $actualHash = Get-Sha256Lower -Path $ActualPath
    if ([int64]$record.bytes -ne $actualFile.Length) {
        throw "Provenance byte count does not match $RelativePath."
    }
    if ([string]$record.sha256 -ine $actualHash) {
        throw "Provenance SHA-256 does not match $RelativePath."
    }
}

function Assert-CompiledSourceIdentity {
    param([Parameter(Mandatory = $true)]$Provenance)

    foreach ($target in $compileTargets) {
        $record = Get-ProvenanceRecord -Provenance $Provenance -RelativePath $target.Output
        if (-not $record) { throw "Compiled target has no provenance record: $($target.Output)" }
        if ([string]$record.provenance.kind -ine "local-build") {
            throw "Compiled target is not recorded as a local build: $($target.Output)"
        }
        if ([string]$record.provenance.source -ine [string]$target.Source) {
            throw "Provenance source mismatch for $($target.Output)."
        }
        if ([string]$record.provenance.toolchain -ine "AutoIt Aut2Exe") {
            throw "Provenance toolchain mismatch for $($target.Output)."
        }
        if ([string]$record.provenance.tool_version -ine $ExpectedAutoItVersion) {
            throw "Provenance tool version mismatch for $($target.Output)."
        }
    }
}

function Read-ReviewedCandidateManifest {
	param(
		[Parameter(Mandatory = $true)][string]$CompiledDirectory,
		[Parameter(Mandatory = $true)][string]$CurrentSourceCommit
	)

	$manifestPath = Join-Path $CompiledDirectory "candidate-hashes.json"
	if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
		throw "ReviewedBinaryDirectory is missing candidate-hashes.json."
	}
	$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
	$sourceTreeClean = $manifest.source_tree_clean -is [bool] -and $manifest.source_tree_clean -eq $true
	$manifestMatches = [int]$manifest.schema_version -eq 1 -and [string]$manifest.version -ceq $Version -and
		[string]$manifest.architecture -ceq "x86" -and [string]$manifest.compiler_version -ceq $ExpectedAutoItVersion -and
		[string]$manifest.compiler_sha256 -ceq $expectedCompilerSha256 -and
		[string]$manifest.compiler_signer -ceq $expectedCompilerSigner -and
		[string]$manifest.signing_claim -ceq "none" -and $sourceTreeClean
	if (-not $manifestMatches) {
		throw "Reviewed candidate manifest does not match the requested product/compiler contract."
	}
	$candidateCommit = [string]$manifest.source_commit
	if ($candidateCommit -notmatch '^[0-9a-fA-F]{40}$') {
		throw "Reviewed candidate manifest has an invalid source commit."
	}
	& git -C $repositoryRoot merge-base --is-ancestor $candidateCommit $CurrentSourceCommit 2>$null
	if ($LASTEXITCODE -ne 0) {
		throw "Reviewed candidate source commit is not an ancestor of the package source commit."
	}
	if ($candidateCommit -cne $CurrentSourceCommit) {
		$allowedPostBuildChanges = @{ "config/binary-provenance.json" = $true }
		foreach ($target in $compileTargets) { $allowedPostBuildChanges[$target.Output.Replace('\', '/')] = $true }
		$changedPaths = @(& git -C $repositoryRoot diff --name-only "$candidateCommit..$CurrentSourceCommit" -- 2>&1)
		if ($LASTEXITCODE -ne 0) { throw "Candidate-to-package source changes could not be inspected." }
		foreach ($changedPath in $changedPaths) {
			$normalizedChanged = $changedPath.Replace('\', '/')
			if (-not $allowedPostBuildChanges.ContainsKey($normalizedChanged)) {
				throw "Package source changed after candidate compilation: $normalizedChanged"
			}
		}
	}

	$records = @($manifest.binaries)
	if ($records.Count -ne $compileTargets.Count) {
		throw "Reviewed candidate manifest does not contain the exact compile matrix."
	}
	foreach ($target in $compileTargets) {
		$record = @($records | Where-Object { [string]$_.path -ceq [string]$target.Output }) | Select-Object -First 1
		$recordMatches = $record -and [string]$record.source -ceq [string]$target.Source -and
			[string]$record.subsystem -ceq [string]$target.Subsystem
		if (-not $recordMatches) {
			throw "Reviewed candidate identity mismatch for $($target.Output)."
		}
		$expectedFlags = @("/x86", [string]$target.Subsystem, "/nopack", "/comp", "2")
		$actualFlags = @($record.flags | ForEach-Object { [string]$_ })
		if ($actualFlags.Count -ne $expectedFlags.Count) {
			throw "Reviewed candidate compile flags mismatch for $($target.Output)."
		}
		for ($iFlag = 0; $iFlag -lt $expectedFlags.Count; $iFlag++) {
			if ($actualFlags[$iFlag] -cne $expectedFlags[$iFlag]) {
				throw "Reviewed candidate compile flags mismatch for $($target.Output)."
			}
		}
		$candidatePath = Join-Path $CompiledDirectory $target.Output
		$candidateExists = Test-Path -LiteralPath $candidatePath -PathType Leaf
		$candidateMatches = $candidateExists -and [int64]$record.bytes -eq (Get-Item -LiteralPath $candidatePath).Length -and
			[string]$record.sha256 -ieq (Get-Sha256Lower -Path $candidatePath)
		if (-not $candidateMatches) {
			throw "Reviewed candidate bytes do not match candidate-hashes.json: $($target.Output)"
		}
	}
	return $manifest
}

function New-DeterministicZip {
    param(
        [Parameter(Mandatory = $true)][string]$PayloadRoot,
        [Parameter(Mandatory = $true)][string]$ZipPath,
        [Parameter(Mandatory = $true)][bool]$ProvenanceVerified
    )

    if (-not $ProvenanceVerified) { throw "Refusing to package binaries before provenance verification." }
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zipStream = [System.IO.File]::Open($ZipPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    try {
        $archive = New-Object System.IO.Compression.ZipArchive($zipStream, [System.IO.Compression.ZipArchiveMode]::Create, $false)
        try {
            $payloadParent = Split-Path -Parent $PayloadRoot
            $files = Get-ChildItem -LiteralPath $PayloadRoot -Recurse -File | Sort-Object FullName
            foreach ($file in $files) {
                $entryName = Get-NormalizedRelativePath -Root $payloadParent -Path $file.FullName
                $entry = $archive.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
                $entry.LastWriteTime = $deterministicZipTimestamp
                $input = [System.IO.File]::OpenRead($file.FullName)
                try {
                    $output = $entry.Open()
                    try { $input.CopyTo($output) }
                    finally { $output.Dispose() }
                }
                finally { $input.Dispose() }
            }
        }
        finally { $archive.Dispose() }
    }
    finally { $zipStream.Dispose() }
}

if ($Mode -eq "PublicDistribution" -and $ImgLocRedistributionAcknowledgement -cne $publicAcknowledgement) {
    throw "PublicDistribution is blocked until written ImgLoc permission is confirmed or a licensed replacement is validated. Pass the exact documented acknowledgement only after that evidence exists."
}

$gitStatus = @(& git -C $repositoryRoot status --porcelain=v1 --untracked-files=all 2>&1)
if ($LASTEXITCODE -ne 0) { throw "Git status could not be read for the release source tree." }
if ($gitStatus.Count -gt 0 -and -not $AllowDirtySource) {
    throw "The source tree is dirty. Commit reviewed release inputs, or use AllowDirtySource only for a local candidate build."
}
if ($AllowDirtySource -and $Action -ne "CompileForReview") {
	throw "AllowDirtySource is restricted to isolated CompileForReview candidates."
}
if ($Mode -eq "PublicDistribution" -and $gitStatus.Count -gt 0) {
    throw "PublicDistribution cannot be created from a dirty source tree."
}
$sourceCommit = (& git -C $repositoryRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($sourceCommit)) {
	throw "The source commit could not be resolved."
}
$versionSource = Get-Content -LiteralPath (Join-Path $repositoryRoot "MyBot.run.version.au3") -Raw
$versionMatch = [regex]::Match($versionSource, 'Global Const \$g_sProductVersion\s*=\s*"v([^"\r\n]+)"')
if (-not $versionMatch.Success -or $versionMatch.Groups[1].Value -cne $Version) {
	throw "Requested release version $Version does not match MyBot.run.version.au3."
}

[System.IO.Directory]::CreateDirectory($outputRoot) | Out-Null
$workDirectory = Join-Path $outputRoot (".release-work-" + [System.Guid]::NewGuid().ToString("N"))
[System.IO.Directory]::CreateDirectory($workDirectory) | Out-Null
$workDirectoryCreated = $true

try {
    $compiledDirectory = Join-Path $workDirectory "compiled"
    $compilerVersion = "reviewed-binaries"
	$compilerSha256 = ""
	$compilerSigner = ""
    if ($Action -ne "PackageReviewed") {
        $compiler = Get-Aut2Exe
        $compilerVersion = $compiler.VersionInfo.FileVersionRaw.ToString()
		$compilerSha256 = Get-Sha256Lower -Path $compiler.FullName
		$compilerSigner = (Get-AuthenticodeSignature -LiteralPath $compiler.FullName).SignerCertificate.Subject
        Invoke-ReleaseCompile -Compiler $compiler -CompiledDirectory $compiledDirectory
    }
	else {
        if ([string]::IsNullOrWhiteSpace($ReviewedBinaryDirectory)) {
            throw "ReviewedBinaryDirectory is required for PackageReviewed."
		}
		$compiledDirectory = (Resolve-Path $ReviewedBinaryDirectory).Path
		$candidateManifest = Read-ReviewedCandidateManifest -CompiledDirectory $compiledDirectory -CurrentSourceCommit $sourceCommit
		$compilerVersion = [string]$candidateManifest.compiler_version
		$compilerSha256 = [string]$candidateManifest.compiler_sha256
		$compilerSigner = [string]$candidateManifest.compiler_signer
	}

    if ($Action -eq "CompileForReview") {
        $candidateName = "MyBot-$Version-win-x86-candidate"
        $candidatePath = Join-Path $outputRoot $candidateName
        if (Test-Path -LiteralPath $candidatePath) { throw "Candidate output already exists: $candidatePath" }
        $candidateFiles = @()
        foreach ($target in $compileTargets) {
            $path = Join-Path $compiledDirectory $target.Output
            $candidateFiles += [ordered]@{
                path = $target.Output.Replace('\', '/')
                source = $target.Source.Replace('\', '/')
                subsystem = $target.Subsystem
                flags = @("/x86", $target.Subsystem, "/nopack", "/comp", "2")
                bytes = (Get-Item -LiteralPath $path).Length
                sha256 = Get-Sha256Lower -Path $path
            }
        }
		$candidateManifest = [ordered]@{
            schema_version = 1
            version = $Version
            architecture = "x86"
			compiler_version = $compilerVersion
			compiler_sha256 = $compilerSha256
			compiler_signer = $compilerSigner
            source_commit = $sourceCommit
			source_tree_clean = ($gitStatus.Count -eq 0)
            signing_claim = "none"
            binaries = $candidateFiles
        }
        Write-DeterministicJson -Value $candidateManifest -Path (Join-Path $compiledDirectory "candidate-hashes.json")
        Move-Item -LiteralPath $compiledDirectory -Destination $candidatePath
        Write-Host "Compiled review candidates: $candidatePath"
        return
    }

    $packageName = "MyBot-$Version-win-x86"
    $payloadRoot = Join-Path $workDirectory $packageName
    [System.IO.Directory]::CreateDirectory($payloadRoot) | Out-Null

    foreach ($directory in $runtimeDirectories + $runtimeConfigDirectories) {
        Copy-ReleaseDirectory -RelativeDirectory $directory -DestinationRoot $payloadRoot
    }
    foreach ($file in $runtimeFiles) {
        Copy-ReleaseFile -RelativePath $file -DestinationRoot $payloadRoot
    }
    # English.ini is runtime-generated in a live checkout. Package the exact reviewed Git blob
    # without reading or modifying the operator's working copy.
    Export-TrackedFileAtCommit -Commit $sourceCommit -RelativePath "Languages\English.ini" -DestinationRoot $payloadRoot
    if ($Mode -eq "PublicDistribution") {
        foreach ($directory in $publicSourceDirectories) {
            Copy-ReleaseDirectory -RelativeDirectory $directory -DestinationRoot $payloadRoot
        }
        foreach ($file in $publicSourceFiles) {
            Copy-ReleaseFile -RelativePath $file -DestinationRoot $payloadRoot
        }
    }

    foreach ($target in $compileTargets) {
        $builtPath = Join-Path $compiledDirectory $target.Output
        if (-not (Test-Path -LiteralPath $builtPath -PathType Leaf)) {
            throw "Reviewed build output is missing: $($target.Output)"
        }
        Copy-Item -LiteralPath $builtPath -Destination (Join-Path $payloadRoot $target.Output)
    }

    $sourceMini = Join-Path $repositoryRoot $pinnedMiniPath
    if ((Get-Item -LiteralPath $sourceMini).Length -ne $pinnedMiniBytes -or (Get-Sha256Lower -Path $sourceMini) -ne $pinnedMiniSha256) {
        throw "The pinned Mini GUI is not the exact reviewed upstream binary. It must never be rebuilt or rebranded."
    }
    Copy-Item -LiteralPath $sourceMini -Destination (Join-Path $payloadRoot $pinnedMiniPath)

    $sourceMarker = Join-Path $repositoryRoot "MyBot.run.txt"
    if (-not (Test-Path -LiteralPath $sourceMarker -PathType Leaf) -or (Get-Item -LiteralPath $sourceMarker).Length -ne 0) {
        throw "MyBot.run.txt must exist in the source root and be exactly zero bytes."
    }
    [System.IO.File]::WriteAllBytes((Join-Path $payloadRoot "MyBot.run.txt"), [byte[]]@())
    if ((Get-Item -LiteralPath (Join-Path $payloadRoot "MyBot.run.txt")).Length -ne 0) {
        throw "Packaged MyBot.run.txt is not zero bytes."
    }

    # Parse the copy that will actually ship so the verification and packaged record cannot drift.
    $provenancePath = Join-Path $payloadRoot "config\binary-provenance.json"
    $provenance = Get-Content -LiteralPath $provenancePath -Raw | ConvertFrom-Json
    Assert-ProvenanceDocument -Provenance $provenance
    Assert-CompiledSourceIdentity -Provenance $provenance
    $packagedBinaries = Get-ChildItem -LiteralPath $payloadRoot -Recurse -File |
        Where-Object { $_.Extension -in @(".exe", ".dll", ".sys") } |
        Sort-Object FullName
    foreach ($binary in $packagedBinaries) {
        $relative = Get-NormalizedRelativePath -Root $payloadRoot -Path $binary.FullName
        Assert-BinaryMatchesProvenance -Provenance $provenance -RelativePath $relative -ActualPath $binary.FullName
    }
    $provenanceVerified = $true

    $forbiddenFiles = Get-ChildItem -LiteralPath $payloadRoot -Recurse -File | Where-Object {
        Test-IsForbiddenPayloadPath -RelativePath (Get-NormalizedRelativePath -Root $payloadRoot -Path $_.FullName)
    }
    if ($forbiddenFiles) {
        throw "A forbidden runtime or local-state path entered the release payload: $($forbiddenFiles[0].FullName)"
    }

    $fileRecords = @()
    $payloadFiles = Get-ChildItem -LiteralPath $payloadRoot -Recurse -File | Sort-Object FullName
    foreach ($file in $payloadFiles) {
        $fileRecords += [ordered]@{
            path = Get-NormalizedRelativePath -Root $payloadRoot -Path $file.FullName
            bytes = $file.Length
            sha256 = Get-Sha256Lower -Path $file.FullName
        }
    }
    $releaseManifest = [ordered]@{
        schema_version = 1
        product = "My Bot 2.0"
        version = $Version
        mode = $Mode
        platform = "windows"
        architecture = "x86"
        compiler_version = $compilerVersion
		compiler_sha256 = $compilerSha256
		compiler_signer = $compilerSigner
        compile_flags = @("/x86", "/gui or /console", "/nopack", "/comp 2")
        source_commit = $sourceCommit
        source_tree_clean = ($gitStatus.Count -eq 0)
        binary_provenance_verified = $provenanceVerified
        pinned_mini_rebuilt = $false
        code_signing_performed = $false
        signing_claim = "none"
        imgloc_redistribution_permission_acknowledged = ($Mode -eq "PublicDistribution")
        files = $fileRecords
    }
    Write-DeterministicJson -Value $releaseManifest -Path (Join-Path $payloadRoot "release-manifest.json")

    $finalZip = Join-Path $outputRoot "$packageName.zip"
    if (Test-Path -LiteralPath $finalZip) { throw "Release ZIP already exists: $finalZip" }
    $temporaryZip = Join-Path $workDirectory "$packageName.zip"
    New-DeterministicZip -PayloadRoot $payloadRoot -ZipPath $temporaryZip -ProvenanceVerified $provenanceVerified
    Move-Item -LiteralPath $temporaryZip -Destination $finalZip
    Write-Host "Release package: $finalZip"
    Write-Host "SHA-256: $(Get-Sha256Lower -Path $finalZip)"
}
finally {
    if ($workDirectoryCreated -and -not $KeepWorkDirectory -and (Test-Path -LiteralPath $workDirectory)) {
        $resolvedWork = [System.IO.Path]::GetFullPath($workDirectory)
        if (-not $resolvedWork.StartsWith($outputRoot + '\.release-work-', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove an unexpected work directory: $resolvedWork"
        }
        Remove-Item -LiteralPath $resolvedWork -Recurse -Force
    }
}
