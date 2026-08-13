# Frontend Redesign Guide

This directory contains the public UI for the speaker diarization demo.

The frontend is intentionally static so it can be hosted on GitHub Pages.

A UI/UX redesign may replace most of the visual structure and styling, but the AWS request sequence described below must remain intact unless coordinated with the backend owner.

## Files

```text
frontend/
├── index.html
├── styles.css
├── app.js
├── config.js
└── README.md
````

## Primary UX Responsibilities

The frontend should provide:

* audio file selection
* drag-and-drop upload
* clear processing feedback
* audio waveform playback
* speaker count
* segment count
* audio duration
* inference time
* real-time factor
* compute device
* speaker statistics
* color-coded speaker timeline
* clickable speaker segments
* segment table
* overlapping-speech visualization
* useful error states
* responsive desktop/mobile behavior

## Backend Contract

The browser talks only to the Lambda broker configured in `config.js`.

### 1. Health

```http
GET /health
```

### 2. Request upload URL

```http
POST /upload-url
Content-Type: application/json
```

Example:

```json
{
  "filename": "meeting.wav",
  "size_bytes": 1234567
}
```

Response:

```json
{
  "upload_url": "https://...",
  "input_key": "async-input/<uuid>.wav",
  "input_location": "s3://...",
  "content_type": "audio/wav",
  "expires_in": 900
}
```

### 3. Upload directly to S3

Use the returned `upload_url`.

```http
PUT <presigned URL>
Content-Type: <returned content_type>
```

The file body is the audio file itself.

Do not proxy the audio through Lambda.

### 4. Start diarization

```http
POST /invoke
Content-Type: application/json
```

```json
{
  "input_key": "async-input/<uuid>.wav",
  "content_type": "audio/wav"
}
```

Response:

```json
{
  "inference_id": "...",
  "output_location": "s3://...",
  "failure_location": "s3://..."
}
```

### 5. Poll result

```http
POST /result
Content-Type: application/json
```

```json
{
  "output_location": "s3://...",
  "failure_location": "s3://..."
}
```

Processing:

```json
{
  "status": "processing"
}
```

Completed:

```json
{
  "status": "completed",
  "result": {
    "...": "..."
  }
}
```

## Result Shape

The frontend currently consumes:

```text
speaker_count
speakers
speaker_stats

segment_count
segments

audio_duration_seconds
inference_seconds
real_time_factor
device

overlap_count
overlap_seconds
overlaps
```

Example:

```json
{
  "device": "cuda",
  "speaker_count": 2,
  "speakers": [
    "SPEAKER_00",
    "SPEAKER_01"
  ],
  "speaker_stats": {
    "SPEAKER_00": {
      "segment_count": 4,
      "speaking_seconds": 12.3,
      "speaking_percentage": 55.2
    }
  },
  "segments": [
    {
      "start": 0.4,
      "end": 3.8,
      "speaker": "SPEAKER_00"
    }
  ],
  "overlaps": []
}
```

## Things You May Change

A frontend contributor may freely change:

* layout
* typography
* spacing
* color palette
* icons
* responsive behavior
* upload experience
* loading states
* charts
* timeline presentation
* result hierarchy
* animations
* accessibility improvements
* frontend component organization

## Things You Should Not Change Without Coordination

Do not:

* put AWS credentials in frontend code
* call SageMaker directly
* call ECR
* call S3 with permanent AWS credentials
* bypass the presigned upload workflow
* remove async result polling
* modify files under `backend/`
* modify files under `infrastructure/`
* commit model weights
* expose IAM credentials or secrets

## Public Configuration

`config.js` contains only public browser configuration.

The Lambda Function URL is public by design and therefore is not a secret.

## Local Frontend Development

From the repository root:

```bash
cd frontend
python -m http.server 5500
```

Open:

```text
http://localhost:5500
```

The AWS Lambda and S3 CORS configuration currently permits this development origin.

## Recommended Redesign Priorities

For a polished demo, prioritize:

1. clearer information hierarchy
2. stronger upload state
3. better analysis-progress feedback
4. improved speaker timeline readability
5. stronger speaker identity/color consistency
6. mobile responsiveness
7. accessible contrast and keyboard controls
8. compact but useful technical metrics
9. clear empty/error states
10. presentation-ready visual polish

The model result structure should drive the visualization rather than being hidden behind decorative UI.