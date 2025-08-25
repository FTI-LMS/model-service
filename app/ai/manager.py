from typing import Dict, Any, Optional
from app.core.config import Config
from .backends.llama_cpp_backend import LlamaCppBackend
from .backends.ollama_backend import OllamaBackend
from .backends.pattern_backend import PatternBackend
from app.services.content_analyzer import ContentAnalyzer

class AIBackendManager:
    def __init__(self):
        self.backends = [
            LlamaCppBackend(),
            OllamaBackend(),
            PatternBackend()
        ]
        self.active_backend = None
        self.content_analyzer = ContentAnalyzer()
        self._select_backend()

    def _select_backend(self):
        for backend in self.backends:
            if backend.available:
                self.active_backend = backend
                print(f"🤖 Using AI backend: {self.active_backend.name}")
                return
        if not self.active_backend:
            raise RuntimeError("No AI backend available")

    def analyze_content(self, transcript: str, filename: str) -> Dict[str, Any]:
        # First try AI backend
        if self.active_backend:
            try:
                result = self.active_backend.analyze_content(transcript, filename)
                result["extraction_method"] = self.active_backend.name

                # Enhance with content analyzer if AI results are poor
                if (not result.get("instructor_name") or
                    result.get("confidence_score", 0) < 0.3 or
                    len(result.get("training_content", "")) < 30):

                    enhanced_result = self._enhance_with_content_analyzer(transcript, filename, result)
                    return enhanced_result

                return result
            except Exception as e:
                print(f"AI analysis failed: {e}")

        # Fallback to content analyzer
        return self._fallback_analysis(transcript, filename)

    def _enhance_with_content_analyzer(self, transcript: str, filename: str, ai_result: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance AI results with content analyzer"""

        # Try to find instructor name if AI couldn't
        if not ai_result.get("instructor_name"):
            instructor_name = self.content_analyzer.extract_instructor_name(transcript)
            if instructor_name:
                ai_result["instructor_name"] = instructor_name
                ai_result["confidence_score"] = min(1.0, ai_result.get("confidence_score", 0) + 0.2)

        # Enhance training content if it's too brief
        current_content = ai_result.get("training_content", "")
        if len(current_content) < 100:
            comprehensive_topics = self.content_analyzer.extract_comprehensive_topics(transcript)
            if len(comprehensive_topics) > len(current_content):
                ai_result["training_content"] = comprehensive_topics
                ai_result["confidence_score"] = min(1.0, ai_result.get("confidence_score", 0) + 0.1)

        # Improve category detection
        if ai_result.get("category") == "Unknown":
            category = self.content_analyzer.detect_category(transcript, filename)
            if category != "Unknown":
                ai_result["category"] = category

        ai_result["extraction_method"] = f"{ai_result.get('extraction_method', 'unknown')}-enhanced"
        return ai_result

    def _fallback_analysis(self, transcript: str, filename: str) -> Dict[str, Any]:
        """Complete fallback analysis using content analyzer"""
        instructor_name = self.content_analyzer.extract_instructor_name(transcript)
        training_content = self.content_analyzer.extract_comprehensive_topics(transcript)
        category = self.content_analyzer.detect_category(transcript, filename)

        confidence = self.content_analyzer.calculate_confidence(
            instructor_found=bool(instructor_name),
            topics_extracted=bool(training_content and len(training_content) > 50),
            transcript_length=len(transcript)
        )

        return {
            "instructor_name": instructor_name,
            "training_content": training_content,
            "category": category,
            "confidence_score": confidence,
            "extraction_method": "content-analyzer-fallback"
        }