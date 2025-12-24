# Biochar Validation Automation Tool

## Overview
This tool automates the process of validating biochar data and generating PDFs. It runs locally on your machine.

## Prerequisites
This tool requires **Python 3.8+**. 
**Good News**: The included run scripts (`run_tool.command` and `run_tool.bat`) will attempt to automatically install Python for you if it's missing!

- **Mac**: The script will trigger the Xcode Command Line Tools installation if needed.
- **Windows**: The script will try to use `winget` to install Python.

## How to Run

### Mac / Linux
1. Open the folder containing these files.
2. Double-click **`run_tool.command`**.
   - If it doesn't run, you may need to allow execution permission. Open Terminal, type `chmod +x `, drag the `run_tool.command` file into the terminal, and press Enter. Then try double-clicking again.
3. A terminal window will open and install dependencies (the first time) and then start the server.
4. Your browser should open automatically to `http://127.0.0.1:8000`.

### Windows
1. Open the folder containing these files.
2. Double-click **`run_tool.bat`**.
3. A command prompt will open, install dependencies (the first time), and start the server.
4. Your browser should open automatically to `http://127.0.0.1:8000`.

## Using the Tool
1. Upload your `.xlsx` or `.csv` file.
2. Click "Upload & Process".
3. Wait for the processing to complete (the progress bar will update).
4. Once finished, a "Download Reports" button will appear. Click it to download a ZIP file containing all generated PDF reports.

## Troubleshooting
- **Browser doesn't open**: Manually open your browser and go to `http://127.0.0.1:8000`.
- **Python not found**: Ensure Python is installed and added to your system PATH.
