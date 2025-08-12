from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from ..deps import get_db
from ...db.models import ProcessingJob, VideoRecord
from app.schemas import JobStatus, VideoAnalysisResult

router = APIRouter()

@router.get("/job/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    videos = db.query(VideoRecord).filter(VideoRecord.job_id == job_id).all()
    results = []
    for v in videos:
        if v.processing_status == 'completed':
            results.append(VideoAnalysisResult(
                job_id=job_id, filename=v.filename, duration=v.duration,
                instructor_name=v.instructor_name, category=v.category or "Unknown",
                training_content=v.training_content or "", confidence_score=v.confidence_score or 0.0,
                extraction_method=v.extraction_method or "unknown", processing_status=v.processing_status
            ))
    progress = ((job.processed_files + job.failed_files) / job.total_files) * 100 if job.total_files else 0.0
    return JobStatus(
        job_id=job_id, status=job.status, total_files=job.total_files,
        processed_files=job.processed_files, failed_files=job.failed_files,
        progress_percentage=round(progress, 2), results=results
    )
