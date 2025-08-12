from fastapi import APIRouter
from app.schemas import HealthCheck

router = APIRouter()

def get_health_payload(ai_backend_name: str, whisper_available: bool) -> HealthCheck:
    return HealthCheck(
        status="healthy",
        ai_backend=ai_backend_name,
        whisper_available=whisper_available
    )

@router.get("/health", response_model=HealthCheck)
async def health():
    # Placeholder; main.py injects actual values via dependency override if needed
    return get_health_payload("unknown", False)
