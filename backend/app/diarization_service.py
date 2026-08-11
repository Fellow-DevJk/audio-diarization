from __future__ import annotations

import os
import time
from pathlib import Path

import torch
import torchaudio
from pyannote.audio import Pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_ROOT = Path(
    os.getenv(
        "MODEL_ROOT",
        str(PROJECT_ROOT / "models"),
    )
).resolve()

CONFIG_PATH = (
    MODEL_ROOT
    / "pyannote"
    / "diarization"
    / "config.yaml"
)

class DiarizationService:
    def __init__(self) -> None:
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.pipeline: Pipeline | None = None
        self.load_seconds: float | None = None

    def load(self) -> None:
        """
        Load the Pyannote diarization pipeline once.

        The same loaded pipeline is reused for subsequent requests.
        """
        if self.pipeline is not None:
            return

        if not CONFIG_PATH.is_file():
            raise FileNotFoundError(
                f"Pyannote config not found: {CONFIG_PATH}"
            )

        # The supplied Pyannote configuration contains model paths
        # relative to the project root.
        os.chdir(PROJECT_ROOT)

        started = time.perf_counter()

        pipeline = Pipeline.from_pretrained(
            str(CONFIG_PATH)
        )
        pipeline.to(self.device)

        self.pipeline = pipeline
        self.load_seconds = (
            time.perf_counter() - started
        )

    def diarize(
        self,
        audio_path: Path,
    ) -> dict:
        """
        Run speaker diarization on an audio file.

        Returns:
            - audio duration
            - inference duration
            - real-time factor
            - detected speakers
            - speaker-level statistics
            - diarization segments
            - overlapping speaker regions
        """
        if self.pipeline is None:
            raise RuntimeError(
                "Diarization model is not loaded."
            )

        if not audio_path.is_file():
            raise FileNotFoundError(
                f"Audio file not found: {audio_path}"
            )

        # -----------------------------------------
        # Audio metadata
        # -----------------------------------------

        metadata = torchaudio.info(
            str(audio_path)
        )

        if metadata.sample_rate <= 0:
            raise RuntimeError(
                f"Invalid sample rate for audio file: "
                f"{audio_path}"
            )

        audio_duration_seconds = (
            metadata.num_frames
            / metadata.sample_rate
        )

        # -----------------------------------------
        # Model inference
        # -----------------------------------------

        started = time.perf_counter()

        diarization = self.pipeline(
            str(audio_path)
        )

        inference_seconds = (
            time.perf_counter() - started
        )

        # -----------------------------------------
        # Extract speaker segments
        # -----------------------------------------

        segments: list[dict] = []
        speakers: set[str] = set()

        for (
            turn,
            _,
            speaker,
        ) in diarization.itertracks(
            yield_label=True
        ):
            speaker_name = str(speaker)

            speakers.add(speaker_name)

            segments.append(
                {
                    "start": round(
                        float(turn.start),
                        3,
                    ),
                    "end": round(
                        float(turn.end),
                        3,
                    ),
                    "speaker": speaker_name,
                }
            )

        segments.sort(
            key=lambda segment: (
                segment["start"],
                segment["end"],
            )
        )

        sorted_speakers = sorted(
            speakers
        )

        # -----------------------------------------
        # Speaker-level statistics
        # -----------------------------------------

        speaker_stats: dict[str, dict] = {}

        for speaker in sorted_speakers:
            speaker_segments = [
                segment
                for segment in segments
                if segment["speaker"] == speaker
            ]

            speaking_seconds = sum(
                (
                    segment["end"]
                    - segment["start"]
                )
                for segment
                in speaker_segments
            )

            speaking_percentage = (
                (
                    speaking_seconds
                    / audio_duration_seconds
                )
                * 100
                if audio_duration_seconds > 0
                else 0.0
            )

            speaker_stats[speaker] = {
                "segment_count": len(
                    speaker_segments
                ),
                "speaking_seconds": round(
                    speaking_seconds,
                    3,
                ),
                "speaking_percentage": round(
                    speaking_percentage,
                    2,
                ),
            }

        # -----------------------------------------
        # Overlapping speech
        # -----------------------------------------

        overlaps = self._find_overlaps(
            segments
        )

        overlap_seconds = sum(
            overlap["end"]
            - overlap["start"]
            for overlap in overlaps
        )

        # -----------------------------------------
        # Performance metrics
        # -----------------------------------------

        real_time_factor = (
            inference_seconds
            / audio_duration_seconds
            if audio_duration_seconds > 0
            else None
        )

        # -----------------------------------------
        # Final API result
        # -----------------------------------------

        return {
            "device": str(self.device),

            "model_load_seconds": (
                round(
                    self.load_seconds,
                    3,
                )
                if self.load_seconds
                is not None
                else None
            ),

            "audio_duration_seconds": round(
                audio_duration_seconds,
                3,
            ),

            "inference_seconds": round(
                inference_seconds,
                3,
            ),

            "real_time_factor": (
                round(
                    real_time_factor,
                    3,
                )
                if real_time_factor
                is not None
                else None
            ),

            "speaker_count": len(
                sorted_speakers
            ),

            "speakers": sorted_speakers,

            "speaker_stats": speaker_stats,

            "segment_count": len(
                segments
            ),

            "segments": segments,

            "overlap_count": len(
                overlaps
            ),

            "overlap_seconds": round(
                overlap_seconds,
                3,
            ),

            "overlaps": overlaps,
        }

    @staticmethod
    def _find_overlaps(
        segments: list[dict],
    ) -> list[dict[str, float]]:
        """
        Find time regions where different speaker
        tracks overlap.
        """
        overlaps: list[
            dict[str, float]
        ] = []

        ordered = sorted(
            segments,
            key=lambda segment: (
                segment["start"],
                segment["end"],
            ),
        )

        for index, first in enumerate(
            ordered
        ):
            for second in ordered[
                index + 1:
            ]:
                # Because segments are ordered by
                # start time, no later segment can
                # overlap once this condition holds.
                if (
                    second["start"]
                    >= first["end"]
                ):
                    break

                if (
                    second["speaker"]
                    == first["speaker"]
                ):
                    continue

                start = max(
                    first["start"],
                    second["start"],
                )

                end = min(
                    first["end"],
                    second["end"],
                )

                if end > start:
                    overlaps.append(
                        {
                            "start": round(
                                start,
                                3,
                            ),
                            "end": round(
                                end,
                                3,
                            ),
                        }
                    )

        return overlaps


diarization_service = (
    DiarizationService()
)