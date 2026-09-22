# User-run setup: register only this user's TEP agent at sign-in, without elevation.
[CmdletBinding()]
param([string]$ProjectDir = 'D:\TEP_DigitalTwin')
$ErrorActionPreference = 'Stop'
$runner = Join-Path $ProjectDir 'deploy\10-start-agent.ps1'
if (-not (Test-Path -LiteralPath $runner)) { throw "Agent runner missing: $runner" }
if (Get-ScheduledTask -TaskName 'TEP-Jenkins-Agent' -ErrorAction SilentlyContinue) {
    throw 'TEP-Jenkins-Agent already exists; review its settings instead of overwriting it.'
}
$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $runner + '" -ProjectDir "' + $ProjectDir + '"')
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $account
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'TEP-Jenkins-Agent' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'TEP home-PC Jenkins agent. Uses the signed-in user and existing Git authentication.' | Out-Null
$agentJar = Join-Path $ProjectDir '.jenkins-agent\agent.jar'
$running = @(Get-CimInstance Win32_Process -Filter "Name='java.exe' OR Name='javaw.exe'" | Where-Object {
    $_.CommandLine -and $_.CommandLine.Contains($agentJar) -and $_.CommandLine.Contains('-name TEP-Windows')
})
if ($running.Count -eq 0) {
    Start-ScheduledTask -TaskName 'TEP-Jenkins-Agent'
} else {
    Write-Host 'The agent is already running. Registered for next sign-in; no duplicate was started.'
}
Get-ScheduledTask -TaskName 'TEP-Jenkins-Agent' | Select-Object TaskName, State
Write-Host 'Open http://localhost:8080/computer/TEP-Windows/ and confirm the agent is online.'
