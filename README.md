# Biochar Rejection Report Generator

A robust web-based utility designed to automate the generation of partner-specific rejection reports from Biochar validation data. This tool supports multiple data formats and provides a simple, non-technical interface for generating PDF summaries of rejected batches.

## 🚀 Features

- **Web Interface**: Simple and intuitive UI for uploading files and selecting report types.
- **Multi-Format Support**: Explicit support for both **Looker Rejections** (Shambav Foundation) and **Kalki Rejections** data structures.
- **Robust Data Processing**:
    - **Flexible Column Matching**: Automatically handles variations in column names (extra spaces, casing, etc.).
    - **Case-Insensitive Status**: Correct recognition of "Rejected" status regardless of case.
    - **Missing Image Support**: Generates placeholders if image URLs are missing, ensuring no rejected row is lost.
- **High Performance**: Optimized to handle large datasets (up to 10,000+ rows) efficiently.
- **Partner-Specific PDFs**: Groups all rejections for a single partner into a single organized PDF.
- **ZIP Export**: Automatically packages all generated reports into a single downloadable ZIP file.

## 📥 Installation & Setup

This tool is designed to be usable by anyone, even without coding knowledge.

### For Windows Users
1. Download the project folder.
2. Double-click `run_tool.bat`.
3. The script will automatically check for Python, set up a virtual environment, install dependencies, and launch the tool in your browser.

### For Mac Users
1. Download the project folder.
2. Double-click `run_tool.command`.
3. The script will handle the environment setup and open the tool in your browser automatically.

## 📖 How to Use

1. **Launch the Tool**: Run the appropriate launcher script (`.bat` or `.command`) for your system.
2. **Select Sheet Type**: Choose between **Looker Rejections** or **Kalki Rejections** from the dropdown based on your input file.
3. **Upload File**: Select your Excel (`.xlsx`) or CSV file.
4. **Process**: Click "Start Processing".
5. **Download**: Once complete, a download link for a ZIP file containing all partner PDFs will appear.

## 🛠️ Technology Stack

- **Backend**: FastAPI (Python)
- **PDF Generation**: ReportLab
- **Data Handling**: Pandas
- **Frontend**: HTML5, Vanilla CSS, JavaScript

## 📂 Project Structure

- `app.py`: Web server and API endpoints.
- `automation.py`: Core logic for data parsing and PDF generation.
- `run_tool.bat / .command`: Automated launchers for Windows and Mac.
- `templates/`: HTML templates for the web interface.
- `requirements.txt`: List of Python dependencies.

---
Developed for Biochar Validation Automation.
