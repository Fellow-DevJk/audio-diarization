from __future__ import annotations

import json
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    version="0.2.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def run_diarization_from_path(
    audio_path: Path,
    filename: str,
) -> dict:
    result = diarization_service.diarize(
        audio_path
    )

    return {
        "filename": filename,
        **result,
    }


@app.get("/health")
def health() -> dict:
    return {
        "status": "ready",
        "model_loaded": (
            diarization_service.pipeline
            is not None
        ),
        "device": str(
            diarization_service.device
        ),
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
    """
    Local/browser API.

    Accepts multipart/form-data uploads.
    """

    filename = (
        audio.filename
        or "audio.wav"
    )

    suffix = (
        Path(filename)
        .suffix
        .lower()
    )

    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported audio format. "
                "Use WAV, FLAC, MP3, or M4A."
            ),
        )

    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:
            shutil.copyfileobj(
                audio.file,
                temp_file,
            )

            temp_path = Path(
                temp_file.name
            )

        return run_diarization_from_path(
            temp_path,
            filename,
        )

    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()


@app.api_route(
    "/ping",
    methods=["GET", "POST"],
)
def ping() -> Response:
    """
    SageMaker health endpoint.
    """

    if (
        diarization_service.pipeline
        is None
    ):
        return Response(
            status_code=503
        )

    return Response(
        status_code=200
    )


@app.post("/invocations")
async def invocations(
    request: Request,
) -> JSONResponse:
    """
    SageMaker inference endpoint.

    SageMaker passes the request payload
    directly to the container.

    For this demo, the payload is expected
    to contain raw audio bytes.
    """

    content_type = (
        request.headers
        .get(
            "content-type",
            "application/octet-stream",
        )
        .split(";")[0]
        .strip()
        .lower()
    )

    suffix_map = {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/wave": ".wav",
        "audio/flac": ".flac",
        "audio/x-flac": ".flac",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
        "application/octet-stream": ".wav",
    }

    suffix = suffix_map.get(
        content_type
    )

    if suffix is None:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported Content-Type: "
                f"{content_type}"
            ),
        )

    body = await request.body()

    if not body:
        raise HTTPException(
            status_code=400,
            detail="Empty request body.",
        )

    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_file.write(body)

            temp_path = Path(
                temp_file.name
            )

        result = (
            run_diarization_from_path(
                temp_path,
                f"input{suffix}",
            )
        )

        return JSONResponse(
            content=result,
            status_code=200,
        )

    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()