# Windows home-PC deployment. Exit 2 means infrastructure ready, app code pending.
[CmdletBinding()]
param(
    [string]$SourceDir,
    [string]$RuntimeDir,
    [string]$ProjectName = 'tep_digitaltwin',
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
if (-not $SourceDir) { $SourceDir = Split-Path $PSScriptRoot -Parent }
if (-not $RuntimeDir) { $RuntimeDir = Split-Path $PSScriptRoot -Parent }
$lock = $null
$overrideFile = $null
$composeArgs = $null
$exitCode = 1
$revision = $null
$ready = @()
$pending = @()
$stage = 'preflight'
$reportFile = $null
$attemptTime = (Get-Date).ToString('o')

function Invoke-Docker {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE)." }
}

try {
    $SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path
    $RuntimeDir = (Resolve-Path -LiteralPath $RuntimeDir).Path
    $reportDir = Join-Path $SourceDir 'reports\deployment'
    $null = New-Item -ItemType Directory -Path $reportDir -Force
    $reportFile = Join-Path $reportDir 'last-attempt.json'
    $revision = (& git -C $SourceDir rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot determine source Git revision.' }
    $composeFile = Join-Path $SourceDir 'compose.yaml'
    $envFile = Join-Path $RuntimeDir '.env'
    foreach ($required in @($composeFile, $envFile, (Join-Path $RuntimeDir 'models'))) {
        if (-not (Test-Path -LiteralPath $required)) { throw "Required path missing: $required" }
    }
    $null = New-Item -ItemType Directory -Path (Join-Path $RuntimeDir 'logs') -Force
    $lock = [IO.File]::Open((Join-Path $RuntimeDir 'logs\deployment.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    if (-not $env:DOCKER_HOST) { $env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine' }
    Invoke-Docker -DockerArgs @('version', '--format', '{{.Server.Version}}')
    Invoke-Docker -DockerArgs @('compose', 'version')

    # Build the checkout but preserve host environment, models and logs.
    # Compose 2.24.4+ supports !override to replace the original env_file list.
    $overrideFile = Join-Path ([IO.Path]::GetTempPath()) ('tep-compose-' + [guid]::NewGuid().ToString('N') + '.yaml')
    $envYaml = ConvertTo-Json ($envFile.Replace('\', '/')) -Compress
    $modelsYaml = ConvertTo-Json ((Join-Path $RuntimeDir 'models').Replace('\', '/')) -Compress
    $logsYaml = ConvertTo-Json ((Join-Path $RuntimeDir 'logs').Replace('\', '/')) -Compress
    $rawYaml = ConvertTo-Json ((Join-Path $RuntimeDir 'data\raw\TEP').Replace('\', '/')) -Compress
    $yaml = "services:`n"
    foreach ($service in @('api', 'inference', 'monitor')) {
        $yaml += "  ${service}:`n    env_file: !override`n      - $envYaml`n    volumes:`n      - type: bind`n        source: $modelsYaml`n        target: /app/models`n        read_only: true`n      - type: bind`n        source: $logsYaml`n        target: /app/logs`n"
        if ($service -eq 'api') {
            $yaml += "      - type: bind`n        source: $rawYaml`n        target: /app/data/raw/TEP`n        read_only: true`n"
        }
    }
    [IO.File]::WriteAllText($overrideFile, $yaml, (New-Object Text.UTF8Encoding($false)))
    $composeArgs = @('compose', '--project-name', $ProjectName, '--project-directory', $SourceDir, '--env-file', $envFile, '-f', $composeFile, '-f', $overrideFile)
    Write-Host '[CHECK] Compose configuration (environment values are not printed)'
    Invoke-Docker -DockerArgs ($composeArgs + @('config', '--quiet'))

    $tests = @(Get-ChildItem (Join-Path $SourceDir 'tests') -Filter 'test_*.py' -Recurse -File -ErrorAction SilentlyContinue)
    $stage = 'python-validation'
    if ($tests.Count -gt 0) {
        $python = Join-Path $RuntimeDir '.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $python)) { throw 'Tests exist, but the host Python environment is missing.' }
        Push-Location $SourceDir
        try {
            & $python -m pip install -r (Join-Path $SourceDir 'requirements.txt')
            if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
            & $python -m compileall -q src kafka tests deploy
            if ($LASTEXITCODE -ne 0) { throw 'Python source compilation failed.' }
            & $python -m pip check
            if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed.' }
            & $python -m pytest tests
            if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit $LASTEXITCODE)." }
        } finally { Pop-Location }
    } else { Write-Host '[TEST] No pytest test files yet; no tests were run.' }

    $stage = 'web-validation'
    $webDir = Join-Path $SourceDir 'web'
    if (Test-Path -LiteralPath (Join-Path $webDir 'package.json')) {
        $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
        $previousWebSource = $env:VITE_PREDICTION_SOURCE
        $previousWebUrl = $env:VITE_PREDICTION_API_URL
        $env:VITE_PREDICTION_SOURCE = 'api'
        $env:VITE_PREDICTION_API_URL = '/api/predictions/latest'
        Push-Location $webDir
        try {
            & $npm ci --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw 'Web dependency installation failed.' }
            & $npm run lint
            if ($LASTEXITCODE -ne 0) { throw 'Web lint failed.' }
            & $npm test
            if ($LASTEXITCODE -ne 0) { throw 'Web tests failed.' }
            & $npm run build
            if ($LASTEXITCODE -ne 0) { throw 'Web build failed.' }
        } finally {
            $env:VITE_PREDICTION_SOURCE = $previousWebSource
            $env:VITE_PREDICTION_API_URL = $previousWebUrl
            Pop-Location
        }
    }

    if ($ValidateOnly) {
        [ordered]@{ time = $attemptTime; revision = $revision; validationOnly = $true; stage = 'validated'; exitCode = 0; fullDeployment = $false } |
            ConvertTo-Json | Set-Content -LiteralPath $reportFile -Encoding UTF8
        Write-Host '[VALIDATED] Tests and build checks passed. No containers were changed.'
        exit 0
    }

    $stage = 'image-build'
    Write-Host '[BUILD] Building all three application images'
    Invoke-Docker -DockerArgs ($composeArgs + @('build'))

    $entrypoints = [ordered]@{ api = 'src\api\main.py'; inference = 'src\inference\main.py'; monitor = 'src\monitoring\main.py' }
    $ready = @('kafka')
    $pending = @()
    foreach ($service in $entrypoints.Keys) {
        if (Test-Path -LiteralPath (Join-Path $SourceDir $entrypoints[$service])) { $ready += $service }
        else { $pending += $service }
    }
    if ($pending.Count -gt 0) {
        Write-Warning ('Not implemented yet; leaving these services stopped: ' + ($pending -join ', '))
        # Stop existing crash loops without deleting containers or volumes.
        Invoke-Docker -DockerArgs ($composeArgs + @('stop') + $pending)
    }
    Write-Host ('[DEPLOY] Starting implemented services: ' + ($ready -join ', '))
    $stage = 'service-start'
    Invoke-Docker -DockerArgs ($composeArgs + @('up', '--detach', '--wait', '--wait-timeout', '180') + $ready)
    $before = @{}
    foreach ($service in $ready) {
        $id = (& docker @composeArgs ps --quiet $service | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $id) { throw "No container for $service" }
        $state = (& docker inspect $id | ConvertFrom-Json)[0]
        $before[$service] = @{ Id = $id; Restarts = $state.RestartCount }
    }
    Start-Sleep -Seconds 10
    foreach ($service in $ready) {
        $state = (& docker inspect $before[$service].Id | ConvertFrom-Json)[0]
        if ($LASTEXITCODE -ne 0 -or $state.State.Status -ne 'running' -or $state.RestartCount -ne $before[$service].Restarts) {
            throw "Service is not stable: $service"
        }
        if ($state.State.Health -and $state.State.Health.Status -ne 'healthy') { throw "Service is not healthy: $service" }
        Write-Host "[VERIFIED] $service is running with no new restarts."
    }
    Invoke-Docker -DockerArgs ($composeArgs + @('ps', '--all'))
    $report = [ordered]@{ time = (Get-Date).ToString('o'); revision = $revision; source = $SourceDir; runtime = $RuntimeDir; running = $ready; pending = $pending; fullDeployment = ($pending.Count -eq 0) }
    $report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RuntimeDir 'logs\last-deployment.json') -Encoding UTF8
    $exitCode = if ($pending.Count -gt 0) { 2 } else { 0 }
    $report['validationOnly'] = $false
    $report['exitCode'] = $exitCode
    $report['stage'] = 'service-verified'
    $report | ConvertTo-Json | Set-Content -LiteralPath $reportFile -Encoding UTF8
} catch {
    Write-Host ('[ERROR] ' + $_.Exception.Message)
    if ($reportFile) {
        # 경로·단계·commit만 기록한다. 환경값/secret/원문 예외는 보고서에 넣지 않는다.
        [ordered]@{ time = $attemptTime; revision = $revision; validationOnly = [bool]$ValidateOnly; stage = $stage; exitCode = 1; fullDeployment = $false } |
            ConvertTo-Json | Set-Content -LiteralPath $reportFile -Encoding UTF8
    }
    if ($composeArgs) {
        & docker @composeArgs ps --all
        if (-not $ValidateOnly) { & docker @composeArgs logs --tail 50 kafka inference monitor api }
    }
} finally {
    if ($overrideFile -and (Test-Path -LiteralPath $overrideFile)) { Remove-Item -LiteralPath $overrideFile }
    if ($lock) { $lock.Dispose() }
}
exit $exitCode
