import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor

from app import database as db
from app.transcriber import transcribe_file
from app.config import MAX_RETRIES, RETRY_DELAYS, MAX_CONCURRENT_WORKERS

_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_WORKERS)


def submit_job(job_id):
    _executor.submit(_process_job, job_id)


def _process_job(job_id):
    job = db.get_job(job_id)
    if not job:
        return

    db.update_job(job_id, status="processing")
    print(f"[Worker] Processing job {job_id}: {job['original_filename']}")

    retry_count = job.get("retry_count", 0)

    while retry_count <= MAX_RETRIES:
        try:
            result = transcribe_file(job["audio_path"])

            db.update_job(
                job_id,
                status="completed",
                full_text=result["full_text"],
                segments=json.dumps(result["segments"]),
                language=result["language"],
                language_confidence=result["language_confidence"],
                duration_seconds=result["duration_seconds"],
                retry_count=retry_count
            )
            print(f"[Worker] Job {job_id} completed successfully")
            return

        except Exception as e:
            retry_count += 1
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"[Worker] Job {job_id} failed (attempt {retry_count}/{MAX_RETRIES + 1}): {error_msg}")

            if retry_count <= MAX_RETRIES:
                delay = RETRY_DELAYS[min(retry_count - 1, len(RETRY_DELAYS) - 1)]
                print(f"[Worker] Retrying in {delay}s...")
                db.update_job(job_id, status="retrying", error=error_msg, retry_count=retry_count)
                time.sleep(delay)
            else:
                db.update_job(
                    job_id,
                    status="failed",
                    error=error_msg,
                    retry_count=retry_count
                )
                print(f"[Worker] Job {job_id} permanently failed")


def retry_failed_job(job_id):
    job = db.get_job(job_id)
    if not job or job["status"] != "failed":
        return False

    db.update_job(job_id, status="queued", error=None, retry_count=0)
    submit_job(job_id)
    return True