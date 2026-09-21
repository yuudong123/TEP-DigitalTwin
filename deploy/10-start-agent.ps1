# Run under the signed-in Windows user. No GitHub token is copied or stored here.
[CmdletBinding()]
param([string]$ProjectDir)
$ErrorActionPreference = 'Stop'
if (-not $ProjectDir) { $ProjectDir = Split-Path $PSScriptRoot -Parent }
$agentDir = Join-Path $ProjectDir '.jenkins-agent'
foreach ($name in @('agent.jar', 'agent.secret')) {
    if (-not (Test-Path -LiteralPath (Join-Path $agentDir $name))) { throw "Missing agent file: $name" }
}
$mutex = New-Object System.Threading.Mutex($false, 'Local\TEP-Jenkins-Agent')
if (-not $mutex.WaitOne(0)) { exit 0 }
try {
    $java = (Get-Command java.exe -ErrorAction Stop).Source
    $agentArgs = @('-jar', ('"' + (Join-Path $agentDir 'agent.jar') + '"'), '-url', 'http://localhost:8080/', '-secret', ('"@' + (Join-Path $agentDir 'agent.secret') + '"'), '-name', 'TEP-Windows', '-webSocket', '-workDir', ('"' + $agentDir + '"'))
    while ($true) {
        $process = Start-Process -FilePath $java -ArgumentList $agentArgs -WorkingDirectory $agentDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $agentDir 'agent.stdout.log') -RedirectStandardError (Join-Path $agentDir 'agent.stderr.log') -PassThru
        $process.WaitForExit()
        Start-Sleep -Seconds 15
    }
} finally { $mutex.ReleaseMutex(); $mutex.Dispose() }
