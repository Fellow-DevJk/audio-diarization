from __future__ import annotations

import json
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)
from fastapi.responses import JSONResponse

from .diarization_service import (
    diarization_service,
)
from .s3_audio import (
    download_audio,
    parse_s3_uri,
)
from .speaker_verification_service import (
    DEFAULT_THRESHOLD,
    speaker_verification_service,
)


ALLOWED_SUFFIXES = {
    ".wav",
    ".flac",
    ".mp3",
    ".m4a",
}


# ============================================================
# APPLICATION STARTUP
# ============================================================


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    """
    Diarization remains the primary capability.

    If Pyannote cannot load, application startup
    fails.

    Speaker verification is additive for now.
    If ECAPA cannot load, existing diarization
    remains available.
    """

    print(
        "Loading diarization model..."
    )

    diarization_service.load()

    print(
        "Diarization model ready "
        f"on {diarization_service.device}"
    )

    print(
        "Loading speaker verification model..."
    )

    try:
        speaker_verification_service.load()

        print(
            "Speaker verification model "
            "ready on "
            f"{speaker_verification_service.device}"
        )

    except Exception as exc:
        print(
            "Speaker verification model "
            "failed to load."
        )

        print(
            f"Error: {exc}"
        )

    yield


app = FastAPI(
    title="Audio Diarization Demo API",
    version="0.4.0",
    lifespan=lifespan,
)


# ============================================================
# CORS
# ============================================================


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
    ],
    allow_headers=["*"],
)


# ============================================================
# SHARED HELPERS
# ============================================================


def _validate_suffix(
    filename: str,
) -> str:
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

    return suffix


def _save_upload_to_temp(
    upload: UploadFile,
) -> Path:
    filename = (
        upload.filename
        or "audio.wav"
    )

    suffix = _validate_suffix(
        filename
    )

    with tempfile.NamedTemporaryFile(
        suffix=suffix,
        delete=False,
    ) as temp_file:
        shutil.copyfileobj(
            upload.file,
            temp_file,
        )

        temp_path = Path(
            temp_file.name
        )

    return temp_path


def _parse_json_list(
    raw_value: str,
    field_name: str,
) -> list[dict]:
    try:
        value = json.loads(
            raw_value
        )

    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{field_name} must contain "
                "valid JSON."
            ),
        ) from exc

    return _validate_dict_list(
        value,
        field_name,
    )


def _validate_dict_list(
    value,
    field_name: str,
) -> list[dict]:
    if not isinstance(
        value,
        list,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{field_name} must be "
                "a JSON array."
            ),
        )

    if not all(
        isinstance(
            item,
            dict,
        )
        for item in value
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Every item in "
                f"{field_name} must be "
                "a JSON object."
            ),
        )

    return value


def _resolve_selected_speaker(
    requested_speaker: str | None,
    segments: list[dict],
) -> str:
    detected_speakers = sorted(
        {
            str(
                segment.get(
                    "speaker",
                    "",
                )
            ).strip()
            for segment in segments
            if str(
                segment.get(
                    "speaker",
                    "",
                )
            ).strip()
        }
    )

    if not detected_speakers:
        raise HTTPException(
            status_code=400,
            detail=(
                "No speaker labels were found "
                "in the supplied diarization "
                "segments."
            ),
        )

    if requested_speaker:
        selected = (
            requested_speaker.strip()
        )

        if (
            selected
            not in detected_speakers
        ):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "The requested speaker "
                        "is not present in the "
                        "supplied diarization "
                        "segments."
                    ),
                    "requested_speaker": (
                        selected
                    ),
                    "available_speakers": (
                        detected_speakers
                    ),
                },
            )

        return selected

    # Single-speaker recordings automatically
    # become the simple two-file comparison case.
    if len(
        detected_speakers
    ) == 1:
        return detected_speakers[0]

    raise HTTPException(
        status_code=400,
        detail={
            "message": (
                "Multiple speakers were "
                "detected. Select the speaker "
                "to compare."
            ),
            "available_speakers": (
                detected_speakers
            ),
        },
    )


def run_diarization_from_path(
    audio_path: Path,
    filename: str,
) -> dict:
    result = (
        diarization_service.diarize(
            audio_path
        )
    )

    return {
        "filename": filename,
        **result,
    }


def run_verification_manifest(
    payload: dict,
) -> dict:
    """
    Run selected-speaker verification from
    a SageMaker JSON manifest.

    Audio objects remain in S3. The container
    downloads them using the SageMaker
    execution environment credentials.
    """

    if (
        speaker_verification_service.model
        is None
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "Speaker verification model "
                "is not available."
            ),
        )

    mode = str(
        payload.get(
            "mode",
            "",
        )
    ).strip()

    if (
        mode
        != "speaker_verification"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported JSON inference "
                f"mode: {mode!r}"
            ),
        )

    source_location = str(
        payload.get(
            "source_location",
            "",
        )
    ).strip()

    reference_location = str(
        payload.get(
            "reference_location",
            "",
        )
    ).strip()

    if not source_location:
        raise HTTPException(
            status_code=400,
            detail=(
                "source_location is required."
            ),
        )

    if not reference_location:
        raise HTTPException(
            status_code=400,
            detail=(
                "reference_location is required."
            ),
        )

    # Validate URI structure before downloading.
    try:
        (
            source_bucket,
            source_key,
        ) = parse_s3_uri(
            source_location
        )

        (
            reference_bucket,
            reference_key,
        ) = parse_s3_uri(
            reference_location
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    segments = (
        _validate_dict_list(
            payload.get(
                "segments",
            ),
            "segments",
        )
    )

    overlaps = (
        _validate_dict_list(
            payload.get(
                "overlaps",
                [],
            ),
            "overlaps",
        )
    )

    raw_speaker = (
        payload.get(
            "speaker"
        )
    )

    requested_speaker = (
        str(raw_speaker)
        if raw_speaker is not None
        else None
    )

    selected_speaker = (
        _resolve_selected_speaker(
            requested_speaker,
            segments,
        )
    )

    try:
        threshold = float(
            payload.get(
                "threshold",
                DEFAULT_THRESHOLD,
            )
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "threshold must be numeric."
            ),
        ) from exc

    source_path: Path | None = None
    reference_path: Path | None = None

    try:
        source_path = download_audio(
            source_location
        )

        reference_path = (
            download_audio(
                reference_location
            )
        )

        try:
            result = (
                speaker_verification_service
                .compare_selected_speaker(
                    source_audio=(
                        source_path
                    ),
                    reference_audio=(
                        reference_path
                    ),
                    segments=segments,
                    overlaps=overlaps,
                    speaker=(
                        selected_speaker
                    ),
                    threshold=threshold,
                )
            )

        except (
            ValueError,
            FileNotFoundError,
        ) as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        return {
            **result,

            "source_filename": (
                Path(
                    source_key
                ).name
            ),

            "reference_filename": (
                Path(
                    reference_key
                ).name
            ),

            "source_location": (
                f"s3://"
                f"{source_bucket}/"
                f"{source_key}"
            ),

            "reference_location": (
                f"s3://"
                f"{reference_bucket}/"
                f"{reference_key}"
            ),
        }

    finally:
        for path in (
            source_path,
            reference_path,
        ):
            if (
                path is not None
                and path.exists()
            ):
                path.unlink()


# ============================================================
# HEALTH
# ============================================================


@app.get("/health")
def health() -> dict:
    diarization_loaded = (
        diarization_service.pipeline
        is not None
    )

    verification_loaded = (
        speaker_verification_service.model
        is not None
    )

    return {
        # Existing contract.
        "status": "ready",

        "model_loaded": (
            diarization_loaded
        ),

        "device": str(
            diarization_service.device
        ),

        "model_load_seconds": (
            round(
                diarization_service
                .load_seconds,
                3,
            )
            if (
                diarization_service
                .load_seconds
                is not None
            )
            else None
        ),

        # Additive verification information.
        "diarization_model_loaded": (
            diarization_loaded
        ),

        "speaker_verification_model_loaded": (
            verification_loaded
        ),

        "speaker_verification_device": (
            speaker_verification_service
            .device
        ),

        "speaker_verification_model_load_seconds": (
            round(
                speaker_verification_service
                .load_seconds,
                3,
            )
            if (
                speaker_verification_service
                .load_seconds
                is not None
            )
            else None
        ),
    }


# ============================================================
# LOCAL DIARIZATION API
# ============================================================


@app.post("/diarize")
def diarize(
    audio: UploadFile = File(...),
) -> dict:
    filename = (
        audio.filename
        or "audio.wav"
    )

    temp_path: Path | None = None

    try:
        temp_path = (
            _save_upload_to_temp(
                audio
            )
        )

        return (
            run_diarization_from_path(
                temp_path,
                filename,
            )
        )

    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()


# ============================================================
# LOCAL SELECTED-SPEAKER VERIFICATION API
# ============================================================


@app.post("/verify-speaker")
def verify_speaker(
    source_audio: UploadFile = File(...),
    reference_audio: UploadFile = File(...),

    segments: str = Form(...),
    overlaps: str = Form("[]"),

    speaker: str | None = Form(
        None
    ),

    threshold: float = Form(
        DEFAULT_THRESHOLD
    ),
) -> dict:
    if (
        speaker_verification_service.model
        is None
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "Speaker verification model "
                "is not available."
            ),
        )

    parsed_segments = (
        _parse_json_list(
            segments,
            "segments",
        )
    )

    parsed_overlaps = (
        _parse_json_list(
            overlaps,
            "overlaps",
        )
    )

    selected_speaker = (
        _resolve_selected_speaker(
            speaker,
            parsed_segments,
        )
    )

    source_path: Path | None = None
    reference_path: Path | None = None

    try:
        source_path = (
            _save_upload_to_temp(
                source_audio
            )
        )

        reference_path = (
            _save_upload_to_temp(
                reference_audio
            )
        )

        try:
            result = (
                speaker_verification_service
                .compare_selected_speaker(
                    source_audio=(
                        source_path
                    ),
                    reference_audio=(
                        reference_path
                    ),
                    segments=(
                        parsed_segments
                    ),
                    overlaps=(
                        parsed_overlaps
                    ),
                    speaker=(
                        selected_speaker
                    ),
                    threshold=threshold,
                )
            )

        except (
            ValueError,
            FileNotFoundError,
        ) as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        return {
            **result,

            "source_filename": (
                source_audio.filename
                or "source_audio"
            ),

            "reference_filename": (
                reference_audio.filename
                or "reference_audio"
            ),
        }

    finally:
        for path in (
            source_path,
            reference_path,
        ):
            if (
                path is not None
                and path.exists()
            ):
                path.unlink()


# ============================================================
# SAGEMAKER HEALTH ENDPOINT
# ============================================================


@app.api_route(
    "/ping",
    methods=[
        "GET",
        "POST",
    ],
)
def ping() -> Response:
    """
    Preserve the existing SageMaker health
    contract.

    Production health currently depends on
    the diarization model only.
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


# ============================================================
# SAGEMAKER INFERENCE
# ============================================================


@app.post("/invocations")
async def invocations(
    request: Request,
) -> JSONResponse:
    """
    SageMaker inference endpoint.

    Two request contracts are supported:

    1. audio/*
       Existing raw-audio diarization.

    2. application/json
       Selected-speaker verification manifest.
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

    body = await request.body()

    if not body:
        raise HTTPException(
            status_code=400,
            detail="Empty request body.",
        )

    # --------------------------------------------------------
    # JSON: selected-speaker verification
    # --------------------------------------------------------

    if (
        content_type
        == "application/json"
    ):
        try:
            payload = json.loads(
                body.decode(
                    "utf-8"
                )
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid JSON inference "
                    "payload."
                ),
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "JSON inference payload "
                    "must be an object."
                ),
            )

        result = (
            run_verification_manifest(
                payload
            )
        )

        return JSONResponse(
            content=result,
            status_code=200,
        )

    # --------------------------------------------------------
    # AUDIO: existing diarization
    # --------------------------------------------------------

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

        "application/octet-stream": (
            ".wav"
        ),
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

    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_file.write(
                body
            )

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
