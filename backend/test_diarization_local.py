from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import torch
from pyannote.audio import Pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = (
    PROJECT_ROOT
    / "models"
    / "pyannote"
    / "diarization"
    / "config.yaml"
)

AUDIO_PATH = PROJECT_ROOT / "sample_audio" / "example1.wav"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "local_diarization.json"


def validate_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required file: {path}")

    if path.stat().st_size == 0:
        raise RuntimeError(f"Required file is empty: {path}")


def merge_overlaps(
    segments: list[dict[str, object]],
) -> list[dict[str, float]]:
    raw_overlaps: list[tuple[float, float]] = []

    ordered = sorted(segments, key=lambda item: float(item["start"]))

    for index, first in enumerate(ordered):
        first_start = float(first["start"])
        first_end = float(first["end"])
        first_speaker = str(first["speaker"])

        for second in ordered[index + 1 :]:
            second_start = float(second["start"])
            second_end = float(second["end"])
            second_speaker = str(second["speaker"])

            if second_start >= first_end:
                break

            if first_speaker == second_speaker:
                continue

            overlap_start = max(first_start, second_start)
            overlap_end = min(first_end, second_end)

            if overlap_end > overlap_start:
                raw_overlaps.append((overlap_start, overlap_end))

    if not raw_overlaps:
        return []

    raw_overlaps.sort(key=lambda item: item[0])
    merged: list[list[float]] = []

    for start, end in raw_overlaps:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    return [
        {
            "start": round(start, 3),
            "end": round(end, 3),
        }
        for start, end in merged
    ]


def main() -> int:
    required_files = [
        CONFIG_PATH,
        AUDIO_PATH,
        PROJECT_ROOT
        / "models"
        / "pyannote"
        / "embedding"
        / "pytorch_model.bin",
        PROJECT_ROOT
        / "models"
        / "pyannote"
        / "segmentation"
        / "pytorch_model.bin",
    ]

    for path in required_files:
        validate_file(path)

    # The supplied Pyannote configuration contains project-relative paths.
    os.chdir(PROJECT_ROOT)

    device = torch.device("cpu")

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Configuration: {CONFIG_PATH}")
    print(f"Audio: {AUDIO_PATH}")
    print(f"Device: {device}")
    print()
    print("Loading local Pyannote pipeline...")

    load_started = time.perf_counter()

    pipeline = Pipeline.from_pretrained(str(CONFIG_PATH))
    pipeline.to(device)

    load_seconds = time.perf_counter() - load_started

    print(f"Pipeline loaded in {load_seconds:.3f} seconds.")
    print("Running diarization...")

    inference_started = time.perf_counter()
    diarization = pipeline(str(AUDIO_PATH))
    inference_seconds = time.perf_counter() - inference_started

    segments: list[dict[str, object]] = []
    speakers: set[str] = set()

    for turn, _, speaker in diarization.itertracks(yield_label=True):
        speaker_name = str(speaker)
        speakers.add(speaker_name)

        segments.append(
            {
                "start": round(float(turn.start), 3),
                "end": round(float(turn.end), 3),
                "speaker": speaker_name,
            }
        )

    overlaps = merge_overlaps(segments)

    result = {
        "audio_file": AUDIO_PATH.name,
        "device": str(device),
        "model_load_seconds": round(load_seconds, 3),
        "inference_seconds": round(inference_seconds, 3),
        "speaker_count": len(speakers),
        "speakers": sorted(speakers),
        "segment_count": len(segments),
        "segments": segments,
        "overlaps": overlaps,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )

    print()
    print(json.dumps(result, indent=2))
    print()
    print(f"Output written to: {OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"\nDiarization test failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
