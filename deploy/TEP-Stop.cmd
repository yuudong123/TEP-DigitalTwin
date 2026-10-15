@echo off
setlocal EnableExtensions

title TEP DigitalTwin - Stop

if /I "%TEP_STOP_NO_ELEVATE%"=="1" goto :elevated

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo [INFO] Requesting administrator permission...
    powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

:elevated
echo ==========================================
echo   TEP DigitalTwin - STOP
echo ==========================================
echo.

echo [1/6] Stop the TEP Docker Compose stack
if exist "D:\TEP_DigitalTwin\compose.yaml" (
    docker info >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Docker engine is already stopped; no TEP containers can be running.
    ) else (
        pushd "D:\TEP_DigitalTwin"
        docker compose --project-name tep_digitaltwin down
        if errorlevel 1 (
            echo [WARN] docker compose down failed.
        ) else (
            echo [OK] TEP Compose stack stopped. Volumes and images were kept.
        )
        popd
    )
) else (
    echo [WARN] Project not found: D:\TEP_DigitalTwin
)
echo.

echo [2/6] Stop Jenkins controller without changing StartupType
sc.exe query Jenkins >nul 2>&1
if errorlevel 1 (
    echo [INFO] Jenkins service was not found.
) else (
    sc.exe query Jenkins | findstr /I "RUNNING" >nul
    if errorlevel 1 (
        echo [INFO] Jenkins service is already stopped.
    ) else (
        net.exe stop Jenkins
        if errorlevel 1 (
            echo [WARN] Jenkins service stop failed.
        ) else (
            echo [OK] Jenkins service stopped. StartupType was not changed.
        )
    )
)
echo.

echo [3/6] Stop the current TEP Jenkins agent only
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$task=Get-ScheduledTask -TaskName 'TEP-Jenkins-Agent' -ErrorAction SilentlyContinue; if($task -and $task.State -eq 'Running'){Stop-ScheduledTask -TaskName 'TEP-Jenkins-Agent' -ErrorAction Continue; Write-Host '[OK] Running TEP agent task stopped.'}else{Write-Host '[INFO] TEP agent task is not running.'}; $agents=Get-CimInstance Win32_Process | Where-Object { ($_.Name -in @('java.exe','javaw.exe')) -and ($_.CommandLine -match '(agent\.jar|remoting\.jar)') -and ($_.CommandLine -match '(TEP-Windows|tep-windows|TEP-dev|D:\\TEP_DigitalTwin)') }; if($agents){foreach($agent in $agents){Write-Host ('[INFO] Stopping agent PID ' + $agent.ProcessId); Stop-Process -Id $agent.ProcessId -Force -ErrorAction Continue}; Write-Host '[OK] TEP Jenkins agent process stopped.'}else{Write-Host '[INFO] TEP Jenkins agent process was not found.'}"
echo.

echo [4/6] Stop Docker Desktop
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "D:\TEP_DigitalTwin\deploy\check-stop-scope.ps1"
if errorlevel 1 (
    echo [INFO] Other work or uncertain state detected. Keeping Docker Desktop and WSL.
    goto :finalstatus
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$p=Start-Process -FilePath 'docker.exe' -ArgumentList @('desktop','stop') -WindowStyle Hidden -PassThru; if($p.WaitForExit(15000)){exit $p.ExitCode}else{Write-Host '[WARN] Docker Desktop did not stop within 15 seconds.'; taskkill.exe /PID $p.Id /T /F | Out-Null; exit 124}"
if errorlevel 1 (
    echo [INFO] Closing remaining Docker Desktop processes...
    taskkill.exe /IM "Docker Desktop.exe" /F >nul 2>&1
    taskkill.exe /IM "com.docker.backend.exe" /F >nul 2>&1
) else (
    echo [OK] Docker Desktop stopped.
)
echo.

echo [5/6] Shut down Docker WSL VM and release VmmemWSL memory
wsl.exe --shutdown
if errorlevel 1 (
    echo [WARN] WSL shutdown failed.
) else (
    echo [OK] WSL shutdown completed.
)
echo.

:finalstatus
echo [6/6] Final status
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$tep=Get-CimInstance Win32_Process | Where-Object { ($_.Name -in @('java.exe','javaw.exe')) -and ($_.CommandLine -match '(agent\.jar|remoting\.jar)') -and ($_.CommandLine -match '(TEP-Windows|tep-windows|TEP-dev|D:\\TEP_DigitalTwin)') }; $docker=Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -Match '^(Docker Desktop|com\.docker\.backend)$'; $vmmem=Get-Process -Name 'vmmemWSL' -ErrorAction SilentlyContinue; Write-Host ('TEP agent processes : ' + @($tep).Count); Write-Host ('Docker processes    : ' + @($docker).Count); Write-Host ('VmmemWSL processes  : ' + @($vmmem).Count)"
for %%S in (Jenkins Tailscale sshd) do (
    sc.exe query "%%S" | findstr /I "STATE"
    sc.exe qc "%%S" | findstr /I "START_TYPE"
)
echo.
echo Tailscale and OpenSSH were intentionally left running.
echo No startup setting, volume, image, or project data was changed.
echo ==========================================
echo.

if /I not "%TEP_STOP_NO_PAUSE%"=="1" pause
endlocal
