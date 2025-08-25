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

        prompt = f"""Analyze this training video transcript and extract specific training topics and concepts.

FOCUS ON IDENTIFYING SPECIFIC TOPICS, NOT TRANSCRIPT SUMMARY:

For training_content, identify SPECIFIC topics being taught such as:
- Technical concepts (e.g., "Java Multithreading", "Spring Framework", "Database Optimization")
- Business skills (e.g., "Client Communication", "Project Management", "Stakeholder Engagement")  
- Soft skills (e.g., "Team Leadership", "Problem Resolution", "Presentation Skills")
- Methodologies (e.g., "Agile Development", "Role-playing Techniques", "Assessment Methods")

Return ONLY a valid JSON object with these exact fields:
- instructor_name: full name if mentioned, otherwise null
- training_content: specific topics and concepts being taught (NOT transcript summary)
- category: one of (Technology, Business, Education, Health, Science, Unknown)
- confidence_score: number between 0.0 and 1.0

Transcript: {t[:800]}

JSON response:"""

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
            return self._enhanced_fallback_analysis(t, filename)

    def _extract_topics_from_transcript(self, transcript: str) -> str:
        """Extract topics using keyword analysis when AI fails"""
        if not transcript:
            return "No content available for analysis"

        # Common topic indicators
        topic_keywords = [
            "learn", "understand", "explain", "discuss", "cover", "topic", "subject",
            "introduction", "overview", "concept", "method", "technique", "process",
            "algorithm", "function", "class", "module", "framework", "library",
            "database", "API", "security", "testing", "deployment", "development"
        ]

        # Split transcript into sentences
        sentences = re.split(r'[.!?]+', transcript)
        topics = []

        for sentence in sentences[:20]:  # Analyze first 20 sentences
            sentence = sentence.strip().lower()
            if any(keyword in sentence for keyword in topic_keywords):
                # Extract potential topic phrases
                words = sentence.split()
                for i, word in enumerate(words):
                    if word in topic_keywords and i < len(words) - 2:
                        topic_phrase = " ".join(words[i:i+3])
                        topics.append(topic_phrase)

        if topics:
            return f"Topics identified: {', '.join(set(topics[:10]))}"
        else:
            return "General training content - specific topics could not be automatically extracted"

    def _enhanced_fallback_analysis(self, transcript: str, filename: str) -> Dict[str, Any]:
        """Enhanced fallback analysis with pattern matching"""
        result = {
            "instructor_name": None,
            "training_content": self._extract_topics_from_transcript(transcript),
            "category": "Unknown",
            "confidence_score": 0.5,  # Start with better base score
            "extraction_method": "pattern-fallback"
        }

        # Enhanced instructor name patterns
        instructor_patterns = [
            r"(?:I'm|I am|My name is|This is|Hello,? I'm|Hi,? I'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            r"Welcome.*?(?:I'm|I am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            r"(?:taught by|instructor|teacher|presenter).*?([A-Z][a-z]+\s+[A-Z][a-z]+)",
            r"([A-Z][a-z]+\s+[A-Z][a-z]+).*?(?:will be|am)\s+(?:teaching|presenting|leading)"
        ]

        for pattern in instructor_patterns:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name.split()) >= 2 and len(name) < 50:
                    result["instructor_name"] = name
                    result["confidence_score"] = 0.7  # Higher confidence for pattern match
                    break

        # Category detection from filename and content
        filename_lower = filename.lower()
        transcript_lower = transcript.lower()

        category_keywords = {
            "Technology": ["python", "javascript", "programming", "code", "software", "development", "api", "database"],
            "Business": ["management", "leadership", "sales", "marketing", "finance", "strategy", "business"],
            "Behaviour": ["teaching", "learning", "education", "academic", "curriculum", "student"]
        }

        for category, keywords in category_keywords.items():
            if any(keyword in filename_lower or keyword in transcript_lower for keyword in keywords):
                result["category"] = category
                break

        return result