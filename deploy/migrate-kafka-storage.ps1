# One-time migration. Run on the Docker host before deploying persistent Compose.
[CmdletBinding()]
param([string]$BackupRoot = 'D:\TEP_DigitalTwin\logs')
$ErrorActionPreference = 'Stop'
function Invoke-Docker {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker failed: $DockerArgs" }
}
$state = (& docker inspect tep-kafka | ConvertFrom-Json)[0]
if ($LASTEXITCODE -ne 0) { throw 'Existing tep-kafka is required for migration.' }
if (@($state.Mounts | Where-Object { $_.Destination -eq '/tmp/kraft-combined-logs' }).Count) {
    throw 'Kafka already has a data mount; inspect it before attempting migration.'
}
$volumes = @(& docker volume ls --format '{{.Name}}')
if ($LASTEXITCODE -ne 0) { throw 'Cannot list Docker volumes.' }
if ($volumes -contains 'tep-kafka-data') { throw 'Target volume exists; refusing to overwrite it.' }
$backup = Join-Path $BackupRoot ('kafka-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$null = New-Item -ItemType Directory -Path $backup
$helper = 'tep-kafka-storage-copy-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
try {
    Invoke-Docker -DockerArgs @('stop', '--time', '60', 'tep-kafka')
    Invoke-Docker -DockerArgs @('cp', 'tep-kafka:/tmp/kraft-combined-logs/.', $backup)
    if (-not (Test-Path (Join-Path $backup 'meta.properties'))) { throw 'Backup lacks Kafka metadata.' }
    Invoke-Docker -DockerArgs @('volume', 'create', 'tep-kafka-data')
    Invoke-Docker -DockerArgs @('create', '--name', $helper, '--user', '0', '--mount', 'type=volume,source=tep-kafka-data,target=/target', '--entrypoint', '/bin/sh', 'apache/kafka:4.1.0', '-c', 'chown -R 1000:1000 /target')
    Invoke-Docker -DockerArgs @('cp', ($backup + '\.'), ($helper + ':/target'))
    Invoke-Docker -DockerArgs @('start', '--attach', $helper)
    $copyState = (& docker inspect $helper | ConvertFrom-Json)[0]
    if ($copyState.State.ExitCode -ne 0) { throw 'Volume ownership setup failed.' }
    Invoke-Docker -DockerArgs @('rm', $helper)
    Write-Host "Backup retained: $backup"
    Write-Host 'Migration complete. Keep the old broker stopped until persistent Compose is deployed.'
} catch {
    & docker start tep-kafka | Out-Null
    throw
}
