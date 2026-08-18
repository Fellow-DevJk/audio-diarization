from __future__ import annotations

import math
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import torch
import torchaudio
try:
    from speechbrain.inference.speaker import (
        SpeakerRecognition,
    )
except ModuleNotFoundError:
    from speechbrain.pretrained import (
        SpeakerRecognition,
    )

PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)

MODEL_ROOT = Path(
    os.getenv(
        "MODEL_ROOT",
        str(PROJECT_ROOT / "models"),
    )
).resolve()

ECAPA_MODEL_DIR = (
    MODEL_ROOT / "ecapa_tdnn"
)

ECAPA_CACHE_DIR = Path(
    tempfile.gettempdir()
) / "audio-diarization-ecapa"

DEFAULT_THRESHOLD = float(
    os.getenv(
        "SPEAKER_VERIFICATION_THRESHOLD",
        "0.45",
    )
)

MIN_VERIFICATION_SECONDS = float(
    os.getenv(
        "MIN_VERIFICATION_SECONDS",
        "3.0",
    )
)


@dataclass
class SpeakerExtractionResult:
    """
    Metadata for audio extracted from one
    diarized speaker.

    The extracted WAV contains only regions
    assigned to the requested speaker, with
    detected cross-talk intervals removed.
    """

    path: Path
    speaker: str

    source_segment_count: int
    clean_fragment_count: int

    source_speaking_seconds: float
    excluded_overlap_seconds: float
    extracted_seconds: float


def _merge_intervals(
    intervals: list[
        tuple[float, float]
    ],
) -> list[
    tuple[float, float]
]:
    """
    Merge overlapping or touching time intervals.
    """

    cleaned = sorted(
        (
            (
                max(
                    0.0,
                    float(start),
                ),
                max(
                    0.0,
                    float(end),
                ),
            )
            for start, end
            in intervals
            if float(end) > float(start)
        ),
        key=lambda item: (
            item[0],
            item[1],
        ),
    )

    if not cleaned:
        return []

    merged: list[
        tuple[float, float]
    ] = [
        cleaned[0]
    ]

    for start, end in cleaned[1:]:
        previous_start, previous_end = (
            merged[-1]
        )

        if start <= previous_end:
            merged[-1] = (
                previous_start,
                max(
                    previous_end,
                    end,
                ),
            )
        else:
            merged.append(
                (
                    start,
                    end,
                )
            )

    return merged


def _subtract_intervals(
    start: float,
    end: float,
    exclusions: list[
        tuple[float, float]
    ],
) -> list[
    tuple[float, float]
]:
    """
    Remove exclusion intervals from one
    source interval.

    Example:

        source:
            1.0 ---- 5.0

        exclusion:
            2.0 ---- 3.0

        result:
            1.0 ---- 2.0
            3.0 ---- 5.0
    """

    start = float(start)
    end = float(end)

    if end <= start:
        return []

    fragments: list[
        tuple[float, float]
    ] = []

    cursor = start

    for (
        exclusion_start,
        exclusion_end,
    ) in exclusions:
        if exclusion_end <= cursor:
            continue

        if exclusion_start >= end:
            break

        if exclusion_start > cursor:
            fragment_end = min(
                exclusion_start,
                end,
            )

            if fragment_end > cursor:
                fragments.append(
                    (
                        cursor,
                        fragment_end,
                    )
                )

        cursor = max(
            cursor,
            exclusion_end,
        )

        if cursor >= end:
            break

    if cursor < end:
        fragments.append(
            (
                cursor,
                end,
            )
        )

    return fragments


def _duration(
    intervals: list[
        tuple[float, float]
    ],
) -> float:
    return sum(
        max(
            0.0,
            end - start,
        )
        for start, end
        in intervals
    )


def extract_speaker_audio(
    source_audio: Path,
    segments: list[dict],
    overlaps: list[dict],
    speaker: str,
) -> SpeakerExtractionResult:
    """
    Extract non-overlapping audio belonging
    to one diarized speaker.

    All diarization regions assigned to the
    requested speaker are collected.

    Any detected cross-talk region is removed
    before the remaining fragments are
    concatenated into a temporary WAV.

    This avoids feeding obvious overlapping
    speakers into ECAPA-TDNN.

    Caller is responsible for removing the
    returned temporary file when finished.
    """

    source_audio = (
        Path(source_audio).resolve()
    )

    if not source_audio.is_file():
        raise FileNotFoundError(
            "Source audio file not found: "
            f"{source_audio}"
        )

    selected_segments = sorted(
        (
            segment
            for segment in segments
            if (
                str(
                    segment.get(
                        "speaker",
                        "",
                    )
                )
                == speaker
            )
        ),
        key=lambda segment: (
            float(
                segment.get(
                    "start",
                    0.0,
                )
            ),
            float(
                segment.get(
                    "end",
                    0.0,
                )
            ),
        ),
    )

    if not selected_segments:
        raise ValueError(
            "No diarization segments found "
            f"for speaker {speaker}."
        )

    source_intervals = [
        (
            float(
                segment["start"]
            ),
            float(
                segment["end"]
            ),
        )
        for segment
        in selected_segments
        if (
            float(
                segment["end"]
            )
            >
            float(
                segment["start"]
            )
        )
    ]

    if not source_intervals:
        raise ValueError(
            "No usable diarization intervals "
            f"found for speaker {speaker}."
        )

    overlap_intervals = (
        _merge_intervals(
            [
                (
                    float(
                        overlap["start"]
                    ),
                    float(
                        overlap["end"]
                    ),
                )
                for overlap
                in overlaps
                if (
                    "start" in overlap
                    and "end" in overlap
                    and float(
                        overlap["end"]
                    )
                    >
                    float(
                        overlap["start"]
                    )
                )
            ]
        )
    )

    clean_intervals: list[
        tuple[float, float]
    ] = []

    for start, end in source_intervals:
        clean_intervals.extend(
            _subtract_intervals(
                start,
                end,
                overlap_intervals,
            )
        )

    clean_intervals = [
        (
            start,
            end,
        )
        for start, end
        in clean_intervals
        if end > start
    ]

    if not clean_intervals:
        raise ValueError(
            "No clean non-overlapping audio "
            f"remains for speaker {speaker}."
        )

    waveform, sample_rate = (
        torchaudio.load(
            str(source_audio)
        )
    )

    if sample_rate <= 0:
        raise RuntimeError(
            "Invalid sample rate for "
            f"{source_audio}."
        )

    if waveform.numel() == 0:
        raise RuntimeError(
            "Source audio contains no "
            f"samples: {source_audio}"
        )

    # SpeakerRecognition operates most
    # predictably with a mono speaker signal.
    if waveform.shape[0] > 1:
        waveform = waveform.mean(
            dim=0,
            keepdim=True,
        )

    total_frames = int(
        waveform.shape[1]
    )

    chunks: list[
        torch.Tensor
    ] = []

    actual_clean_intervals: list[
        tuple[float, float]
    ] = []

    for start, end in clean_intervals:
        start_frame = max(
            0,
            int(
                math.floor(
                    start * sample_rate
                )
            ),
        )

        end_frame = min(
            total_frames,
            int(
                math.ceil(
                    end * sample_rate
                )
            ),
        )

        if end_frame <= start_frame:
            continue

        chunk = waveform[
            :,
            start_frame:end_frame,
        ]

        if chunk.numel() == 0:
            continue

        chunks.append(
            chunk
        )

        actual_clean_intervals.append(
            (
                start_frame
                / sample_rate,
                end_frame
                / sample_rate,
            )
        )

    if not chunks:
        raise ValueError(
            "Speaker extraction produced "
            f"no audio for {speaker}."
        )

    combined = torch.cat(
        chunks,
        dim=1,
    )

    if combined.shape[1] == 0:
        raise ValueError(
            "Speaker extraction produced "
            f"an empty waveform for {speaker}."
        )

    temp_file = (
        tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        )
    )

    temp_path = Path(
        temp_file.name
    )

    temp_file.close()

    try:
        torchaudio.save(
            str(temp_path),
            combined,
            sample_rate,
        )
    except Exception:
        if temp_path.exists():
            temp_path.unlink()

        raise

    source_seconds = (
        _duration(
            source_intervals
        )
    )

    extracted_seconds = (
        combined.shape[1]
        / sample_rate
    )

    excluded_overlap_seconds = max(
        0.0,
        source_seconds
        - extracted_seconds,
    )

    return SpeakerExtractionResult(
        path=temp_path,
        speaker=speaker,

        source_segment_count=len(
            selected_segments
        ),

        clean_fragment_count=len(
            actual_clean_intervals
        ),

        source_speaking_seconds=round(
            source_seconds,
            3,
        ),

        excluded_overlap_seconds=round(
            excluded_overlap_seconds,
            3,
        ),

        extracted_seconds=round(
            extracted_seconds,
            3,
        ),
    )


class SpeakerVerificationService:
    """
    Local ECAPA-TDNN speaker verification
    service.

    Supports:

    1. Direct comparison of two audio files.

    2. Speaker-selected verification:
       extract one diarized speaker from a
       multi-speaker recording, remove detected
       cross-talk, and compare the resulting
       speaker signal against a reference
       recording.
    """

    def __init__(self) -> None:
        self.device = (
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        self.model: (
            SpeakerRecognition | None
        ) = None

        self.load_seconds: (
            float | None
        ) = None

    def load(self) -> None:
        """
        Load the local SpeechBrain ECAPA-TDNN
        model once.

        The loaded model is reused across
        subsequent comparisons.
        """

        if self.model is not None:
            return

        if not ECAPA_MODEL_DIR.is_dir():
            raise FileNotFoundError(
                "ECAPA model directory "
                "not found: "
                f"{ECAPA_MODEL_DIR}"
            )

        hyperparams_path = (
            ECAPA_MODEL_DIR
            / "hyperparams.yaml"
        )

        if not hyperparams_path.is_file():
            raise FileNotFoundError(
                "ECAPA hyperparams not "
                "found: "
                f"{hyperparams_path}"
            )

        started = time.perf_counter()

        ECAPA_CACHE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        model = (
            SpeakerRecognition
            .from_hparams(
                source=str(
                    ECAPA_MODEL_DIR
                ),
                hparams_file=(
                    "hyperparams.yaml"
                ),
                savedir=str(
                    ECAPA_CACHE_DIR
                ),
                overrides={
                    "pretrained_path":
                        str(
                            ECAPA_MODEL_DIR
                        ),
                },
                run_opts={
                    "device": self.device,
                },
            )
        )

        self.model = model

        self.load_seconds = (
            time.perf_counter()
            - started
        )

    def compare(
        self,
        primary_audio: Path,
        reference_audio: Path,
        threshold: float = (
            DEFAULT_THRESHOLD
        ),
    ) -> dict:
        """
        Compare two predominantly single-speaker
        audio files using ECAPA-TDNN.

        The SpeechBrain similarity score is
        returned directly.

        The threshold decision is computed here
        explicitly so that the API clearly
        reports which configured threshold was
        used.

        A threshold match is NOT equivalent to
        forensic or biometric identification.
        """

        if self.model is None:
            raise RuntimeError(
                "Speaker verification model "
                "is not loaded."
            )

        primary_audio = (
            Path(
                primary_audio
            ).resolve()
        )

        reference_audio = (
            Path(
                reference_audio
            ).resolve()
        )

        if not primary_audio.is_file():
            raise FileNotFoundError(
                "Primary audio file "
                "not found: "
                f"{primary_audio}"
            )

        if not reference_audio.is_file():
            raise FileNotFoundError(
                "Reference audio file "
                "not found: "
                f"{reference_audio}"
            )

        threshold = float(
            threshold
        )

        started = time.perf_counter()

        score, _ = (
            self.model.verify_files(
                str(
                    primary_audio
                ),
                str(
                    reference_audio
                ),
            )
        )

        inference_seconds = (
            time.perf_counter()
            - started
        )

        similarity_score = float(
            score.item()
        )

        threshold_match = (
            similarity_score
            >= threshold
        )

        return {
            "model": "ECAPA-TDNN",

            "device": self.device,

            "model_load_seconds": (
                round(
                    self.load_seconds,
                    3,
                )
                if self.load_seconds
                is not None
                else None
            ),

            "inference_seconds": round(
                inference_seconds,
                3,
            ),

            "similarity_score": round(
                similarity_score,
                4,
            ),

            "threshold": round(
                threshold,
                4,
            ),

            "threshold_match": (
                threshold_match
            ),

            "threshold_decision": (
                "match"
                if threshold_match
                else "no_match"
            ),
        }

    def compare_selected_speaker(
        self,
        source_audio: Path,
        reference_audio: Path,
        segments: list[dict],
        overlaps: list[dict],
        speaker: str,
        threshold: float = (
            DEFAULT_THRESHOLD
        ),
    ) -> dict:
        """
        Compare one diarized speaker from a
        potentially multi-speaker recording
        against a reference voice sample.

        Workflow:

            source recording
                ↓
            select speaker segments
                ↓
            remove detected cross-talk
                ↓
            concatenate remaining clean audio
                ↓
            ECAPA-TDNN comparison
                ↓
            structured result

        If the source recording contains only
        one diarized speaker, this naturally
        becomes the ordinary two-file comparison
        workflow discussed as Option A.
        """

        extraction: (
            SpeakerExtractionResult
            | None
        ) = None

        try:
            extraction = (
                extract_speaker_audio(
                    source_audio=(
                        source_audio
                    ),
                    segments=segments,
                    overlaps=overlaps,
                    speaker=speaker,
                )
            )

            # -----------------------------------------
            # Minimum usable clean speaker audio
            # -----------------------------------------

            if (
                extraction.extracted_seconds
                < MIN_VERIFICATION_SECONDS
            ):
                return {
                    "comparison_available": False,

                    "reason": (
                        "insufficient_clean_speaker_audio"
                    ),

                    "selected_speaker": (
                        speaker
                    ),

                    "source_filename": (
                        Path(
                            source_audio
                        ).name
                    ),

                    "reference_filename": (
                        Path(
                            reference_audio
                        ).name
                    ),

                    "minimum_required_seconds": (
                        MIN_VERIFICATION_SECONDS
                    ),

                    "speaker_extraction": {
                        "source_segment_count": (
                            extraction
                            .source_segment_count
                        ),

                        "clean_fragment_count": (
                            extraction
                            .clean_fragment_count
                        ),

                        "source_speaking_seconds": (
                            extraction
                            .source_speaking_seconds
                        ),

                        "excluded_overlap_seconds": (
                            extraction
                            .excluded_overlap_seconds
                        ),

                        "extracted_seconds": (
                            extraction
                            .extracted_seconds
                        ),
                    },
                }

            # -----------------------------------------
            # ECAPA verification
            # -----------------------------------------

            verification = self.compare(
                primary_audio=(
                    extraction.path
                ),
                reference_audio=(
                    reference_audio
                ),
                threshold=threshold,
            )

            return {
                "comparison_available": True,

                **verification,

                "selected_speaker": (
                    speaker
                ),

                "source_filename": (
                    Path(
                        source_audio
                    ).name
                ),

                "reference_filename": (
                    Path(
                        reference_audio
                    ).name
                ),

                "speaker_extraction": {
                    "source_segment_count": (
                        extraction
                        .source_segment_count
                    ),

                    "clean_fragment_count": (
                        extraction
                        .clean_fragment_count
                    ),

                    "source_speaking_seconds": (
                        extraction
                        .source_speaking_seconds
                    ),

                    "excluded_overlap_seconds": (
                        extraction
                        .excluded_overlap_seconds
                    ),

                    "extracted_seconds": (
                        extraction
                        .extracted_seconds
                    ),
                },
            }

        finally:
            if (
                extraction is not None
                and
                extraction.path.exists()
            ):
                extraction.path.unlink()

speaker_verification_service = (
    SpeakerVerificationService()
)
