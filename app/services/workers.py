from datetime import datetime
from typing import List
from sqlalchemy.orm import Session
from ..db.sessions import SessionLocal
from ..db.models import ProcessingJob
from .video_processor import VideoProcessor

async def process_videos_background(job_id: str, video_paths: List[str], video_processor: VideoProcessor):
    db: Session = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
        if job:
            job.status = 'processing'; db.commit()

        processed = failed = 0
        for path in video_paths:
            try:
                await video_processor.process_video(path, job_id, db)
                processed += 1
            except Exception as e:
                failed += 1
                print(f"Failed to process {path}: {e}")
            if job:
                job.processed_files = processed
                job.failed_files = failed
                db.commit()

        if job:
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            db.commit()
    except Exception as e:
        print(f"Background processing error: {e}")
        if job:
            job.status = 'failed'; db.commit()
    finally:
        db.close()
