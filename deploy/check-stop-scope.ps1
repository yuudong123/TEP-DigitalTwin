# Return 0 only when Docker/WSL shutdown cannot interrupt a non-TEP workload.
$ErrorActionPreference = 'Stop'
try {
    & docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        $rows = & docker ps --format '{{json .}}'
        if ($LASTEXITCODE -ne 0) { throw 'Container inventory failed.' }
        foreach ($line in $rows) {
            $container = $line | ConvertFrom-Json
            if (($container.Labels -split ',') -notcontains 'com.docker.compose.project=tep_digitaltwin') {
                Write-Host ('[KEEP] Non-TEP Docker workload: ' + $container.Names)
                exit 2
            }
        }
    } elseif (Get-Process -Name 'com.docker.backend' -ErrorAction SilentlyContinue) {
        Write-Host '[KEEP] Docker backend is running but container inventory is unavailable.'
        exit 2
    }
    $distros = & wsl.exe --list --running --quiet
    if ($LASTEXITCODE -ne 0) { throw 'WSL inventory failed.' }
    foreach ($line in $distros) {
        $name = $line.Replace([string][char]0,'').Trim()
        if ($name -and $name -notin @('docker-desktop','docker-desktop-data')) {
            Write-Host ('[KEEP] Non-Docker WSL workload: ' + $name)
            exit 2
        }
    }
    exit 0
} catch {
    Write-Host '[KEEP] Shutdown scope could not be verified; Docker and WSL will be kept.'
    exit 2
}
