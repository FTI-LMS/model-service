import os
import sqlite3
import json
import re
from datetime import datetime
from pathlib import Path
import subprocess
import tempfile
import traceback
from typing import Dict, List, Optional, Tuple

# Required packages (install with pip):
# pip install openai python-dotenv moviepy whisper-openai sqlalchemy

import openai
from dotenv import load_dotenv
import moviepy.editor as mp
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from openai import OpenAI

# Load environment variables
load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)



# Database setup
Base = declarative_base()


class TrainingVideo(Base):
    __tablename__ = 'training_videos'

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    duration = Column(Float, nullable=False)  # in seconds
    instructor_name = Column(String(255))
    category = Column(String(100))
    training_content = Column(Text)
    transcript = Column(Text)
    confidence_score = Column(Float)  # AI confidence in extraction
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VideoContentExtractor:
    def __init__(self, openai_api_key: str = None, openai_base_url: str = None):
        """
        Initialize the Video Content Extractor

        Args:
            openai_api_key: OpenAI API key (or None for local setup)
            openai_base_url: Base URL for local OpenAI API (e.g., "http://localhost:1234/v1")
        """
        # Configure OpenAI client
        if openai_base_url:
            # Local OpenAI setup (like LM Studio, Ollama with OpenAI compatibility)
            self.client = OpenAI(
                api_key=openai_api_key or os.getenv("OPENAI_API_KEY"),
                base_url=openai_base_url or os.getenv("OPENAI_BASE_URL")
            )
        else:
            # Standard OpenAI setup
            openai.api_key = openai_api_key or os.getenv('OPENAI_API_KEY')

        # Database setup
        self.engine = create_engine('sqlite:///training_videos.db')
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Supported video formats
        self.supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']

    def extract_video_duration(self, video_path: str) -> float:
        """Extract video duration using moviepy"""
        try:
            with mp.VideoFileClip(video_path) as video:
                return video.duration
        except Exception as e:
            print(f"Error extracting duration: {e}")
            return 0.0

    def extract_audio_from_video(self, video_path: str, video_duration: int) -> str:
        """Extract audio from video file for transcription"""
        try:
            video = mp.VideoFileClip(video_path)
            # Trim video duration if needed
            if video_duration > 120:
                print(f"Clipping video duration")
                video = video.subclip(0, 60)

            # Create temporary audio file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                temp_audio_path = temp_audio.name

            # Extract audio
            audio = video.audio
            audio.write_audiofile(temp_audio_path, verbose=False, logger=None)

            video.close()
            audio.close()

            return temp_audio_path
        except Exception as e:
            print(f"Error extracting audio: {e}")
            return None

    def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio using OpenAI Whisper API"""
        try:
            with open(audio_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                ).text
            return transcript
        except Exception as e:
            print(f"Error in transcription: {e}")
            #traceback.print_exc()
            # Fallback: try with local whisper if available
            try:
                import whisper
                model = whisper.load_model("base")
                result = model.transcribe(audio_path)
                return result["text"]
            except Exception as e:
                print("❌ Local Whisper failed:")
                import traceback
                traceback.print_exc()
                return ""

    def analyze_content_with_ai(self, transcript: str) -> Dict:
        """Use OpenAI to analyze transcript and extract information"""
        prompt = f"""
        You are an AI trained to extract structured metadata from training video transcripts.

        Instructions:
        - Analyze the transcript below
        - Extract these 4 fields:
          1. instructor_name (full name if mentioned, else null)
          2. training_content (topics of training)
          3. category (like Technology, Health, Business, etc.)
          4. confidence_score (between 0 and 1)

        Respond ONLY with a valid JSON object like:
        {{
          "instructor_name": ...,
          "training_content": ...,
          "category": ...,
          "confidence_score": ...
        }}

        Transcript:
        \"\"\"
        {transcript[:1000]}
        \"\"\"
        """


        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # LM Studio ignores this, it's fine
                messages=[
                    #{"role": "system", "content": "You are an AI assistant..."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=5000,
                timeout=900,
                stream = True
            )
            #result = response.choices[0].message.content

            #result = response.choices[0].message.content.strip()

            result = ""
            for chunk in response:
                delta = chunk.choices[0].delta
                print("⚠️ Processing chunk...")
                if hasattr(delta, "content") and delta.content:
                    result += delta.content
                    print("⚠️ Processing chunk...result: {result}")

            # Try parsing JSON
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                print("⚠️ JSON parse failed. Trying fallback...")
                return self._parse_fallback_response(result)

        except Exception as e:
            print(f"Error in AI analysis: {e}")
            return {
                "instructor_name": None,
                "training_content": "Content analysis failed",
                "category": "Unknown",
                "confidence_score": 0.0
            }

    def _parse_fallback_response(self, response: str) -> Dict:
        """Fallback parsing if JSON response fails"""
        result = {
            "instructor_name": None,
            "training_content": "Could not extract content",
            "category": "Unknown",
            "confidence_score": 0.0
        }

        # Simple regex patterns for extraction
        instructor_match = re.search(r'"instructor_name":\s*"([^"]*)"', response)
        if instructor_match:
            result["instructor_name"] = instructor_match.group(1)

        content_match = re.search(r'"training_content":\s*"([^"]*)"', response)
        if content_match:
            result["training_content"] = content_match.group(1)

        category_match = re.search(r'"category":\s*"([^"]*)"', response)
        if category_match:
            result["category"] = category_match.group(1)

        return result

    def detect_instructor_from_patterns(self, transcript: str) -> Optional[str]:
        """Detect instructor name using text patterns"""
        patterns = [
            r"I'm ([A-Z][a-z]+ [A-Z][a-z]+)",
            r"My name is ([A-Z][a-z]+ [A-Z][a-z]+)",
            r"This is ([A-Z][a-z]+ [A-Z][a-z]+)",
            r"I am ([A-Z][a-z]+ [A-Z][a-z]+)",
            r"Hello, I'm ([A-Z][a-z]+ [A-Z][a-z]+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, transcript)
            if match:
                return match.group(1)

        return None

    def process_video(self, video_path: str) -> Dict:
        """Main method to process a single video file"""
        print(f"Processing video: {video_path}")

        # Validate file
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        file_ext = Path(video_path).suffix.lower()
        if file_ext not in self.supported_formats:
            raise ValueError(f"Unsupported video format: {file_ext}")

        # Extract basic metadata
        filename = os.path.basename(video_path)
        duration = self.extract_video_duration(video_path)

        print(f"Duration: {duration:.2f} seconds")

        # Extract and transcribe audio
        print("Extracting audio...")
        audio_path = self.extract_audio_from_video(video_path,duration)

        transcript = ""
        if audio_path:
            print("Transcribing audio...")
            transcript = self.transcribe_audio(audio_path)

            # Clean up temporary audio file
            try:
                os.unlink(audio_path)
            except:
                pass

        # Analyze content with AI
        print("Analyzing content with AI...")
        ai_analysis = self.analyze_content_with_ai(transcript)

        # Try pattern-based instructor detection as fallback
        if not ai_analysis.get("instructor_name"):
            pattern_instructor = self.detect_instructor_from_patterns(transcript)
            if pattern_instructor:
                ai_analysis["instructor_name"] = pattern_instructor

        # Prepare result
        result = {
            "filename": filename,
            "file_path": video_path,
            "duration": duration,
            "transcript": transcript,
            "instructor_name": ai_analysis.get("instructor_name"),
            "training_content": ai_analysis.get("training_content"),
            "category": ai_analysis.get("category"),
            "confidence_score": ai_analysis.get("confidence_score", 0.0)
        }

        return result

    def save_to_database(self, video_data: Dict) -> int:
        """Save extracted video data to database"""
        video_record = TrainingVideo(**video_data)

        self.session.add(video_record)
        self.session.commit()

        print(f"Saved to database with ID: {video_record.id}")
        return video_record.id

    def process_video_folder(self, folder_path: str) -> List[Dict]:
        """Process all videos in a folder"""
        results = []
        folder_path = Path(folder_path)

        for video_file in folder_path.rglob("*"):
            if video_file.suffix.lower() in self.supported_formats:
                try:
                    result = self.process_video(str(video_file))
                    video_id = self.save_to_database(result)
                    result["database_id"] = video_id
                    results.append(result)
                    print(f"✅ Successfully processed: {video_file.name}\n")
                except Exception as e:
                    print(f"❌ Error processing {video_file.name}: {e}\n")
                    continue

        return results

    def get_video_by_id(self, video_id: int) -> Optional[TrainingVideo]:
        """Retrieve video record from database"""
        return self.session.query(TrainingVideo).filter(TrainingVideo.id == video_id).first()

    def search_videos(self, category: str = None, instructor: str = None) -> List[TrainingVideo]:
        """Search videos by category or instructor"""
        query = self.session.query(TrainingVideo)

        if category:
            query = query.filter(TrainingVideo.category.ilike(f"%{category}%"))

        if instructor:
            query = query.filter(TrainingVideo.instructor_name.ilike(f"%{instructor}%"))

        return query.all()

    def close(self):
        """Close database session"""
        self.session.close()


# Example usage and testing
def main():
    """Example usage of the VideoContentExtractor"""

    # Initialize extractor
    extractor = VideoContentExtractor(
        # For local OpenAI API (e.g., LM Studio):
        openai_base_url="http://localhost:1234/v1",
        openai_api_key="lm-studio"
    )

    try:
        # Process a single video
        video_path = "videos/training-video.mp4"

        # Check if file exists (for demo purposes)
        if os.path.exists(video_path):
            result = extractor.process_video(video_path)
            video_id = extractor.save_to_database(result)

            print("Extraction Results:")
            print(f"Instructor: {result['instructor_name']}")
            print(f"Category: {result['category']}")
            print(f"Duration: {result['duration']:.2f} seconds")
            print(f"Content: {result['training_content']}")
            print(f"Confidence: {result['confidence_score']:.2f}")
        else:
            print("Demo: Video file not found. Please update the video_path variable.")

        # Process entire folder (uncomment to use)
        # results = extractor.process_video_folder("path/to/video/folder")

        # Search examples
        # tech_videos = extractor.search_videos(category="Technology")
        # instructor_videos = extractor.search_videos(instructor="John")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        extractor.close()


if __name__ == "__main__":
    main()