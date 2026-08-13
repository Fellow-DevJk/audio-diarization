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

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    endpoint_url=f"https://s3.{AWS_REGION}.amazonaws.com",
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


def response(
    status_code: int,
    body: dict,
) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body),
    }


def parse_body(event: dict) -> dict:
    raw = event.get("body")

    if not raw:
        return {}

    if isinstance(raw, dict):
        return raw

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def get_route(event: dict) -> tuple[str, str]:
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


def extension_from_filename(
    filename: str,
) -> str:
    lowered = filename.lower()

    for extension in ALLOWED_EXTENSIONS:
        if lowered.endswith(extension):
            return extension

    return ""


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
                "error": "filename is required",
            },
        )

    extension = extension_from_filename(
        filename
    )

    if not extension:
        return response(
            400,
            {
                "error": (
                    "Unsupported audio format. "
                    "Use WAV, FLAC, MP3 or M4A."
                ),
            },
        )

    content_type = ALLOWED_EXTENSIONS[
        extension
    ]

    object_id = str(uuid.uuid4())

    key = (
        f"{INPUT_PREFIX}/"
        f"{object_id}{extension}"
    )

    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=900,
    )

    return response(
        200,
        {
            "upload_url": upload_url,
            "input_key": key,
            "input_location": (
                f"s3://{BUCKET}/{key}"
            ),
            "content_type": content_type,
            "expires_in": 900,
        },
    )


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
                "error": "input_key is required",
            },
        )

    if not input_key.startswith(
        f"{INPUT_PREFIX}/"
    ):
        return response(
            400,
            {
                "error": "Invalid input key",
            },
        )

    if content_type not in set(
        ALLOWED_EXTENSIONS.values()
    ):
        return response(
            400,
            {
                "error": "Invalid content type",
            },
        )

    try:
        s3.head_object(
            Bucket=BUCKET,
            Key=input_key,
        )
    except ClientError as exc:
        if exc.response[
            "Error"
        ][
            "Code"
        ] in {
            "404",
            "NoSuchKey",
            "NotFound",
        }:
            return response(
                404,
                {
                    "error": (
                        "Uploaded audio was "
                        "not found in S3"
                    ),
                },
            )

        raise

    inference_id = str(
        uuid.uuid4()
    )

    result = (
        runtime.invoke_endpoint_async(
            EndpointName=ENDPOINT_NAME,
            InputLocation=(
                f"s3://{BUCKET}/{input_key}"
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
        },
    )


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
        output_bucket, output_key = (
            s3_uri_to_parts(
                output_location
            )
        )
    except ValueError:
        return response(
            400,
            {
                "error": (
                    "Invalid output location"
                ),
            },
        )

    if output_bucket != BUCKET:
        return response(
            400,
            {
                "error": (
                    "Unexpected output bucket"
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
            failure_bucket, failure_key = (
                s3_uri_to_parts(
                    failure_location
                )
            )

            if (
                failure_bucket
                == BUCKET
            ):
                obj = s3.get_object(
                    Bucket=failure_bucket,
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
                        "error": failure_text,
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
