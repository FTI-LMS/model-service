import os, tempfile
from typing import Optional, Dict, Any
from datetime import datetime
import moviepy.editor as mp
import asyncio
from app.services.slide_processor import extract_instructor_from_slides, choose_instructor

try:
    import whisper as whisper_og

    WHISPER_OG_OK = True
except Exception:
    WHISPER_OG_OK = False

try:
    from faster_whisper import WhisperModel

    FASTER_OK = True
except Exception:
    FASTER_OK = False

from sqlalchemy.orm import Session
from app.core.config import Config
from app.db.models import VideoRecord
from app.ai.manager import AIBackendManager


class VideoProcessor:
    def __init__(self, ai_manager: AIBackendManager):
        self.ai_manager = ai_manager
        self.whisper_model = None
        self.backend = None

        if FASTER_OK:
            size = getattr(Config, "WHISPER_MODEL_SIZE", "base")
            if not os.path.isdir("/home/vineetmishra89/lms-portal/model-service/models/faster-whisper-base"):
                print(f"path does not exist")
            # good defaults for CPU; tweak if you want
            self.whisper_model = WhisperModel(
                model_size_or_path="/home/vineetmishra89/lms-portal/model-service/models/faster-whisper-base",
                device="cpu", compute_type="int8", local_files_only=True)
            self.backend = "faster-whisper"
            print(f"✅ Whisper model loaded (faster-whisper: {size})")
        elif WHISPER_OG_OK:
            size = getattr(Config, "WHISPER_MODEL_SIZE", "base")
            self.whisper_model = whisper_og.load_model(size)
            self.backend = "openai-whisper"
            print(f"✅ Whisper model loaded (openai-whisper: {size})")
        else:
            print("⚠️  No Whisper backend available")

    def extract_duration(self, video_path: str) -> float:
        try:
            with mp.VideoFileClip(video_path) as video:
                return float(video.duration or 0.0)
        except Exception as e:
            print(f"Error extracting duration: {e}")
            return 0.0

    def extract_audio(self, video_path: str, video_duration: int) -> Optional[str]:
        try:
            with mp.VideoFileClip(video_path) as video:
                if not video.audio:
                    return None

                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                    path = tmp.name

                # Simplified approach: extract audio directly from segments without video concatenation
                if video_duration > 600:  # If video is longer than 10 minutes
                    print(f"Long video detected. Extracting key segments for better topic coverage.")

                    # Extract audio segments directly
                    audio_segments = []
                    segment_duration = 60  # 1 minute segments

                    # Beginning (first minute)
                    start_audio = video.subclip(0, min(segment_duration, video_duration)).audio
                    if start_audio:
                        audio_segments.append(start_audio)

                    # Middle segment
                    if video_duration > 180:
                        mid_start = video_duration // 2 - segment_duration // 2
                        mid_end = mid_start + segment_duration
                        mid_audio = video.subclip(mid_start, min(mid_end, video_duration)).audio
                        if mid_audio:
                            audio_segments.append(mid_audio)

                    # End segment (last minute)
                    if video_duration > 120:
                        end_start = max(video_duration - segment_duration, 120)
                        end_audio = video.subclip(end_start, video_duration).audio
                        if end_audio:
                            audio_segments.append(end_audio)

                    # Concatenate audio clips directly
                    if audio_segments:
                        composite_audio = mp.concatenate_audioclips(audio_segments)
                        composite_audio.write_audiofile(
                            path,
                            verbose=False,
                            logger=None,
                            bitrate="192k",
                            ffmpeg_params=["-ac", "1"]
                        )
                        # Clean up
                        composite_audio.close()
                        for segment in audio_segments:
                            segment.close()
                    else:
                        return None

                elif video_duration > 300:  # 5-10 minutes
                    print(f"Medium video detected. Using first 3 minutes for analysis.")
                    audio_clip = video.subclip(0, 180).audio
                    audio_clip.write_audiofile(
                        path,
                        verbose=False,
                        logger=None,
                        bitrate="192k",
                        ffmpeg_params=["-ac", "1"]
                    )
                    audio_clip.close()
                else:
                    # Short video - use full audio
                    video.audio.write_audiofile(
                        path,
                        verbose=False,
                        logger=None,
                        bitrate="192k",
                        ffmpeg_params=["-ac", "1"]
                    )

                return path
        except Exception as e:
            print(f"Error extracting audio: {e}")
            return None

    # make transcribe_audio async and handle both backends
    def transcribe_audio(self, audio_path: str) -> str:
        if not self.whisper_model:
            return ""
        try:
            if self.backend == "faster-whisper":
                # returns generator of segments + info; run in a thread
                segments, _info = self.whisper_model.transcribe(audio_path)
                text = "".join(seg.text for seg in segments)
                return text.strip()
            else:
                result = self.whisper_model.transcribe(audio_path)
                return result.get("text", "").strip()
        except Exception as e:
            print(f"Error in transcription: {e}")
            return ""

    async def process_video(self, video_path: str, job_id: str, db: Session) -> Dict[str, Any]:
        filename = os.path.basename(video_path)
        video_record = db.query(VideoRecord).filter(
            VideoRecord.job_id == job_id,
            VideoRecord.file_path == video_path
        ).first()

        if video_record:
            video_record.processing_status = 'processing'
            db.commit()

        try:
            duration = self.extract_duration(video_path)
            transcript = ""
            audio_path = self.extract_audio(video_path, duration)
            if audio_path:
                transcript = await self.transcribe_audio(audio_path)
                try:
                    os.unlink(audio_path)
                except:
                    pass

            analysis = await self.ai_manager.analyze_content(transcript, filename)
            result = {
                "filename": filename,
                "duration": duration,
                "transcript": transcript,
                "instructor_name": analysis.get("instructor_name"),
                "training_content": analysis.get("training_content"),
                "category": analysis.get("category"),
                "confidence_score": analysis.get("confidence_score", 0.0),
                "extraction_method": analysis.get("extraction_method")
            }

            if video_record:
                video_record.duration = duration
                video_record.instructor_name = result["instructor_name"]
                video_record.category = result["category"]
                video_record.training_content = result["training_content"]
                video_record.transcript = transcript
                video_record.confidence_score = result["confidence_score"]
                video_record.extraction_method = result["extraction_method"]
                video_record.processing_status = 'completed'
                video_record.completed_at = datetime.utcnow()
                db.commit()

            return result

        except Exception as e:
            if video_record:
                video_record.processing_status = 'failed'
                video_record.error_message = str(e)
                db.commit()
            raise

    def process_file(self, video_path: str) -> Dict[str, Any]:
        filename = os.path.basename(video_path)
        try:
            duration = self.extract_duration(video_path)
            transcript = ""
            audio_path = self.extract_audio(video_path, duration)
            if audio_path:
                transcript = self.transcribe_audio(audio_path)
                try:
                    os.unlink(audio_path)
                except:
                    pass

            analysis = self.ai_manager.analyze_content(transcript, filename)
            # audio_instrcutor = {"name":analysis.get("instructor_name"), "confidence": analysis.get("confidence_score", 0.0), "source": "audio"}
            # slide_instructor = extract_instructor_from_slides(video_path)
            # instructor = choose_instructor(audio_instrcutor,slide_instructor)
            result = {
                "filename": filename,
                "duration": duration,
                "transcript": transcript,
                "instructorName": analysis.get("instructor_name"),
                "moduleTopic": analysis.get("training_content"),
                "trainingTopic": "",
                "category": analysis.get("category"),
                "confidence_score": analysis.get("confidence_score", 0.0),
                "extraction_method": analysis.get("extraction_method")
            }
            return result
        except Exception as e:
            raise
