from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from statistics import median

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from vosk import KaldiRecognizer, Model

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
PRAAT_BINARY = shutil.which("praat") or "/usr/bin/praat"
PRAAT_SCRIPT = Path(__file__).with_name("praat_formants.praat")
VOSK_MODEL_PATH = Path(__file__).with_name("models") / "vosk-model-small-ko-0.22"
VOSK_MODEL = Model(str(VOSK_MODEL_PATH)) if VOSK_MODEL_PATH.exists() else None
VOSK_VOWELS = ["어", "오", "아", "으", "우", "이", "에", "[unk]"]
VOWEL_WORD_BY_JAMO = {"ㅓ": "어", "ㅗ": "오"}
VOWEL_JAMO_BY_WORD = {"어": "ㅓ", "오": "ㅗ", "아": "ㅏ", "으": "ㅡ", "우": "ㅜ", "이": "ㅣ", "에": "ㅔ"}
FORMANT_REFERENCE = {
    "male": {
        "ㅓ": {"f1": (521.4, 41.1), "f2": (903.7, 81.4)},
        "ㅗ": {"f1": (317.7, 38.7), "f2": (691.4, 103.6)},
    },
    "female": {
        "ㅓ": {"f1": (659.8, 90.4), "f2": (1182.7, 150.5)},
        "ㅗ": {"f1": (337.4, 41.9), "f2": (686.7, 104.3)},
    },
}

app = FastAPI(title="Gaga Korean Praat + Vosk API")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://gaga-korean(?:-[a-z0-9]+)?-eungdi\.vercel\.app|https://gaga-korean\.vercel\.app|https?://tauri\.localhost(?::\d+)?|http://127\.0\.0\.1(?::\d+)?|http://localhost(?::\d+)?",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _read_formant_rows(path: str) -> dict[str, int] | None:
    values: list[tuple[float, float, float]] = []
    tokens = Path(path).read_text(encoding="utf-8").split()
    for index in range(0, len(tokens) - 2, 3):
        try:
            row = tuple(float(value) for value in tokens[index:index + 3])
        except ValueError:
            continue
        if all(math.isfinite(value) and value > 0 for value in row):
            values.append(row)
    if not values:
        return None
    return {
        "f1": round(median(row[0] for row in values)),
        "f2": round(median(row[1] for row in values)),
        "f3": round(median(row[2] for row in values)),
    }

def _recognize_vowel(path: str, target: str) -> dict[str, object]:
    if VOSK_MODEL is None:
        return {
            "stt_available": False,
            "recognized_vowel": None,
            "stt_score": None,
            "stt_confidence": None,
        }
    with wave.open(path, "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            return {
                "stt_available": False,
                "recognized_vowel": None,
                "stt_score": None,
                "stt_confidence": None,
            }
        recognizer = KaldiRecognizer(
            VOSK_MODEL,
            source.getframerate(),
            json.dumps(VOSK_VOWELS, ensure_ascii=False),
        )
        recognizer.SetWords(True)
        while data := source.readframes(4000):
            recognizer.AcceptWaveform(data)
    result = json.loads(recognizer.FinalResult())
    recognized = "".join(result.get("text", "").split())
    recognized_vowel = VOWEL_JAMO_BY_WORD.get(recognized, recognized or None)
    words = result.get("result", [])
    confidences = [
        float(word["conf"])
        for word in words
        if math.isfinite(float(word.get("conf", 0)))
    ]
    confidence = sum(confidences) / len(confidences) if confidences else None
    target_match = VOWEL_WORD_BY_JAMO.get(target, target) in recognized
    score = None
    if confidence is not None:
        score = round(confidence * 100 if target_match else (1 - confidence) * 100)
    return {
        "stt_available": True,
        "recognized_vowel": recognized_vowel,
        "recognized_text": recognized or None,
        "stt_score": score,
        "stt_confidence": round(confidence, 3) if confidence is not None else None,
    }


def _score_formants(measured: dict[str, int], profile: str, vowel: str) -> int | None:
    reference = FORMANT_REFERENCE.get(profile, {}).get(vowel)
    if reference is None:
        return None
    distance = math.sqrt(sum(
        ((measured[key] - mean) / standard_deviation) ** 2
        for key, (mean, standard_deviation) in reference.items()
    ))
    return max(0, round(100 * math.exp(-0.25 * distance**2)))


def _combine_scores(acoustic_score: int | None, stt_score: int | None) -> dict[str, object]:
    weighted_scores = []
    if acoustic_score is not None:
        weighted_scores.append((acoustic_score, 0.65))
    if stt_score is not None:
        weighted_scores.append((stt_score, 0.35))
    if not weighted_scores:
        return {"combined_score": None, "verdict": "unavailable"}
    total_weight = sum(weight for _, weight in weighted_scores)
    combined = round(sum(score * weight for score, weight in weighted_scores) / total_weight)
    verdict = "good" if combined >= 75 else "near" if combined >= 55 else "needs-work"
    return {"combined_score": combined, "verdict": verdict}


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "analyzer": "praat+vosk-local" if VOSK_MODEL is not None else "praat",
        "stt_model": VOSK_MODEL_PATH.name if VOSK_MODEL is not None else None,
    }


@app.post("/analyze")
async def analyze_audio(
    audio: UploadFile = File(...),
    profile: str = "male",
    vowel: str = "ㅓ",
) -> dict[str, object]:
    if profile not in {"male", "female"}:
        raise HTTPException(status_code=400, detail="profile must be male or female")
    if vowel not in {"ㅓ", "ㅗ"}:
        raise HTTPException(status_code=400, detail="vowel must be ㅓ or ㅗ")

    payload = await audio.read()
    if not payload or len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="audio file is empty or too large")

    suffix = os.path.splitext(audio.filename or "recording.webm")[1] or ".webm"
    audio_path: str | None = None
    analysis_path: str | None = None
    recognition_path: str | None = None
    output_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as audio_file:
            audio_file.write(payload)
            audio_path = audio_file.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as analysis_file:
            analysis_path = analysis_file.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as recognition_file:
            recognition_path = recognition_file.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as output_file:
            output_path = output_file.name
        conversion = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", audio_path, "-ac", "1", "-ar", "48000", analysis_path],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if conversion.returncode != 0:
            raise HTTPException(status_code=422, detail="poor-audio-quality")
        recognition_conversion = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", audio_path, "-ac", "1", "-ar", "16000", recognition_path],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if recognition_conversion.returncode != 0:
            raise HTTPException(status_code=422, detail="poor-audio-quality")

        process = subprocess.run(
            [PRAAT_BINARY, "--run", "--utf8", str(PRAAT_SCRIPT), analysis_path, profile, output_path],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if process.returncode != 0:
            raise HTTPException(status_code=422, detail="formant-analysis-failed")
        measured = _read_formant_rows(output_path)
        if measured is None:
            raise HTTPException(status_code=422, detail="poor-audio-quality")

        stt = _recognize_vowel(recognition_path, vowel)
        acoustic_score = _score_formants(measured, profile, vowel)
        combined = _combine_scores(acoustic_score, stt["stt_score"])
        return {
            "analyzer": "praat+vosk-local",
            "profile": profile,
            "target_vowel": vowel,
            **measured,
            "acoustic_score": acoustic_score,
            **stt,
            **combined,
        }
    except subprocess.TimeoutExpired as error:
        raise HTTPException(status_code=504, detail="formant-analysis-failed") from error
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=422, detail="formant-analysis-failed") from error
    finally:
        for path in (audio_path, analysis_path, recognition_path, output_path):
            if path:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
