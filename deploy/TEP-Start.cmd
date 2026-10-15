@echo off
setlocal EnableExtensions
title TEP DigitalTwin - Start
if /I "%TEP_START_NO_ELEVATE%"=="1" goto :ready
net session >nul 2>&1
if not "%errorlevel%"=="0" (
    powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
:ready
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "D:\TEP_DigitalTwin\deploy\start-services.ps1" -ProjectDir "D:\TEP_DigitalTwin"
if errorlevel 1 echo [WARN] TEP startup failed. See the message above.
if /I not "%TEP_START_NO_PAUSE%"=="1" pause
endlocal
