from fastapi import FastAPI, Request, UploadFile, File, BackgroundTasks, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import shutil
import os
import zipfile
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from automation import process_data_and_generate_reports
import logging
import sys

# Ensure log file is deleted on startup for a fresh start
LOG_FILE = "server_app.log"
if os.path.exists(LOG_FILE):
    try:
        os.remove(LOG_FILE)
    except:
        pass

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("BiocharApp")

# Change working directory to the directory of the executable (if frozen)
# or the script (if running from source), to ensure relative paths work.
if getattr(sys, 'frozen', False):
    # Running as compiled PyInstaller binary
    application_path = os.path.dirname(sys.executable)
    os.chdir(application_path)
else:
    # Running as standard Python script
    # logic already handled by run_tool.command/bat usually, but good fallback:
    pass 
    
app = FastAPI()

# Mount templates
templates = Jinja2Templates(directory="templates")

# Config
UPLOAD_FOLDER = "uploads"
OUTPUT_DIR = "generated_reports"
ZIPS_DIR = "zips"

for d in [UPLOAD_FOLDER, OUTPUT_DIR, ZIPS_DIR]:
    os.makedirs(d, exist_ok=True)

ALLOWED_EXTENSIONS = {'xlsx', 'csv'}

# Global store for task progress
# Format: {task_id: {"status": "processing", "message": "...", "percent": 0, "result": None}}
task_progress = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def zip_results(task_id, file_paths):
    zip_filename = f"reports_{task_id}.zip"
    zip_path = os.path.join(ZIPS_DIR, zip_filename)
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in file_paths:
            if os.path.exists(file):
                 zipf.write(file, os.path.basename(file))
    return zip_path

def run_automation_task(task_id, file_path, sheet_type='shambav'):
    def update_progress(msg):
        task_progress[task_id]["message"] = msg
        # Simple heuristic for percentage if possible, or just keep spinning
    
    try:
        task_progress[task_id] = {"status": "processing", "message": "Starting...", "percent": 0}
        
        # Run blocking automation
        logger.info(f"Task {task_id}: Starting automation processing for {file_path}")
        success, message, file_paths = process_data_and_generate_reports(file_path, sheet_type=sheet_type, progress_callback=update_progress)
        
        if success and file_paths:
            logger.info(f"Task {task_id}: Processing successful. Zipping {len(file_paths)} files.")
            zip_path = zip_results(task_id, file_paths)
            task_progress[task_id] = {
                "status": "complete", 
                "message": "Done!", 
                "download_url": f"/download/{os.path.basename(zip_path)}"
            }
        else:
             logger.warning(f"Task {task_id}: Processing failed or no rejections found. Message: {message}")
             task_progress[task_id] = {"status": "error", "message": message}
             
    except Exception as e:
        logger.exception(f"Task {task_id}: Unhandled exception during processing")
        task_progress[task_id] = {"status": "error", "message": str(e)}
    finally:
        # Cleanup upload
        if os.path.exists(file_path):
            os.remove(file_path)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def process_file(
    file: UploadFile = File(...), 
    sheet_type: str = Form("shambav"),
    background_tasks: BackgroundTasks = None
):
    if not file.filename:
        return JSONResponse(status_code=400, content={"message": "No file selected"})
        
    if not allowed_file(file.filename):
        return JSONResponse(status_code=400, content={"message": "Invalid file type"})
    
    task_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Initialize task status
    task_progress[task_id] = {"status": "queued", "message": "Queued..."}
    
    # Start background task
    logger.info(f"New upload received: {file.filename}, assigned task_id: {task_id}")
    background_tasks.add_task(run_automation_task, task_id, file_path, sheet_type)
    
    return {"task_id": task_id}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    return task_progress.get(task_id, {"status": "unknown"})

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(ZIPS_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename)
    return JSONResponse(status_code=404, content={"message": "File not found"})

if __name__ == "__main__":
    logger.info("Starting FastAPI server...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
