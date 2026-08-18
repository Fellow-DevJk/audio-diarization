from __future__ import annotations

import json
import mimetypes
import os
import uuid
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


AWS_REGION = os.environ["AWS_REGION"]
BUCKET = os.environ["BUCKET"]
ENDPOINT_NAME = os.environ["ENDPOINT_NAME"]

INPUT_PREFIX = os.getenv(
    "INPUT_PREFIX",
    "async-input",
)

DEFAULT_VERIFICATION_THRESHOLD = float(
    os.getenv(
        "SPEAKER_VERIFICATION_THRESHOLD",
        "0.45",
    )
)


s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    endpoint_url=(
        f"https://s3.{AWS_REGION}.amazonaws.com"
    ),
    config=Config(
        signature_version="s3v4",
        s3={
            "addressing_style": "virtual",
        },
    ),
)

runtime = boto3.client(
    "sagemaker-runtime",
    region_name=AWS_REGION,
)


ALLOWED_EXTENSIONS = {
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
}


# ============================================================
# RESPONSE / REQUEST HELPERS
# ============================================================


def response(
    status_code: int,
    body: dict,
) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": (
                "application/json"
            ),
        },
        "body": json.dumps(body),
    }


def parse_body(
    event: dict,
) -> dict:
    raw = event.get("body")

    if not raw:
        return {}

    if isinstance(raw, dict):
        return raw

    try:
        value = json.loads(raw)

    except json.JSONDecodeError:
        return {}

    if not isinstance(value, dict):
        return {}

    return value


def get_route(
    event: dict,
) -> tuple[str, str]:
    request_context = event.get(
        "requestContext",
        {},
    )

    http = request_context.get(
        "http",
        {},
    )

    method = http.get(
        "method",
        "",
    ).upper()

    path = event.get(
        "rawPath",
        "/",
    )

    return method, path


# ============================================================
# AUDIO / S3 HELPERS
# ============================================================


def extension_from_filename(
    filename: str,
) -> str:
    lowered = filename.lower()

    for extension in ALLOWED_EXTENSIONS:
        if lowered.endswith(extension):
            return extension

    return ""


def validate_input_key(
    key: str,
) -> bool:
    return key.startswith(
        f"{INPUT_PREFIX}/"
    )


def validate_audio_key(
    key: str,
) -> bool:
    if not validate_input_key(key):
        return False

    return bool(
        extension_from_filename(key)
    )


def object_exists(
    key: str,
) -> bool:
    try:
        s3.head_object(
            Bucket=BUCKET,
            Key=key,
        )

        return True

    except ClientError as exc:
        code = exc.response[
            "Error"
        ][
            "Code"
        ]

        if code in {
            "404",
            "NoSuchKey",
            "NotFound",
        }:
            return False

        raise


def content_type_for_key(
    key: str,
) -> str | None:
    extension = (
        extension_from_filename(
            key
        )
    )

    if extension:
        return (
            ALLOWED_EXTENSIONS[
                extension
            ]
        )

    guessed, _ = (
        mimetypes.guess_type(key)
    )

    return guessed


# ============================================================
# UPLOAD URL
# ============================================================


def create_upload_url(
    payload: dict,
) -> dict:
    filename = str(
        payload.get(
            "filename",
            "",
        )
    ).strip()

    if not filename:
        return response(
            400,
            {
                "error": (
                    "filename is required"
                ),
            },
        )

    extension = (
        extension_from_filename(
            filename
        )
    )

    if not extension:
        return response(
            400,
            {
                "error": (
                    "Unsupported audio "
                    "format. Use WAV, FLAC, "
                    "MP3 or M4A."
                ),
            },
        )

    content_type = (
        ALLOWED_EXTENSIONS[
            extension
        ]
    )

    object_id = str(
        uuid.uuid4()
    )

    key = (
        f"{INPUT_PREFIX}/"
        f"{object_id}"
        f"{extension}"
    )

    upload_url = (
        s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": BUCKET,
                "Key": key,
                "ContentType": (
                    content_type
                ),
            },
            ExpiresIn=900,
        )
    )

    return response(
        200,
        {
            "upload_url": (
                upload_url
            ),
            "input_key": key,
            "input_location": (
                f"s3://{BUCKET}/{key}"
            ),
            "content_type": (
                content_type
            ),
            "expires_in": 900,
        },
    )


# ============================================================
# DIARIZATION ASYNC INVOCATION
# ============================================================


def start_inference(
    payload: dict,
) -> dict:
    input_key = str(
        payload.get(
            "input_key",
            "",
        )
    ).strip()

    content_type = str(
        payload.get(
            "content_type",
            "",
        )
    ).strip()

    if not input_key:
        return response(
            400,
            {
                "error": (
                    "input_key is required"
                ),
            },
        )

    if not validate_audio_key(
        input_key
    ):
        return response(
            400,
            {
                "error": (
                    "Invalid input key"
                ),
            },
        )

    if content_type not in set(
        ALLOWED_EXTENSIONS.values()
    ):
        return response(
            400,
            {
                "error": (
                    "Invalid content type"
                ),
            },
        )

    if not object_exists(
        input_key
    ):
        return response(
            404,
            {
                "error": (
                    "Uploaded audio was "
                    "not found in S3"
                ),
            },
        )

    inference_id = str(
        uuid.uuid4()
    )

    result = (
        runtime.invoke_endpoint_async(
            EndpointName=ENDPOINT_NAME,
            InputLocation=(
                f"s3://"
                f"{BUCKET}/"
                f"{input_key}"
            ),
            ContentType=content_type,
            Accept="application/json",
            InferenceId=inference_id,
            RequestTTLSeconds=1800,
            InvocationTimeoutSeconds=900,
        )
    )

    return response(
        202,
        {
            "inference_id": result[
                "InferenceId"
            ],
            "output_location": result[
                "OutputLocation"
            ],
            "failure_location": result[
                "FailureLocation"
            ],
            "mode": "diarization",
        },
    )


# ============================================================
# SPEAKER VERIFICATION ASYNC INVOCATION
# ============================================================

def start_verification(
    payload: dict,
) -> dict:
    source_input_key = str(
        payload.get(
            "source_input_key",
            "",
        )
    ).strip()

    reference_input_key = str(
        payload.get(
            "reference_input_key",
            "",
        )
    ).strip()

    if not source_input_key:
        return response(
            400,
            {
                "error": (
                    "source_input_key "
                    "is required"
                ),
            },
        )

    if not reference_input_key:
        return response(
            400,
            {
                "error": (
                    "reference_input_key "
                    "is required"
                ),
            },
        )

    if not validate_audio_key(
        source_input_key
    ):
        return response(
            400,
            {
                "error": (
                    "Invalid source input key"
                ),
            },
        )

    if not validate_audio_key(
        reference_input_key
    ):
        return response(
            400,
            {
                "error": (
                    "Invalid reference "
                    "input key"
                ),
            },
        )

    if not object_exists(
        source_input_key
    ):
        return response(
            404,
            {
                "error": (
                    "Source audio was "
                    "not found in S3"
                ),
            },
        )

    if not object_exists(
        reference_input_key
    ):
        return response(
            404,
            {
                "error": (
                    "Reference audio was "
                    "not found in S3"
                ),
            },
        )

    segments = payload.get(
        "segments"
    )

    if not isinstance(
        segments,
        list,
    ):
        return response(
            400,
            {
                "error": (
                    "segments must be "
                    "a JSON array"
                ),
            },
        )

    if not segments:
        return response(
            400,
            {
                "error": (
                    "segments cannot be empty"
                ),
            },
        )

    if not all(
        isinstance(
            segment,
            dict,
        )
        for segment in segments
    ):
        return response(
            400,
            {
                "error": (
                    "Every segments item "
                    "must be an object"
                ),
            },
        )

    overlaps = payload.get(
        "overlaps",
        [],
    )

    if not isinstance(
        overlaps,
        list,
    ):
        return response(
            400,
            {
                "error": (
                    "overlaps must be "
                    "a JSON array"
                ),
            },
        )

    if not all(
        isinstance(
            overlap,
            dict,
        )
        for overlap in overlaps
    ):
        return response(
            400,
            {
                "error": (
                    "Every overlaps item "
                    "must be an object"
                ),
            },
        )

    raw_speaker = payload.get(
        "speaker"
    )

    speaker = None

    if raw_speaker is not None:
        speaker = str(
            raw_speaker
        ).strip()

        if not speaker:
            speaker = None

    try:
        threshold = float(
            payload.get(
                "threshold",
                DEFAULT_VERIFICATION_THRESHOLD,
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return response(
            400,
            {
                "error": (
                    "threshold must "
                    "be numeric"
                ),
            },
        )

    manifest = {
        "mode": (
            "speaker_verification"
        ),

        "source_location": (
            f"s3://"
            f"{BUCKET}/"
            f"{source_input_key}"
        ),

        "reference_location": (
            f"s3://"
            f"{BUCKET}/"
            f"{reference_input_key}"
        ),

        "segments": segments,

        "overlaps": overlaps,

        "threshold": threshold,
    }

    if speaker is not None:
        manifest[
            "speaker"
        ] = speaker

    manifest_bytes = json.dumps(
        manifest,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )

    inference_id = str(
        uuid.uuid4()
    )

    manifest_key = (
        f"{INPUT_PREFIX}/"
        f"verification-manifests/"
        f"{inference_id}.json"
    )

    s3.put_object(
        Bucket=BUCKET,
        Key=manifest_key,
        Body=manifest_bytes,
        ContentType=(
            "application/json"
        ),
    )

    result = (
        runtime.invoke_endpoint_async(
            EndpointName=ENDPOINT_NAME,
            InputLocation=(
                f"s3://"
                f"{BUCKET}/"
                f"{manifest_key}"
            ),
            ContentType=(
                "application/json"
            ),
            Accept=(
                "application/json"
            ),
            InferenceId=inference_id,
            RequestTTLSeconds=1800,
            InvocationTimeoutSeconds=900,
        )
    )

    return response(
        202,
        {
            "inference_id": result[
                "InferenceId"
            ],
            "output_location": result[
                "OutputLocation"
            ],
            "failure_location": result[
                "FailureLocation"
            ],
            "mode": (
                "speaker_verification"
            ),
            "selected_speaker": (
                speaker
            ),
            "manifest_key": (
                manifest_key
            ),
        },
    )


# ============================================================
# RESULT POLLING
# ============================================================


def s3_uri_to_parts(
    uri: str,
) -> tuple[str, str]:
    parsed = urlparse(uri)

    if parsed.scheme != "s3":
        raise ValueError(
            "Expected S3 URI"
        )

    return (
        parsed.netloc,
        parsed.path.lstrip("/"),
    )


def get_result(
    payload: dict,
) -> dict:
    output_location = str(
        payload.get(
            "output_location",
            "",
        )
    ).strip()

    failure_location = str(
        payload.get(
            "failure_location",
            "",
        )
    ).strip()

    if not output_location:
        return response(
            400,
            {
                "error": (
                    "output_location "
                    "is required"
                ),
            },
        )

    try:
        (
            output_bucket,
            output_key,
        ) = s3_uri_to_parts(
            output_location
        )

    except ValueError:
        return response(
            400,
            {
                "error": (
                    "Invalid output "
                    "location"
                ),
            },
        )

    if output_bucket != BUCKET:
        return response(
            400,
            {
                "error": (
                    "Unexpected output "
                    "bucket"
                ),
            },
        )

    try:
        obj = s3.get_object(
            Bucket=output_bucket,
            Key=output_key,
        )

        raw = obj[
            "Body"
        ].read()

        result = json.loads(
            raw.decode(
                "utf-8"
            )
        )

        return response(
            200,
            {
                "status": "completed",
                "result": result,
            },
        )

    except ClientError as exc:
        code = exc.response[
            "Error"
        ][
            "Code"
        ]

        if code not in {
            "404",
            "NoSuchKey",
            "NotFound",
        }:
            raise

    if failure_location:
        try:
            (
                failure_bucket,
                failure_key,
            ) = s3_uri_to_parts(
                failure_location
            )

            if (
                failure_bucket
                == BUCKET
            ):
                obj = s3.get_object(
                    Bucket=(
                        failure_bucket
                    ),
                    Key=failure_key,
                )

                failure_text = (
                    obj["Body"]
                    .read()
                    .decode(
                        "utf-8",
                        errors="replace",
                    )
                )

                return response(
                    500,
                    {
                        "status": "failed",
                        "error": (
                            failure_text
                        ),
                    },
                )

        except ClientError as exc:
            code = exc.response[
                "Error"
            ][
                "Code"
            ]

            if code not in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                raise

    return response(
        202,
        {
            "status": "processing",
        },
    )


# ============================================================
# ROUTING
# ============================================================


def lambda_handler(
    event,
    context,
):
    method, path = get_route(
        event
    )

    payload = parse_body(
        event
    )

    if (
        method == "GET"
        and path == "/health"
    ):
        return response(
            200,
            {
                "status": "ok",
            },
        )

    if (
        method == "POST"
        and path == "/upload-url"
    ):
        return create_upload_url(
            payload
        )

    if (
        method == "POST"
        and path == "/invoke"
    ):
        return start_inference(
            payload
        )

    if (
        method == "POST"
        and path == "/verify"
    ):
        return start_verification(
            payload
        )

    if (
        method == "POST"
        and path == "/result"
    ):
        return get_result(
            payload
        )

    return response(
        404,
        {
            "error": "Not found",
        },
    )
