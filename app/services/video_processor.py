import os, tempfile, gc
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
        # Check file size limit (500MB threshold)
        file_size = os.path.getsize(video_path)
        if file_size > 500 * 1024 * 1024:  # 500MB
            print(f"Large file detected ({file_size / (1024 * 1024):.1f}MB). Using reduced sampling.")
            return self._extract_audio_large_file(video_path, video_duration)

        video = None
        audio_segments = []
        composite_audio = None

        try:
            # Use lower resolution for large videos to reduce memory usage
            if file_size > 200 * 1024 * 1024:  # 200MB+
                video = mp.VideoFileClip(video_path, audio_fps=16000, target_resolution=(480, None))
            else:
                video = mp.VideoFileClip(video_path)

            if not video.audio:
                return None

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                path = tmp.name

            # Simplified approach: extract audio directly from segments without video concatenation
            if video_duration > 600:  # If video is longer than 10 minutes
                print(f"Long video detected. Extracting key segments for better topic coverage.")

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
                        bitrate="128k",  # Reduced bitrate for large files
                        ffmpeg_params=["-ac", "1", "-ar", "16000"]  # Lower sample rate
                    )
                else:
                    return None

            elif video_duration > 300:  # 5-10 minutes
                print(f"Medium video detected. Using first 3 minutes for analysis.")
                audio_clip = video.subclip(0, 180).audio
                audio_clip.write_audiofile(
                    path,
                    verbose=False,
                    logger=None,
                    bitrate="128k",
                    ffmpeg_params=["-ac", "1", "-ar", "16000"]
                )
                audio_clip.close()
                del audio_clip
            else:
                # Short video - use full audio
                video.audio.write_audiofile(
                    path,
                    verbose=False,
                    logger=None,
                    bitrate="128k",
                    ffmpeg_params=["-ac", "1", "-ar", "16000"]
                )

            return path

        except Exception as e:
            print(f"Error extracting audio: {e}")
            return None
        finally:
            # Explicit cleanup in reverse order
            if composite_audio:
                composite_audio.close()
                del composite_audio

            for segment in audio_segments:
                try:
                    segment.close()
                except:
                    pass
            audio_segments.clear()

            if video:
                video.close()
                del video

            # Force garbage collection
            gc.collect()

    def _extract_audio_large_file(self, video_path: str, video_duration: int) -> Optional[str]:
        """Extract audio from very large files using minimal memory approach"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                path = tmp.name

            # For very large files, extract only the first 2 minutes using ffmpeg directly
            print(f"Using direct ffmpeg extraction for large file")

            # Use subprocess to call ffmpeg directly (more memory efficient)
            import subprocess
            cmd = [
                'ffmpeg', '-i', video_path,
                '-t', '120',  # First 2 minutes only
                '-vn',  # No video
                '-acodec', 'pcm_s16le',
                '-ar', '16000',  # 16kHz sample rate
                '-ac', '1',  # Mono
                '-y',  # Overwrite output
                path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5 min timeout

            if result.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 0:
                return path
            else:
                print(f"ffmpeg extraction failed: {result.stderr}")
                if os.path.exists(path):
                    os.unlink(path)
                return None

        except Exception as e:
            print(f"Error in large file extraction: {e}")
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
        file_size = os.path.getsize(video_path)

        video_record = db.query(VideoRecord).filter(
            VideoRecord.job_id == job_id,
            VideoRecord.file_path == video_path
        ).first()

        if video_record:
            video_record.processing_status = 'processing'
            db.commit()

        audio_path = None
        start_time = datetime.utcnow()

        try:
            print(f"Processing video: {filename} (Size: {file_size / (1024 * 1024):.1f}MB)")

            # Skip extremely large files
            if file_size > 1000 * 1024 * 1024:  # 1GB limit
                raise Exception(f"File too large ({file_size / (1024 * 1024):.1f}MB). Maximum supported size is 1GB.")

            duration = self.extract_duration(video_path)
            print(f"Video duration: {duration:.1f} seconds")

            transcript = ""

            # Add timeout for audio extraction
            try:
                audio_path = self.extract_audio(video_path, duration)
            except Exception as e:
                print(f"Audio extraction failed: {e}")
                audio_path = None

            if audio_path and os.path.exists(audio_path):
                try:
                    transcript = await self.transcribe_audio(audio_path)
                    print(f"Transcription completed: {len(transcript)} characters")
                except Exception as e:
                    print(f"Transcription failed: {e}")
                    transcript = ""
                finally:
                    # Clean up audio file immediately
                    try:
                        os.unlink(audio_path)
                        audio_path = None
                    except:
                        pass
            else:
                print("No audio extracted, using filename for analysis")

            analysis = await self.ai_manager.analyze_content(transcript, filename)

            processing_time = (datetime.utcnow() - start_time).total_seconds()
            print(f"Processing completed in {processing_time:.1f} seconds")

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

            print(f"Completed processing: {filename}")
            return result

        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            print(f"Error processing {filename} after {processing_time:.1f}s: {e}")
            if video_record:
                video_record.processing_status = 'failed'
                video_record.error_message = str(e)
                db.commit()
            raise
        finally:
            # Cleanup audio file if it still exists
            if audio_path and os.path.exists(audio_path):
                try:
                    os.unlink(audio_path)
                except:
                    pass

            # Force garbage collection after each video
            gc.collect()
            print(f"Memory cleanup completed for: {filename}")

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
                "category": analysis.get("category"),
                "confidence_score": analysis.get("confidence_score", 0.0),
                "extraction_method": analysis.get("extraction_method")
            }
            return result
        except Exception as e:
            raise
