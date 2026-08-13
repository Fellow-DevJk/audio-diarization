# Audio Diarization Demo

A browser-based speaker diarization demo built around Pyannote Audio and deployed on AWS.

The application accepts an audio recording, identifies speaker turns, returns timestamps and speaker-level statistics, detects overlapping speech, and renders the result as an interactive waveform and speaker timeline.

## Live Demo

Frontend:

https://fellow-devjk.github.io/audio-diarization/

The demo backend is intentionally operated with a manual ON/OFF switch to control SageMaker GPU cost. If the frontend reports that the AWS backend is unavailable, the demo infrastructure may currently be switched off.

## Architecture

```text
Browser / GitHub Pages
        |
        | POST /upload-url
        v
AWS Lambda Function URL
        |
        | returns presigned S3 PUT URL
        v
Amazon S3
        |
        | audio object
        v
AWS Lambda
        |
        | InvokeEndpointAsync
        v
Amazon SageMaker Async Inference
        |
        | ml.g4dn.xlarge / NVIDIA T4
        v
Pyannote diarization container
        |
        | JSON result
        v
Amazon S3
        |
        | Lambda /result polling
        v
Browser visualization
````

The browser never receives AWS credentials and never calls SageMaker directly.

## Current Stack

### Model runtime

* Pyannote Audio 3.1.1
* PyTorch 2.5.1
* CUDA 12.4
* custom local Pyannote model artifacts
* SageMaker `ml.g4dn.xlarge`

### Backend

* FastAPI for local development
* Docker
* Amazon ECR
* Amazon SageMaker Async Inference
* AWS Lambda broker
* Amazon S3
* CloudWatch Logs

### Frontend

* HTML
* CSS
* vanilla JavaScript
* WaveSurfer.js
* GitHub Pages

## Repository Structure

```text
audio-diarization/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   └── diarization_service.py
│   ├── Dockerfile.cpu
│   ├── Dockerfile.gpu
│   ├── Dockerfile.gpu.sagemaker
│   └── requirements-container.txt
│
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   ├── config.js
│   └── README.md
│
├── infrastructure/
│   └── aws/
│       ├── lambda-broker/
│       ├── demo-on.sh
│       ├── demo-off.sh
│       ├── demo-status.sh
│       ├── env.sh
│       └── AWS configuration files
│
└── .github/
    └── workflows/
        └── pages.yml
```

Model weights are intentionally not committed to Git.

## Application Flow

The public frontend uses four broker operations.

### `GET /health`

Checks whether the Lambda broker is reachable.

### `POST /upload-url`

Example request:

```json
{
  "filename": "meeting.wav",
  "size_bytes": 104390
}
```

Returns a short-lived presigned S3 upload URL.

### Direct S3 upload

The browser uploads the audio directly to S3 with the returned presigned URL.

Audio does not pass through Lambda.

### `POST /invoke`

Example request:

```json
{
  "input_key": "async-input/<uuid>.wav",
  "content_type": "audio/wav"
}
```

The Lambda broker submits a SageMaker Async Inference request.

### `POST /result`

The frontend polls the output and failure locations returned from `/invoke`.

While processing:

```json
{
  "status": "processing"
}
```

On completion:

```json
{
  "status": "completed",
  "result": {
    "device": "cuda",
    "speaker_count": 2,
    "segment_count": 7,
    "segments": []
  }
}
```

## Diarization Response

Typical fields include:

```text
filename
device
model_load_seconds
audio_duration_seconds
inference_seconds
real_time_factor

speaker_count
speakers
speaker_stats

segment_count
segments

overlap_count
overlap_seconds
overlaps
```

A segment has the form:

```json
{
  "start": 1.242,
  "end": 4.817,
  "speaker": "SPEAKER_00"
}
```

## Local Development

The local Python environment used during development is Python 3.10.

Activate it:

```bash
source .venv-diarization/bin/activate
```

Start the local FastAPI service:

```bash
uvicorn backend.app.main:app \
  --host 0.0.0.0 \
  --port 8000
```

Check:

```bash
curl http://localhost:8000/health
```

Local diarization:

```bash
curl \
  -X POST \
  http://localhost:8000/diarize \
  -F "audio=@sample_audio/example1.wav"
```

## Docker

CPU and GPU inference containers are maintained separately.

The SageMaker image must support SageMaker's `serve` invocation contract.

Local SageMaker-style test:

```bash
docker run \
  --rm \
  --gpus all \
  -p 8084:8080 \
  audio-diarization:gpu-sm-v2 \
  serve
```

Then:

```bash
curl http://localhost:8084/ping
```

## Demo Operations

AWS identifiers used by the operational scripts are stored in:

```text
infrastructure/aws/env.sh
```

Turn the public demo on:

```bash
./infrastructure/aws/demo-on.sh
```

Check status:

```bash
./infrastructure/aws/demo-status.sh
```

Turn the demo off after use:

```bash
./infrastructure/aws/demo-off.sh
```

The intended demo workflow is:

```text
demo-on.sh
→ wait for SageMaker GPU
→ send one warm-up request
→ run presentation
→ demo-off.sh
```

## Security and Cost Controls

This repository contains no AWS access keys.

The frontend contains only public application configuration.

Current demo controls include or are intended to include:

* presigned S3 uploads
* private S3 bucket
* public-access blocking on S3
* CORS restricted to development and GitHub Pages origins
* SageMaker execution through Lambda only
* upload-size validation
* S3 lifecycle expiration for temporary audio/results
* manual SageMaker GPU ON/OFF control
* Lambda concurrency limiting while the demo is public

This is a demonstration deployment, not a production multi-tenant service.

## Frontend Development

Frontend contributors should read:

```text
frontend/README.md
```

The frontend may be redesigned extensively, but the AWS request contract must remain intact unless backend changes are coordinated.

## Known Limitations

* speakers are anonymous labels such as `SPEAKER_00`
* diarization quality depends on recording conditions
* overlapping speech may be imperfect
* cold-start time is significant when GPU capacity is started from zero
* the current CUDA image is larger than ideal and can be optimized later
* the public Lambda broker is designed for controlled demo usage rather than unrestricted production traffic

## Model Artifacts

Model weights are excluded from Git.

The local runtime expects Pyannote artifacts under:

```text
models/pyannote/
```

and ECAPA-TDNN artifacts under:

```text
models/ecapa_tdnn/
```

Do not commit model binaries or checkpoints unless repository storage and licensing requirements are explicitly reviewed.