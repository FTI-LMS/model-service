from pydantic import BaseModel, Field
from typing import Optional, List

class VideoAnalysisResult(BaseModel):
    job_id: str
    filename: str
    duration: float
    instructor_name: Optional[str] = None
    category: str
    training_content: str
    confidence_score: float
    extraction_method: str
    processing_status: str

class JobStatus(BaseModel):
    job_id: str
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    progress_percentage: float
    results: List[VideoAnalysisResult] = []

class UploadResponse(BaseModel):
    job_id: str
    message: str
    files_uploaded: int

class HealthCheck(BaseModel):
    status: str
    ai_backend: str
    whisper_available: bool
    version: str = "1.0.0"
