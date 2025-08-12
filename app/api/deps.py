from app.db.sessions import get_db
from app.ai.manager import AIBackendManager
from app.services.video_processor import VideoProcessor

__all__ = ["get_db"]

# Create singletons once
_ai_manager = AIBackendManager()
_video_processor = VideoProcessor(_ai_manager)

def get_ai_manager() -> AIBackendManager:
    return _ai_manager

def get_video_processor() -> VideoProcessor:
    return _video_processor