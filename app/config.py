import os

SUPPORTED_FORMATS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".webm"}
CHUNK_MINUTES = 10
MAX_FILE_SIZE_MB = 500

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "storage/uploads")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")

MAX_RETRIES = 3
RETRY_DELAYS = [10, 30, 90]

MAX_CONCURRENT_WORKERS = int(os.getenv("MAX_WORKERS", "3"))