from __future__ import annotations

import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from .diarization_service import diarization_service


ALLOWED_SUFFIXES = {
    ".wav",
    ".flac",
    ".mp3",
    ".m4a",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading diarization model...")
    diarization_service.load()

    print(
        "Diarization model ready "
        f"on {diarization_service.device}"
    )

    yield


app = FastAPI(
    title="Audio Diarization Demo API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ready",
        "model_loaded": (
            diarization_service.pipeline is not None
        ),
        "device": str(diarization_service.device),
        "model_load_seconds": (
            round(
                diarization_service.load_seconds,
                3,
            )
            if diarization_service.load_seconds
            is not None
            else None
        ),
    }


@app.post("/diarize")
def diarize(
    audio: UploadFile = File(...),
) -> dict:
    filename = audio.filename or "audio.wav"

    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported audio format. "
                "Use WAV, FLAC, MP3, or M4A."
            ),
        )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:
            shutil.copyfileobj(
                audio.file,
                temp_file,
            )

            temp_path = Path(temp_file.name)

        result = diarization_service.diarize(
            temp_path
        )

        return {
            "filename": filename,
            **result,
        }

    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()
