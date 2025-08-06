import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')

    if not OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY is not loaded!")
    else:
        print("✅ API key loaded.")

    # Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///training_videos.db')

    # Processing Configuration
    MAX_TRANSCRIPT_LENGTH = int(os.getenv('MAX_TRANSCRIPT_LENGTH', 5000))
    DEFAULT_CONFIDENCE_THRESHOLD = float(os.getenv('DEFAULT_CONFIDENCE_THRESHOLD', 0.5))

    # Paths
    VIDEO_STORAGE_PATH = os.getenv('VIDEO_STORAGE_PATH', './videos/')
    TEMP_AUDIO_PATH = os.getenv('TEMP_AUDIO_PATH', './temp/')
    DATABASE_PATH = os.getenv('DATABASE_PATH', './training_videos.db')

    # Supported formats
    SUPPORTED_VIDEO_FORMATS = os.getenv(
        'SUPPORTED_VIDEO_FORMATS',
        '.mp4,.avi,.mov,.mkv,.wmv,.flv,.webm'
    ).split(',')

    @classmethod
    def validate(cls):
        """Validate configuration"""
        if not cls.OPENAI_API_KEY and not cls.OPENAI_BASE_URL:
            raise ValueError("Either OPENAI_API_KEY or OPENAI_BASE_URL must be set")

        # Create directories if they don't exist
        os.makedirs(cls.VIDEO_STORAGE_PATH, exist_ok=True)
        os.makedirs(cls.TEMP_AUDIO_PATH, exist_ok=True)

        return True