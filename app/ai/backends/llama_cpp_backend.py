import os, json, re, asyncio
from typing import Dict, Any
from app.core.config import Config
from .base import AIBackend

try:
    from llama_cpp import Llama
    LLAMA_OK = True
except Exception:
    LLAMA_OK = False

SYSTEM_PROMPT = (
    "You are a precise analyzer for training videos. "
    "Return STRICT JSON only with keys: instructor_name (string|null), "
    "training_content (string), category (Technology|Business|Education|Health|Science|Unknown), "
    "confidence_score (0.0-1.0). No extra text."
)

def _strip_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    return text

class LlamaCppBackend(AIBackend):
    def __init__(self):
        self.name = "llama-cpp"
        self.llm = None
        if LLAMA_OK and os.path.exists(Config.LLAMA_MODEL_PATH):
            try:
                self.llm = Llama(
                    model_path=Config.LLAMA_MODEL_PATH,
                    n_ctx=Config.LLAMA_N_CTX,
                    n_threads=Config.LLAMA_N_THREADS,
                    chat_format=Config.LLAMA_CHAT_FORMAT,
                    verbose=False
                )
                self.available = True
                print(f"✅ Llama-cpp loaded: {Config.LLAMA_MODEL_PATH}")
            except Exception as e:
                print(f"❌ Failed to load llama-cpp model: {e}")
        else:
            print("⚠️  llama-cpp not available or model missing")

    def analyze_content(self, transcript: str, filename: str) -> Dict[str, Any]:
        if not self.available:
            raise Exception("Llama-cpp backend not available")

        t = (transcript or "").strip()
        if len(t) > 6000: t = t[:6000]

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

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt
              ##  f"Filename: {filename}\n\nTranscript:\n{t}\n\n"
               ## 'JSON format: {"instructor_name": null, "training_content": "", "category": "Unknown", "confidence_score": 0.0}'
            }
        ]

        try:
            out = self.llm.create_chat_completion(
                messages=messages, # type: ignore
                max_tokens=Config.LLAMA_MAX_TOKENS,
                temperature=Config.LLAMA_TEMPERATURE,
                top_p=Config.LLAMA_TOP_P
            )
            text = _strip_json(out["choices"][0]["message"]["content"])
            data = json.loads(text)
            return {
                "instructor_name": (data.get("instructor_name") or None) if isinstance(data.get("instructor_name"), str) else None,
                "training_content": str(data.get("training_content", ""))[:2000],
                "category": str(data.get("category", "Unknown"))[:50],
                "confidence_score": float(data.get("confidence_score", 0.3))
            }
        except Exception as e:
            print(f"Llama-cpp analysis failed: {e}")
            return self._parse_fallback("", t, filename)
