#!/bin/bash
cd "$(dirname "$0")"

# Define venv path
VENV_DIR="venv"
PYTHON_CMD="python3"

# Check if python3 exists
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "Python 3 not found."
    echo "Attempting to trigger Xcode Command Line Tools installation..."
    xcode-select --install
    
    echo "If a dialog appeared, please click 'Install'."
    echo "Once the installation is complete, run this script again."
    echo "If no dialog appeared, please install Python manually from https://www.python.org/downloads/"
    exit 1
fi

# Create or Verify venv
RECREATE_VENV=false
if [ ! -d "$VENV_DIR" ]; then
    RECREATE_VENV=true
else
    # Check if venv is functional (paths can break if moved)
    if ! "$VENV_DIR/bin/python" -c "import sys; print('ok')" &> /dev/null; then
        echo "Virtual environment appears broken (possibly moved). Recreating..."
        rm -rf "$VENV_DIR"
        RECREATE_VENV=true
    fi
fi

if [ "$RECREATE_VENV" = true ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_DIR"
fi

# Define paths to venv binaries
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# Ensure venv python works
if [ ! -x "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment python not found at $VENV_PYTHON"
    exit 1
fi

# Install/Update requirements
if [ -f "requirements.txt" ]; then
    echo "Checking and installing dependencies..."
    "$VENV_PYTHON" -m pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install requirements."
        exit 1
    fi
fi

# Open Browser (Wait a bit for server to start in background, or just open first)
echo "Opening browser..."
sleep 2
open http://127.0.0.1:8000 &

# Start App
echo "Starting Biochar Rejection Report Generator on Port 8000..."
"$VENV_PYTHON" app.py
