# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import upload as upload_route, jobs as jobs_route, videos as videos_route
from app.api.deps import get_ai_manager, get_video_processor

app = FastAPI(title="Video Content Extractor API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health")
async def health():
    ai = get_ai_manager()
    vp = get_video_processor()
    return {
        "status": "healthy",
        "ai_backend": ai.current_backend.name,
        "whisper_available": vp.whisper_model is not None,
        "version": "1.0.0"
    }

app.include_router(upload_route.router, tags=["upload"])
app.include_router(jobs_route.router, tags=["jobs"])
app.include_router(videos_route.router, tags=["videos"])
