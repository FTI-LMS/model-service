from typing import Dict, Any
from .base import AIBackend
from .llama_cpp_backend import LlamaCppBackend

class PatternBackend(AIBackend):
    def __init__(self):
        self.name = "pattern-matching"
        self.available = True

    async def analyze_content(self, transcript: str, filename: str) -> Dict[str, Any]:
        return LlamaCppBackend()._parse_fallback("", transcript, filename)
