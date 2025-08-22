from typing import List, Dict, Any
from app.core.config import Config
from .backends.llama_cpp_backend import LlamaCppBackend
from .backends.ollama_backend import OllamaBackend
from .backends.pattern_backend import PatternBackend

class AIBackendManager:
    def __init__(self):
        self.backends = []
        if Config.AI_BACKEND in ["auto", "llama-cpp"]:
            self.backends.append(LlamaCppBackend())
        if Config.AI_BACKEND in ["auto", "ollama"]:
            self.backends.append(OllamaBackend())
        self.backends.append(PatternBackend())

        self.current_backend = next((b for b in self.backends if b.available), None)
        if not self.current_backend:
            raise RuntimeError("No AI backend available")
        print(f"🤖 Using AI backend: {self.current_backend.name}")

    def analyze_content(self, transcript: str, filename: str) -> Dict[str, Any]:
        try:
            result = self.current_backend.analyze_content(transcript, filename)
            result["extraction_method"] = self.current_backend.name
            return result
        except Exception:
            for b in self.backends:
                if b is not self.current_backend and b.available:
                    try:
                        r = b.analyze_content(transcript, filename)
                        r["extraction_method"] = f"{b.name} (fallback)"
                        return r
                    except Exception:
                        continue
            # Final fallback
            r = PatternBackend().analyze_content(transcript, filename)
            r["extraction_method"] = "pattern-matching (final fallback)"
            return r
