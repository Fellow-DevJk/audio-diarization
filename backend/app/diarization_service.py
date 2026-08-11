from __future__ import annotations

import os
import time
from pathlib import Path

import torch
from pyannote.audio import Pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "models"
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
        if self.pipeline is not None:
            return

        if not CONFIG_PATH.is_file():
            raise FileNotFoundError(
                f"Pyannote config not found: {CONFIG_PATH}"
            )

        # Supplied config contains paths relative to project root.
        os.chdir(PROJECT_ROOT)

        started = time.perf_counter()

        pipeline = Pipeline.from_pretrained(str(CONFIG_PATH))
        pipeline.to(self.device)

        self.pipeline = pipeline
        self.load_seconds = time.perf_counter() - started

    def diarize(self, audio_path: Path) -> dict:
        if self.pipeline is None:
            raise RuntimeError("Diarization model is not loaded.")

        if not audio_path.is_file():
            raise FileNotFoundError(
                f"Audio file not found: {audio_path}"
            )

        started = time.perf_counter()

        diarization = self.pipeline(str(audio_path))

        inference_seconds = time.perf_counter() - started

        segments = []
        speakers = set()

        for turn, _, speaker in diarization.itertracks(
            yield_label=True
        ):
            speaker_name = str(speaker)
            speakers.add(speaker_name)

            segments.append(
                {
                    "start": round(float(turn.start), 3),
                    "end": round(float(turn.end), 3),
                    "speaker": speaker_name,
                }
            )

        return {
            "device": str(self.device),
            "model_load_seconds": (
                round(self.load_seconds, 3)
                if self.load_seconds is not None
                else None
            ),
            "inference_seconds": round(
                inference_seconds,
                3,
            ),
            "speaker_count": len(speakers),
            "speakers": sorted(speakers),
            "segment_count": len(segments),
            "segments": segments,
            "overlaps": self._find_overlaps(segments),
        }

    @staticmethod
    def _find_overlaps(
        segments: list[dict],
    ) -> list[dict[str, float]]:
        overlaps = []

        ordered = sorted(
            segments,
            key=lambda segment: segment["start"],
        )

        for index, first in enumerate(ordered):
            for second in ordered[index + 1:]:
                if second["start"] >= first["end"]:
                    break

                if second["speaker"] == first["speaker"]:
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
                            "start": round(start, 3),
                            "end": round(end, 3),
                        }
                    )

        return overlaps


diarization_service = DiarizationService()
