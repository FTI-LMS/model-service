from datetime import datetime
from typing import List
from sqlalchemy.orm import Session
from ..db.sessions import SessionLocal
from ..db.models import ProcessingJob
from .video_processor import VideoProcessor


async def process_videos_background_async(job_id: str, video_paths: List[str], video_processor: VideoProcessor):
    db: Session = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
        if job:
            job.status = 'processing';
            db.commit()

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
            job.status = 'failed';
            db.commit()
    finally:
        db.close()


def process_videos_background(job_id: str, video_paths: List[str], video_processor: VideoProcessor):
    db: Session = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
        if job:
            job.status = 'processing';
            db.commit()

        processed = failed = 0
        for i, path in enumerate(video_paths):
            try:
                file_size = os.path.getsize(path)
                filename = os.path.basename(path)

                print(f"Processing file {i + 1}/{len(video_paths)}: {filename} ({file_size / (1024 * 1024):.1f}MB)")

                # Skip files that are too large
                if file_size > 1000 * 1024 * 1024:  # 1GB
                    print(f"Skipping {filename}: File too large ({file_size / (1024 * 1024):.1f}MB)")
                    failed += 1
                    continue

                # Add timeout wrapper
                import signal

                def timeout_handler(signum, frame):
                    raise TimeoutError("Processing timeout")

                # Set timeout based on file size (larger files get more time)
                timeout_seconds = min(600, max(120, file_size // (10 * 1024 * 1024)))  # 2-10 minutes

                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout_seconds)

                try:
                    video_processor.process_video(path, job_id, db)
                    processed += 1
                    print(f"✅ Successfully processed: {filename}")
                except TimeoutError:
                    print(f"❌ Timeout processing {filename} after {timeout_seconds}s")
                    failed += 1
                finally:
                    signal.alarm(0)  # Cancel timeout

                # Force garbage collection every 2 files to prevent memory buildup
                if (processed + failed) % 2 == 0:
                    import gc
                    gc.collect()
                    print(f"Memory cleanup after {processed + failed} files")

            except Exception as e:
                failed += 1
                print(f"❌ Failed to process {path}: {e}")

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
            job.status = 'failed';
            db.commit()
    finally:
        db.close()
