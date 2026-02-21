# Transcription Pipeline

Audio-to-text transcription service built with faster-whisper and FastAPI.

## Architecture
```
Client → FastAPI (POST /transcribe) → Thread Pool Workers → faster-whisper → SQLite (results)
```

1. Client uploads audio via POST /transcribe
2. API validates format/size, saves file, creates job record, returns 202 with job ID
3. Background worker picks up job: convert → split (if long) → transcribe → store result
4. Client polls GET /transcribe/{job_id} for status and results

## Design Decisions

**faster-whisper over OpenAI Whisper** — CTranslate2-optimized, roughly 4x faster CPU inference with lower memory at comparable accuracy.

**Normalize all audio to 16kHz mono WAV** — Whisper expects 16kHz input. Using pydub/FFmpeg to convert everything to a canonical format decouples format handling from transcription. Adding a new format = adding its extension to the whitelist.

**Chunk long audio** — Whisper loads entire audio into memory. A 2-hour file could OOM on constrained hardware. 10-minute chunks keep memory bounded and enable future parallelization.

**Thread pool for concurrency** — ThreadPoolExecutor keeps the project self-contained (no Redis/RabbitMQ). In production, swap to Celery + Redis for distributed processing.

**Exponential backoff retries** — Failed jobs retry up to 3 times with delays of 10s, 30s, 90s. Handles transient failures like memory pressure. Permanent failures are logged with error details.

**SQLite for job tracking** — Zero-config for single-node. Tracks full lifecycle (queued → processing → completed/failed). For production, swap to PostgreSQL.

## Project Structure
```
transcribe/
├── app/
│   ├── __init__.py
│   ├── config.py          # All configurable settings
│   ├── database.py        # SQLite job tracking (CRUD)
│   ├── transcriber.py     # Core: validate → convert → split → transcribe
│   ├── worker.py          # Thread pool + retry logic
│   └── main.py            # FastAPI endpoints
├── transcribe.py          # Standalone CLI
├── requirements.txt
└── Dockerfile
```

## Setup

### Prerequisites
- Python 3.9+
- FFmpeg (`brew install ffmpeg` or `sudo apt install ffmpeg`)

### Install
```bash
git clone <repo_url>
cd transcribe
pip install -r requirements.txt
```

### CLI Usage
```bash
python3 transcribe.py audio.mp3
python3 transcribe.py audio.wav --json
```

### API Usage
```bash
python3 -m uvicorn app.main:app --reload
```

API docs at http://localhost:8000/docs
```bash
# Upload
curl -X POST http://localhost:8000/transcribe -F "file=@audio.mp3"

# Check status
curl http://localhost:8000/transcribe/{job_id}/status

# Get result
curl http://localhost:8000/transcribe/{job_id}

# Get segments
curl http://localhost:8000/transcribe/{job_id}/segments
```

### Docker
```bash
docker build -t transcription-pipeline .
docker run -p 8000:8000 transcription-pipeline
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /transcribe | Upload audio, returns job ID (202) |
| GET | /transcribe/{job_id} | Full result with text + timestamps |
| GET | /transcribe/{job_id}/status | Lightweight status check |
| GET | /transcribe/{job_id}/segments | Timestamped segments only |
| DELETE | /transcribe/{job_id} | Delete job and files |
| POST | /transcribe/{job_id}/retry | Retry a failed job |
| GET | /jobs | List all jobs |
| GET | /health | Health check |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| WHISPER_MODEL | base | tiny, base, small, medium, large |
| WHISPER_DEVICE | cpu | cpu or cuda |
| MAX_WORKERS | 3 | Concurrent transcription workers |
| MAX_FILE_SIZE_MB | 500 | Maximum upload size |

## Supported Formats

WAV, MP3, FLAC, OGG, M4A, AAC, WebM — all converted to 16kHz mono WAV via FFmpeg.