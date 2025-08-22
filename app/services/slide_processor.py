import os, re, json, shutil, subprocess, tempfile

from collections import Counter

from typing import Dict, Any, List, Tuple

import easyocr

import spacy

# ---- reusable singletons (load once at import) ----

_EASYOCR = easyocr.Reader(['en'], gpu=False)  # set gpu=True if you have CUDA

_NLP = spacy.load("en_core_web_sm")

# Common slide phrases that precede names
_STOP_WORDS = {"participants", "attendees", "meeting", "chat", "reactions", "team", "teams", "recording", "agenda", "index", "copyright"}
_TITLE_HINTS = {"by", "presented by", "speaker", "instructor", "trainer", "host", "facilitator"}
_PREFIXES = [

    r"instructor", r"trainer", r"presenter", r"speaker", r"facilitator",

    r"author", r"mentor", r"coach", r"by", r"presented\s+by", r"Organized\s+by", r"Recorded\s+by"

]

_PREFIX_RE = re.compile(rf"\b({'|'.join(_PREFIXES)})\b[:\-]?\s+(.*)", re.I)

# Basic name candidate filter (keeps “Dr. Jane Doe”, drops ALL CAPS words etc.)

_NAME_RE = re.compile(r"\b(Dr\.|Prof\.|Mr\.|Ms\.)?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b")


def _run_ffmpeg_keyframes(video_path: str, out_dir: str, scene_thresh: float = 0.30, max_frames: int = 30) -> List[str]:
    """

    Extract visually-distinct frames (approx slide changes) with ffmpeg scene change filter.

    Returns a list of image paths (at most max_frames).

    """

    os.makedirs(out_dir, exist_ok=True)

    # select frames with scene change over threshold

    # %04d guarantees ordered names

    cmd = [

        "ffmpeg", "-y",

        "-ss", "0", "-t", "180",

        "-i", video_path,

        "-vf", f"select='gt(scene,{scene_thresh})',showinfo",

        "-vsync", "vfr", os.path.join(out_dir, "kf_%04d.jpg")

    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    frames = sorted([os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.endswith(".jpg")])

    return frames[:max_frames] if len(frames) > max_frames else frames


def _ocr_image_text(img_path: str) -> str:
    try:

        # detail=0 returns only strings; paragraph=True merges lines

        lines = _EASYOCR.readtext(img_path, detail=0, paragraph=True)

        txt =  "\n".join(lines)

        return re.sub(r"\s+", " ", txt).strip()

    except Exception:

        return ""


def _extract_names_from_text(txt: str) -> List[str]:
    """

    Combine lightweight heuristics + spaCy PERSON entities.

    """
    if not txt:
        return []

    low = txt.lower()
    if any(k in low for k in _STOP_WORDS):
        return []

    candidates: List[str] = []

    # 1) Look for “Presented by: …”, “Instructor: …”, etc.

    for line in txt.splitlines():

        m = _PREFIX_RE.search(line)

        if m:
            tail = m.group(2)

            candidates += _NAME_RE.findall(tail)

    # 2) Generic proper-name patterns anywhere

    candidates += _NAME_RE.findall(txt)

    # 3) spaCy NER

    doc = _NLP(txt)

    candidates += [ent.text for ent in doc.ents if ent.label_ == "PERSON"]

    # Normalise

    def clean(n: str) -> str:

        n = re.sub(r"\s+", " ", n.strip())
        if not n:
            return ""

        if any (sym in n for sym in ",/\\|@#:"):
            return ""
        parts = n.split()

        # drop single short tokens (e.g., “Johns” alone / or all Caps acronyms)

        if not(2 <= len(parts) <= 3):
            return ""

        # avoid obvious non-names

        if any(w.isupper() and len(w) > 3 for w in n.split()):
            return ""

        return n

    out = [clean(n) for n in candidates]

    return [n for n in out if n]

def _score_slide_name(name: str, slide_txt: str, from_top_band: bool) -> float:

    base = 0.45

    low = slide_txt.lower()

    if any(h in low for h in _TITLE_HINTS):

        base += 0.25

    words = name.split()

    if 2 <= len(words) <= 3:

        base += 0.10

    # if slide has many names, likely participants list

    if len(_NAME_RE.findall(slide_txt)) >= 3:

        base -= 0.15

    if from_top_band:

        base += 0.10

    return max(0.0, min(0.95, base))

# UPDATED: crop top band helper (focus on title/byline area)

def _crop_top_band(img_path: str, top_fraction: float = 0.35) -> str:

    try:

        from PIL import Image

    except Exception:

        return img_path  # no Pillow, skip cropping

    try:

        im = Image.open(img_path)

        w, h = im.size

        box = (0, 0, w, int(h * top_fraction))

        top = im.crop(box)

        out_path = img_path.replace(".jpg", "_top.jpg")

        top.save(out_path, quality=90)

        return out_path

    except Exception:

        return img_path

def extract_instructor_from_slides(video_path: str) -> Dict[str, Any]:

    """

    Returns: {"name": Optional[str], "confidence": float, "source": "slides", "samples": [("Name", score_avg), ...]}

    """

    tmp = tempfile.mkdtemp(prefix="vce_kf_")

    try:

        frames = _run_ffmpeg_keyframes(video_path, tmp, scene_thresh=0.30, max_frames=40)

        if not frames:

            return {"name": None, "confidence": 0.0, "source": "slides", "samples": []}



        # UPDATED: keep score list instead of raw counts

        score_map: Dict[str, List[float]] = {}



        for fp in frames:

            # crop to the top band before OCR (focus on title/byline area)

            top_fp = _crop_top_band(fp, top_fraction=0.35)

            txt = _ocr_image_text(top_fp) or _ocr_image_text(fp)

            if not txt:

                continue



            names = _extract_names_from_text(txt)

            if not names:

                continue



            # score each candidate on this frame and accumulate

            for n in names:

                sc = _score_slide_name(n, txt, from_top_band=(top_fp != fp))

                score_map.setdefault(n, []).append(sc)



        if not score_map:

            return {"name": None, "confidence": 0.0, "source": "slides", "samples": []}



        # average scores per candidate and pick the best

        avg_scores = {n: (sum(v) / len(v)) for n, v in score_map.items()}

        best = max(avg_scores.items(), key=lambda kv: kv[1])

        best_name, best_conf = best[0], best[1]



        # top 5 for debug

        top5 = sorted(avg_scores.items(), key=lambda kv: kv[1], reverse=True)[:5]



        return {

            "name": best_name,

            "confidence": round(best_conf, 3),

            "source": "slides",

            "samples": [(n, round(s, 3)) for n, s in top5]

        }

    finally:

        shutil.rmtree(tmp, ignore_errors=True)



# ---------- Example fusion with your existing audio transcript path ----------



# UPDATED: treat “not provided/unknown/empty” as missing, allow slide override when stronger

def choose_instructor(audio_guess: Dict[str, Any] | None,

                      slide_guess: Dict[str, Any] | None) -> Dict[str, Any]:

    """

    audio_guess: {"name": str|None, "confidence": float, "source": "audio"}

    slide_guess: {"name": str|None, "confidence": float, "source": "slides"}

    Picks the better one; if both agree, boosts confidence.

    """

    a = audio_guess or {"name": None, "confidence": 0.0, "source": "audio"}

    s = slide_guess or {"name": None, "confidence": 0.0, "source": "slides"}



    def _missing(n: Any) -> bool:

        return (n is None) or (isinstance(n, str) and n.strip().lower() in {"", "not provided", "unknown", "n/a"})



    # if both present and same -> boost

    if not _missing(a["name"]) and not _missing(s["name"]):

        if str(a["name"]).lower() == str(s["name"]).lower():

            return {

                "name": a["name"],

                "confidence": round(min(0.99, (float(a["confidence"]) + float(s["confidence"])) / 2 + 0.15), 3),

                "source": "audio+slides"

            }

        # disagree: choose the higher confidence, but allow slide to override if clearly stronger

        if float(s["confidence"]) >= float(a["confidence"]) + 0.20:

            return s

        return a if float(a["confidence"]) >= float(s["confidence"]) else s



    # audio strong and not missing -> prefer audio

    if not _missing(a["name"]) and float(a["confidence"]) >= 0.55:

        # slide can override only if much stronger

        if not _missing(s["name"]) and float(s["confidence"]) >= float(a["confidence"]) + 0.20:

            return s

        return a



    # audio missing/weak -> consider slide if reasonable

    if not _missing(s["name"]) and float(s["confidence"]) >= 0.55:

        return s



    # fallback: whichever is non-missing with higher conf (or None with max conf)

    return a if float(a["confidence"]) >= float(s["confidence"]) else s
