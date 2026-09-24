from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from statistics import median

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
PRAAT_BINARY = shutil.which("praat") or "/usr/bin/praat"
PRAAT_SCRIPT = Path(__file__).with_name("praat_formants.praat")

app = FastAPI(title="Gaga Korean Praat Formant API")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://gaga-korean(?:-[a-z0-9]+)?-eungdi\.vercel\.app|https://gaga-korean\.vercel\.app|http://127\.0\.0\.1(?::\d+)?|http://localhost(?::\d+)?",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _read_formant_rows(path: str) -> dict[str, int] | None:
    values: list[tuple[float, float, float]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            row = tuple(float(value) for value in parts[:3])
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "analyzer": "praat"}


@app.post("/analyze")
async def analyze_audio(audio: UploadFile = File(...), profile: str = "male") -> dict[str, object]:
    if profile not in {"male", "female"}:
        raise HTTPException(status_code=400, detail="profile must be male or female")

    payload = await audio.read()
    if not payload or len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="audio file is empty or too large")

    suffix = os.path.splitext(audio.filename or "recording.webm")[1] or ".webm"
    audio_path: str | None = None
    analysis_path: str | None = None
    output_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as audio_file:
            audio_file.write(payload)
            audio_path = audio_file.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as analysis_file:
            analysis_path = analysis_file.name
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
        return {"analyzer": "praat", "profile": profile, **measured}
    except subprocess.TimeoutExpired as error:
        raise HTTPException(status_code=504, detail="formant-analysis-failed") from error
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=422, detail="formant-analysis-failed") from error
    finally:
        for path in (audio_path, analysis_path, output_path):
            if path:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
