from __future__ import annotations

import tempfile
from pathlib import Path
from urllib.parse import urlparse

import boto3


s3 = boto3.client("s3")


ALLOWED_SUFFIXES = {
    ".wav",
    ".flac",
    ".mp3",
    ".m4a",
}


def parse_s3_uri(
    uri: str,
) -> tuple[str, str]:
    parsed = urlparse(
        uri
    )

    if parsed.scheme != "s3":
        raise ValueError(
            "Expected an s3:// URI."
        )

    bucket = (
        parsed.netloc.strip()
    )

    key = (
        parsed.path
        .lstrip("/")
        .strip()
    )

    if not bucket or not key:
        raise ValueError(
            "Invalid S3 URI."
        )

    return bucket, key


def download_audio(
    uri: str,
) -> Path:
    """
    Download an audio object from S3 to a
    temporary local path.

    Caller is responsible for deleting the
    returned path.
    """

    bucket, key = (
        parse_s3_uri(uri)
    )

    suffix = (
        Path(key)
        .suffix
        .lower()
    )

    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(
            "Unsupported S3 audio format. "
            "Use WAV, FLAC, MP3, or M4A."
        )

    temp_file = (
        tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        )
    )

    temp_path = Path(
        temp_file.name
    )

    temp_file.close()

    try:
        s3.download_file(
            bucket,
            key,
            str(temp_path),
        )

    except Exception:
        if temp_path.exists():
            temp_path.unlink()

        raise

    return temp_path
