from pydantic import BaseModel
from typing import Optional

class FileProcessingResponse(BaseModel):
      filename: str
      duration: float
      transcript: str
      instructorName: Optional[str] = None
      moduleTopic: Optional[str] = None
      trainingTopic: Optional[str] = None
      category: Optional[str] = None
      confidence_score: float = 0.0
      extraction_method: Optional[str] = None