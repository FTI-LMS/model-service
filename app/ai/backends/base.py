import re, json
from typing import Dict, Any

class AIBackend:
    name: str = "base"
    available: bool = False

    async def analyze_content(self, transcript: str, filename: str) -> Dict[str, Any]:
        raise NotImplementedError

    # Fallback parser from your code
    def _parse_fallback(self, response: str, transcript: str, filename: str) -> Dict[str, Any]:
        result = {
            "instructor_name": None,
            "training_content": f"Training content from {filename}",
            "category": "Unknown",
            "confidence_score": 0.3
        }
        if transcript:
            for pat in [r"I'm ([A-Z][a-z]+ [A-Z][a-z]+)", r"My name is ([A-Z][a-z]+ [A-Z][a-z]+)", r"This is ([A-Z][a-z]+ [A-Z][a-z]+)"]:
                m = re.search(pat, transcript)
                if m:
                    result["instructor_name"] = m.group(1)
                    result["confidence_score"] = 0.7
                    break

        keywords = {
            'Technology': ['python','programming','code','software','java','web','api'],
            'Business': ['management','leadership','marketing','sales','business'],
            'Education': ['teaching','learning','course','lesson','training'],
            'Health': ['health','medical','fitness','wellness'],
            'Science': ['research','science','biology','chemistry','physics']
        }
        low = f"{transcript} {filename}".lower()
        for cat, words in keywords.items():
            if any(k in low for k in words):
                result["category"] = cat
                result["confidence_score"] = min(0.8, result["confidence_score"] + 0.2)
                break
        return result
