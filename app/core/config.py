import os
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()

class Config:
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./video_extractor.db")

    # Files
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 500 * 1024 * 1024))
    SUPPORTED_FORMATS = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']

    # AI backend selection
    AI_BACKEND = os.getenv("AI_BACKEND", "auto")  # auto|llama-cpp|ollama|openai

    # llama.cpp (Gemma)
    LLAMA_MODEL_PATH = os.getenv("LLAMA_MODEL_PATH", "./models/gemma-2-2b-it-q4_k_m.gguf")
    LLAMA_N_CTX = int(os.getenv("LLAMA_N_CTX", 4096))
    LLAMA_N_THREADS = int(os.getenv("LLAMA_N_THREADS", 6))
    LLAMA_CHAT_FORMAT = os.getenv("LLAMA_CHAT_FORMAT", "gemma")
    LLAMA_MAX_TOKENS = int(os.getenv("LLAMA_MAX_TOKENS", 256))
    LLAMA_TEMPERATURE = float(os.getenv("LLAMA_TEMPERATURE", 0.2))
    LLAMA_TOP_P = float(os.getenv("LLAMA_TOP_P", 0.9))

    # Ollama
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")

    # Whisper
    WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
