[CmdletBinding()]
param([string]$ProjectDir)
$ErrorActionPreference = 'Stop'
if (-not $ProjectDir) { $ProjectDir = Split-Path $PSScriptRoot -Parent }
$ProjectDir = (Resolve-Path -LiteralPath $ProjectDir).Path
if (-not (Test-Path -LiteralPath (Join-Path $ProjectDir 'compose.yaml'))) { throw 'TEP compose.yaml not found.' }
Write-Host '[1/4] Docker engine'
& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $process = Start-Process -FilePath 'docker.exe' -ArgumentList @('desktop','start') -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(30000)) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue }
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        & docker info *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 3
    }
    if (-not $ready) { throw 'Docker Desktop did not become ready.' }
}
Write-Host '[2/4] TEP services (existing built images; no build or deletion)'
Push-Location $ProjectDir
try {
    & docker compose up --no-build --detach --wait --wait-timeout 180 kafka api inference monitor
    if ($LASTEXITCODE -ne 0) { throw 'TEP services failed to start.' }
} finally { Pop-Location }
Write-Host '[3/4] Jenkins and existing agent task'
$jenkins = Get-Service -Name Jenkins -ErrorAction SilentlyContinue
if ($jenkins -and $jenkins.Status -ne 'Running') { Start-Service -Name Jenkins }
$task = Get-ScheduledTask -TaskName 'TEP-Jenkins-Agent' -ErrorAction SilentlyContinue
if ($task -and $task.State -ne 'Running') { Start-ScheduledTask -TaskName 'TEP-Jenkins-Agent' }
Write-Host '[4/4] API readiness'
$ready = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/ready' -TimeoutSec 10
if ($ready.status -ne 'ready') { throw 'API is not ready.' }
Write-Host '[OK] http://tep-server:8000/'
Write-Host 'Startup settings, models, volumes, Tailscale and OpenSSH were not changed.'
