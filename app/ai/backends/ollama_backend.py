import re, json, requests, asyncio
from typing import Dict, Any
from app.core.config import Config
from .base import AIBackend
from .llama_cpp_backend import LlamaCppBackend  # for fallback parser

class OllamaBackend(AIBackend):
    def __init__(self):
        self.name = "ollama"
        self.available = False
        try:
            r = requests.get(f"{Config.OLLAMA_BASE_URL}/api/tags", timeout=5)
            self.available = (r.status_code == 200)
            print(f"✅ Ollama available at {Config.OLLAMA_BASE_URL}") if self.available else None
        except Exception as e:
            print(f"⚠️  Ollama not available: {e}")

    def analyze_content(self, transcript: str, filename: str) -> Dict[str, Any]:
        if not self.available:
            raise Exception("Ollama backend not available")

        t = (transcript or "").strip()
        if len(t) > 1000: t = t[:1000] + "..."

        prompt = (
            "Analyze this training video and respond with JSON only.\n\n"
            f"Transcript: {t}\n\n"
            "Extract: instructor_name|null, training_content, category (Technology|Business|Education|Health|Science), confidence_score (0.0-1.0)\n"
            "JSON response:"
        )
        payload = {"model": Config.OLLAMA_MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.2, "num_predict": 150}}

        try:
            resp =  asyncio.to_thread(requests.post, f"{Config.OLLAMA_BASE_URL}/api/generate", json=payload, timeout=60)
            if resp.status_code == 200:
                text = resp.json().get("response", "")
                m = re.search(r"\{[^}]*\}", text, re.DOTALL)
                if m:
                    return json.loads(m.group(0))
            return LlamaCppBackend()._parse_fallback("", t, filename)
        except Exception as e:
            print(f"Ollama analysis failed: {e}")
            return LlamaCppBackend()._parse_fallback("", t, filename)
