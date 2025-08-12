from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db
from ...db.models import VideoRecord

router = APIRouter()

@router.get("/videos")
async def search_videos(
    category: Optional[str] = None,
    instructor: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    q = db.query(VideoRecord).filter(VideoRecord.processing_status == 'completed')
    if category: q = q.filter(VideoRecord.category.ilike(f"%{category}%"))
    if instructor: q = q.filter(VideoRecord.instructor_name.ilike(f"%{instructor}%"))
    videos = q.limit(limit).all()
    return [
        {
            "id": v.id, "filename": v.filename, "duration": v.duration,
            "instructor_name": v.instructor_name, "category": v.category,
            "training_content": v.training_content, "confidence_score": v.confidence_score,
            "extraction_method": v.extraction_method, "created_at": v.created_at
        } for v in videos
    ]
