# Windows home-PC deployment. Exit 2 means infrastructure ready, app code pending.
[CmdletBinding()]
param(
    [string]$SourceDir,
    [string]$RuntimeDir,
    [string]$ProjectName = 'tep_digitaltwin'
)
$ErrorActionPreference = 'Stop'
if (-not $SourceDir) { $SourceDir = Split-Path $PSScriptRoot -Parent }
if (-not $RuntimeDir) { $RuntimeDir = Split-Path $PSScriptRoot -Parent }
$lock = $null
$overrideFile = $null
$composeArgs = $null
$exitCode = 1

function Invoke-Docker {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE)." }
}

try {
    $SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path
    $RuntimeDir = (Resolve-Path -LiteralPath $RuntimeDir).Path
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
    $yaml = "services:`n"
    foreach ($service in @('api', 'inference', 'monitor')) {
        $yaml += "  ${service}:`n    env_file: !override`n      - $envYaml`n    volumes:`n      - type: bind`n        source: $modelsYaml`n        target: /app/models`n        read_only: true`n      - type: bind`n        source: $logsYaml`n        target: /app/logs`n"
    }
    [IO.File]::WriteAllText($overrideFile, $yaml, (New-Object Text.UTF8Encoding($false)))
    $composeArgs = @('compose', '--project-name', $ProjectName, '--project-directory', $SourceDir, '--env-file', $envFile, '-f', $composeFile, '-f', $overrideFile)
    Write-Host '[CHECK] Compose configuration (environment values are not printed)'
    Invoke-Docker -DockerArgs ($composeArgs + @('config', '--quiet'))

    $tests = @(Get-ChildItem (Join-Path $SourceDir 'tests') -Filter 'test_*.py' -Recurse -File -ErrorAction SilentlyContinue)
    if ($tests.Count -gt 0) {
        $python = Join-Path $RuntimeDir '.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $python)) { throw 'Tests exist, but the host Python environment is missing.' }
        Push-Location $SourceDir
        try {
            & $python -m pytest tests
            if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit $LASTEXITCODE)." }
        } finally { Pop-Location }
    } else { Write-Host '[TEST] No pytest test files yet; no tests were run.' }

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
    $revision = (& git -C $SourceDir rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot determine deployed Git revision.' }
    $report = [ordered]@{ time = (Get-Date).ToString('o'); revision = $revision; source = $SourceDir; runtime = $RuntimeDir; running = $ready; pending = $pending; fullDeployment = ($pending.Count -eq 0) }
    $report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RuntimeDir 'logs\last-deployment.json') -Encoding UTF8
    $exitCode = if ($pending.Count -gt 0) { 2 } else { 0 }
} catch {
    Write-Host ('[ERROR] ' + $_.Exception.Message)
    if ($composeArgs) { & docker @composeArgs ps --all }
} finally {
    if ($overrideFile -and (Test-Path -LiteralPath $overrideFile)) { Remove-Item -LiteralPath $overrideFile }
    if ($lock) { $lock.Dispose() }
}
exit $exitCode
