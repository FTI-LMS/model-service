import os, uuid, shutil
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from ...core.config import Config
from ...db.models import ProcessingJob, VideoRecord
from app.schemas import UploadResponse
from ...services.workers import process_videos_background
from ...services.video_processor import VideoProcessor
from ..deps import get_db, get_video_processor

router = APIRouter()

def save_uploads(files: List[UploadFile]) -> List[str]:
    paths = []
    for f in files:
        file_id = str(uuid.uuid4())
        ext = Path(f.filename).suffix
        unique = f"{file_id}{ext}"
        p = Config.UPLOAD_DIR / unique
        with open(p, "wb") as buf:
            shutil.copyfileobj(f.file, buf)
        paths.append(str(p))
    return paths

@router.post("/upload", response_model=UploadResponse)
async def upload_videos(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    video_processor: VideoProcessor = Depends(get_video_processor),
):
    job_id = str(uuid.uuid4())
    valid = []
    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in Config.SUPPORTED_FORMATS:
            raise HTTPException(400, f"Unsupported file format: {ext}")
        valid.append(f)
    if not valid:
        raise HTTPException(400, "No valid video files provided")

    job = ProcessingJob(job_id=job_id, total_files=len(valid), status='pending')
    db.add(job); db.commit()

    Config.UPLOAD_DIR.mkdir(exist_ok=True)
    video_paths = save_uploads(valid)

    for f, p in zip(valid, video_paths):
        rec = VideoRecord(
            job_id=job_id, filename=f.filename, file_path=p,
            file_size=Path(p).stat().st_size, duration=0.0, processing_status='pending'
        )
        db.add(rec)
    db.commit()

    background_tasks.add_task(process_videos_background, job_id, video_paths, video_processor)
    return UploadResponse(job_id=job_id, message=f"Uploaded {len(valid)} files", files_uploaded=len(valid))
