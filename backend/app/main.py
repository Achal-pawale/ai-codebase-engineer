from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import subprocess
import shutil
import os
import stat

app = FastAPI(title="AI Codebase Engineer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)

IGNORE_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv"}


class IngestRequest(BaseModel):
    repo_url: str


@app.get("/")
def root():
    return {"message": "AI Codebase Engineer API is running."}


@app.get("/health")
def health_check():
    return {"status": "ok"}



def remove_readonly(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)

@app.post("/ingest")
def ingest_repo(req: IngestRequest):
    repo_name = req.repo_url.rstrip("/").split("/")[-1]
    dest = WORKSPACE_DIR / repo_name

    if dest.exists():
        shutil.rmtree(dest, onerror=remove_readonly)

    result = subprocess.run(
        ["git", "clone", "--depth", "1", req.repo_url, str(dest)],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        return {"success": False, "error": result.stderr}

    top_level = [item.name for item in dest.iterdir() if item.name not in IGNORE_DIRS]

    file_count = 0
    for root, dirs, files in os.walk(dest):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        file_count += len(files)

    return {
        "success": True,
        "cloned_to": str(dest),
        "top_level_items": sorted(top_level),
        "file_count": file_count,
    }
