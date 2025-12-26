@echo off
setlocal enabledelayedexpansion
title Biochar Rejection Report Generator

:: Change directory to the script's location
cd /d "%~dp0"

set VENV_DIR=venv
set PORT=8000
set HOST=127.0.0.1

echo ======================================================
echo   Biochar Rejection Report Generator - Windows Setup
echo ======================================================

:: 1. Check if Port 8000 is already in use
netstat -ano | findstr :%PORT% >nul 2>nul
if %errorlevel% equ 0 (
    echo [ERROR] Port %PORT% is already in use by another application.
    echo Please close any other instances of this tool or applications using port %PORT%.
    pause
    exit /b 1
)

:: 2. Robust Python Detection
:: Try 'python' first, then check if it's the valid interpreter
set PYTHON_CMD=python
%PYTHON_CMD% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Python not found in PATH or is the Windows Store shim.
    echo [INFO] Attempting to install Python via Winget...
    
    winget install -e --id Python.Python.3.11 --scope machine
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Automatic installation failed. 
        echo please install Python manually from https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
    echo [SUCCESS] Python installed. Please RESTART this script.
    pause
    exit /b 0
)

:: 3. Virtual Environment Management
if not exist "%VENV_DIR%" (
    echo [INFO] Creating virtual environment...
    %PYTHON_CMD% -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    REM Simple check if venv is functional
    if not exist "%VENV_DIR%\Scripts\python.exe" (
        echo [WARNING] Virtual environment looks corrupted. Recreating...
        rmdir /s /q "%VENV_DIR%"
        %PYTHON_CMD% -m venv %VENV_DIR%
    )
)

set VENV_PYTHON="%VENV_DIR%\Scripts\python.exe"

:: 4. Dependency Installation
if exist "requirements.txt" (
    echo [INFO] Checking and installing dependencies...
    %VENV_PYTHON% -m pip install --upgrade pip >nul 2>&1
    %VENV_PYTHON% -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install requirements.
        pause
        exit /b 1
    )
)

:: 5. Start Application and Wait for Port
echo [INFO] Starting Biochar Rejection Report Generator...
start "Biochar Server" /min %VENV_PYTHON% app.py

echo [INFO] Waiting for server to start on http://%HOST%:%PORT%...
:: Using PowerShell to wait until the port is active (timeout 30s)
powershell -Command "$waitCount = 0; while (!(Test-NetConnection %HOST% -Port %PORT% -WarningAction SilentlyContinue).TcpTestSucceeded -and $waitCount -lt 30) { Start-Sleep -Seconds 1; $waitCount++ }"

:: 6. Launch Browser
echo [INFO] Opening browser...
start http://%HOST%:%PORT%

echo.
echo ======================================================
echo   Application is running!
echo   You can close this window to stop the server.
echo ======================================================
echo.

:: Keep the window open to show logs if they redirected here, or just to keep proc alive
pause
