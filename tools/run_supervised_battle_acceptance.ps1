param(
    [switch]$AuthorizeOneBattle
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$planPath = Join-Path $root "config\run-plan.local.json"
$eventPath = Join-Path $root "logs\run-events.jsonl"
$binaryPath = Join-Path $root "MyBot.run.exe"
$provenancePath = Join-Path $root "config\binary-provenance.json"

function Get-ControlStatus {
    Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/control/status" -TimeoutSec 5
}

function Send-ControlCommand([string]$Action) {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8765/api/control/command" `
        -Method Post -ContentType "application/json" -Body (@{action=$Action} | ConvertTo-Json -Compress) -TimeoutSec 10
    [pscustomobject]@{http=[int]$response.StatusCode; body=$response.Content | ConvertFrom-Json}
}

function Get-LatestNativeLog([string]$Profile) {
    if ($Profile -notmatch '^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$' -or $Profile -in @('.', '..')) {
        throw "The active profile name is not path-safe"
    }
    $logDir = Join-Path $root ("Profiles\{0}\Logs" -f $Profile)
    $candidate = Get-ChildItem -LiteralPath $logDir -File -ErrorAction Stop |
        Where-Object {$_.Name -match '^\d{4}-\d{2}-\d{2}_\d{2}\.\d{2}\.\d{2}\.log$'} |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
    if (-not $candidate) { throw "No native log exists for the active profile" }
    $candidate
}

function Read-FileDelta([string]$Path, [long]$Offset) {
    $stream = [System.IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite')
    try {
        [void]$stream.Seek($Offset, 'Begin')
        $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::UTF8, $true, 4096, $true)
        try { $reader.ReadToEnd() } finally { $reader.Dispose() }
    } finally { $stream.Dispose() }
}

function Require-ExactlyOne([string]$Text, [string]$Pattern, [string]$Description) {
    $matches = [regex]::Matches($Text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if ($matches.Count -ne 1) { throw "$Description count was $($matches.Count), expected exactly one" }
}

function Require-ExactlyOneEvent([object[]]$Events, [string]$Type, [string]$Pattern, [string]$Description) {
    $matches = @($Events | Where-Object {
        $_.type -eq $Type -and [string]$_.message -match $Pattern
    })
    if ($matches.Count -ne 1) { throw "$Description count was $($matches.Count), expected exactly one" }
}

function Require-ProvenSpellCast([object[]]$Events, [string]$SpellName) {
    $valid = 0
    foreach ($event in @($Events | Where-Object {$_.type -eq 'combat.spell-cast'})) {
        $match = [regex]::Match([string]$event.message,
            ('^{0} cast at .+quantity ([0-9]+)->([0-9]+)' -f [regex]::Escape($SpellName)),
            [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if ($match.Success -and [int]$match.Groups[1].Value -gt [int]$match.Groups[2].Value) { $valid++ }
    }
    if ($valid -lt 1) { throw "$SpellName did not have a proven quantity-decreasing cast" }
}

if (-not $AuthorizeOneBattle) {
    throw "This tool performs one live account-affecting battle. Re-run only with explicit current authorization: -AuthorizeOneBattle"
}

$planHashBefore = (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash
$plan = Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
if ($plan.'run.surface' -ne 'regular' -or $plan.'run.strategy' -ne 'smart.local' -or
    $plan.'run.max_battles' -ne 1 -or $plan.'army.manage_training' -ne $false -or
    $plan.'army.wait_for_full' -ne $true -or $plan.'donate.mode' -ne 'off' -or
    $plan.'events.collect_resources' -ne $false -or $plan.'events.clan_games' -ne $false -or
    $plan.'events.laboratory' -ne 'off' -or $plan.'upgrade.policy' -ne 'disabled') {
    throw "Saved plan is not the bounded current-army one-battle plan"
}
if (@($plan.'run.heroes').Count -lt 1) {
    throw "Smart supervised acceptance requires at least one explicitly selected Hero"
}

$provenance = Get-Content -LiteralPath $provenancePath -Raw | ConvertFrom-Json
$binaryRecord = @($provenance.artifacts | Where-Object {$_.path -eq 'MyBot.run.exe'})
if ($binaryRecord.Count -ne 1) { throw "MyBot.run.exe does not have exactly one provenance record" }
$binaryHash = (Get-FileHash -LiteralPath $binaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
$binarySize = (Get-Item -LiteralPath $binaryPath).Length
if ($binaryHash -ne [string]$binaryRecord[0].sha256 -or $binarySize -ne [long]$binaryRecord[0].bytes) {
    throw "MyBot.run.exe does not match binary provenance"
}

$pre = Get-ControlStatus
if (-not $pre.connected -or $pre.state -ne 'idle' -or -not $pre.engine_available) {
    throw "Native preflight is not connected, idle, and engine-ready"
}
if ($pre.emulator -ne 'BlueStacks5' -or $pre.instance -ne 'Pie64') {
    throw "The attached emulator is not the exact BlueStacks5/Pie64 target"
}
$preflightDeferredAttachment = -not ($pre.emulator_attached -and $pre.window_attached -and $pre.adb_ready)

$blueStacks = @(Get-Process HD-Player -ErrorAction Stop | Where-Object {$_.MainWindowTitle -eq 'BlueStacks5-Pie64'})
if ($blueStacks.Count -ne 1) { throw "Expected exactly one BlueStacks5-Pie64 process" }
$blueStacksPid = $blueStacks[0].Id
$nativeLog = Get-LatestNativeLog $pre.profile
$logOffset = $nativeLog.Length
$eventOffset = if (Test-Path -LiteralPath $eventPath) {(Get-Item -LiteralPath $eventPath).Length} else {0}
$startedAt = Get-Date
$result = [ordered]@{
    pass=$false; automated_proof=$false; visual_review=$false; phase='preflight'; session_id=''
    binary_sha256=$binaryHash; deferred_attachment=$preflightDeferredAttachment; start=$null; final=$null; events=@(); errors=@()
}

try {
    Write-Host "WATCH BLUESTACKS NOW. The proof is invalid unless you visibly see the enemy view zoom out and troops leave the bar and appear on the battlefield." -ForegroundColor Yellow
    $start = Send-ControlCommand 'start'
    $result.start = $start
    if ($start.http -ne 202 -or -not $start.body.ok) { throw "Start request was refused" }
    Write-Output "START_ACCEPTED $($start.body.request_id)"

    $deadline = (Get-Date).AddMinutes(12)
    $lastPhase = ''
    while ((Get-Date) -lt $deadline) {
        $status = Get-ControlStatus
        if (-not $status.connected) { throw "Native heartbeat went offline" }
        if ($status.session_id) { $result.session_id = $status.session_id }
        $phase = "$($status.state)|$($status.last_outcome)|$($status.plan_message)"
        if ($phase -ne $lastPhase) { Write-Output "STATE $phase"; $lastPhase = $phase }
        if ($status.last_command_id -eq $start.body.request_id -and $status.last_outcome -in @('rejected','failed')) {
            throw "Start failed: $($status.last_command_message)"
        }
        if ($status.state -eq 'idle' -and $result.session_id) {
            $result.final = $status
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $result.final) { throw "One-battle run exceeded the twelve-minute watchdog" }

    if (Test-Path -LiteralPath $eventPath) {
        $eventDelta = Read-FileDelta $eventPath $eventOffset
        $result.events = @($eventDelta -split "`r?`n" | Where-Object {$_} | ForEach-Object {$_ | ConvertFrom-Json} |
            Where-Object {$_.session_id -eq $result.session_id})
    }
    $nativeDelta = Read-FileDelta $nativeLog.FullName $logOffset
    $types = @($result.events | ForEach-Object {$_.type})
    if (@($result.events | Where-Object {$_.type -eq 'battle.completed'}).Count -ne 1) { throw "Exactly one battle.completed event was not recorded" }
    if (@($result.events | Where-Object {$_.type -eq 'session.completed'}).Count -ne 1) { throw "Exactly one session.completed event was not recorded" }
    if (@($result.events | Where-Object {$_.type -eq 'session.stopping' -and $_.message -match 'battle-limit'}).Count -ne 1) {
        throw "The run did not stop internally on battle-limit"
    }

    Require-ExactlyOneEvent $result.events 'combat.decision' '^Smart side .+ selected:' 'Smart side selection'
    Require-ExactlyOneEvent $result.events 'combat.decision' '^Smart combat started from ' 'Smart combat start'
    $heroNames = @{
        'barbarian-king' = 'Barbarian King'
        'archer-queen' = 'Archer Queen'
        'minion-prince' = 'Minion Prince'
        'grand-warden' = 'Grand Warden'
        'royal-champion' = 'Royal Champion'
    }
    foreach ($heroId in @($plan.'run.heroes')) {
        if (-not $heroNames.ContainsKey([string]$heroId)) { throw "Unknown selected hero in saved plan: $heroId" }
        $heroName = $heroNames[[string]$heroId]
        Require-ExactlyOneEvent $result.events 'combat.hero-ability' `
            ('^{0} ability command issued:' -f [regex]::Escape($heroName)) `
            "$heroName Smart ability command"
    }
    if (@($result.events | Where-Object {$_.type -eq 'combat.hero-ability' -and $_.message -match ' ability not issued:'}).Count) {
        throw "At least one selected hero ability was not issued"
    }
    Require-ProvenSpellCast $result.events 'Rage'
    Require-ProvenSpellCast $result.events 'Freeze'
    if (@($result.events | Where-Object {$_.type -eq 'combat.spell-retained'}).Count) {
        throw "Smart retained a spell instead of proving the requested spell use"
    }

    Require-ExactlyOne $nativeDelta 'Run Planner: enemy zoom-out and [5-9][0-9]+ deployable red-line points verified' 'enemy zoom and red-line proof'
    Require-ExactlyOne $nativeDelta 'Run Planner deployment proof: live attack bar read 1/2 contains zero deployable troops' 'first empty troop-bar proof'
    Require-ExactlyOne $nativeDelta 'Run Planner deployment proof: live attack bar read 2/2 contains zero deployable troops' 'second empty troop-bar proof'
    Require-ExactlyOne $nativeDelta 'Run Planner deployment verified: [1-9][0-9]* deployable troops reduced to zero' 'positive troop depletion proof'
    Require-ExactlyOne $nativeDelta 'Run Planner: stop condition reached - battle-limit' 'internal battle-limit stop'
    Require-ExactlyOne $nativeDelta '=+ Start Attack =+' 'attack start'
    if ($nativeDelta -match '(?i)deployment verification failed|deployment was not proven|could not send enemy zoom-out gesture|lost the attack page after zoom-out|could not prove deployable red-line geometry after zoom-out|Smart side selection failed|Smart Attack could not establish|Smart Attack retained|cast was not proven|no blind portrait click was sent') {
        throw "Native log contains a zoom, deployment, Smart targeting, hero, or spell failure"
    }

    if ((Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash -ne $planHashBefore) { throw "Saved plan changed during the run" }
    if (-not (Get-Process -Id $blueStacksPid -ErrorAction SilentlyContinue)) { throw "BlueStacks process changed or exited" }
    if ($result.final.state -ne 'idle' -or $result.final.run_state -or $result.final.plan_active -or $result.final.session_id) {
        throw "The final native lifecycle is not clean idle with an empty session"
    }
    $crashes = @(Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=$startedAt} -ErrorAction SilentlyContinue |
        Where-Object {$_.Id -eq 1000 -and $_.Message -match 'HD-Player|MyBot\.run'})
    if ($crashes.Count) { throw "A new MyBot/BlueStacks application crash was recorded" }

    $result.automated_proof = $true
    $review = Read-Host "Type exactly SMART DEPLOYMENT ABILITIES AND SPELLS CONFIRMED only if you personally watched all four happen"
    if ($review -cne 'SMART DEPLOYMENT ABILITIES AND SPELLS CONFIRMED') {
        throw "Player-eye Smart deployment, ability, and spell confirmation was not supplied"
    }
    $result.visual_review = $true
    $result.pass = $true
    $result.phase = 'complete'
}
catch {
    $result.errors += $_.Exception.Message
    $result.phase = 'failed'
    try {
        $status = Get-ControlStatus
        if ($status.state -ne 'idle') {
            [void](Send-ControlCommand 'stop')
            $stopDeadline = (Get-Date).AddSeconds(45)
            do { Start-Sleep -Milliseconds 250; $status = Get-ControlStatus } while ($status.state -ne 'idle' -and (Get-Date) -lt $stopDeadline)
        }
        $result.final = $status
    } catch { $result.errors += "Emergency Stop failed: $($_.Exception.Message)" }
}

$result | ConvertTo-Json -Depth 10
if (-not $result.pass) { exit 9 }
