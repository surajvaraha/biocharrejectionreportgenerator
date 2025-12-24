@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set VENV_DIR=venv
set PYTHON_CMD=python

REM Check if python exists
where %PYTHON_CMD% >nul 2>nul
if %errorlevel% neq 0 (
    echo Python not found. Attempting to install Python via Winget...
    winget install -e --id Python.Python.3.11 --scope machine
    
    if %errorlevel% neq 0 (
        echo.
        echo Error: Automatic installation failed.
        echo Please download and install Python from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    
    echo Python installed successfully!
    echo Please RESTART this script to continue.
    pause
    exit /b 0
)

REM Create or Verify venv
set RECREATE_VENV=false
if not exist "%VENV_DIR%" (
    set RECREATE_VENV=true
) else (
    REM Check if venv is functional (paths can break if moved)
    "%VENV_DIR%\Scripts\python.exe" -c "import sys; print('ok')" >nul 2>nul
    if %errorlevel% neq 0 (
        echo Virtual environment appears broken (possibly moved). Recreating...
        rmdir /s /q "%VENV_DIR%"
        set RECREATE_VENV=true
    )
)

if "%RECREATE_VENV%"=="true" (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv %VENV_DIR%
)

REM Define venv executable paths
set VENV_PYTHON=%VENV_DIR%\Scripts\python.exe

REM Install/Update requirements
if exist "requirements.txt" (
    echo Checking and installing dependencies...
    "%VENV_PYTHON%" -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo Error: Failed to install requirements.
        pause
        exit /b 1
    )
)

REM Open Browser
echo Opening browser...
timeout /t 2 /nobreak >nul
start http://127.0.0.1:8000

REM Start App
echo Starting Biochar Rejection Report Generator on Port 8000...
"%VENV_PYTHON%" app.py
pause
