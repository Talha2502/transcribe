import os
import uuid
import shutil

from fastapi import FastAPI, UploadFile, File, HTTPException

from app import database as db
from app import worker
from app.config import SUPPORTED_FORMATS, UPLOAD_DIR, MAX_FILE_SIZE_MB

app = FastAPI(title="Transcription Pipeline API", version="1.0.0")


@app.on_event("startup")
def startup():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    db.init_db()


@app.post("/transcribe", status_code=202)
async def create_transcription(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=422, detail=f"Unsupported format '{ext}'")

    file.file.seek(0, 2)
    size_mb = file.file.tell() / (1024 * 1024)
    file.file.seek(0)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=422, detail=f"File too large ({size_mb:.1f} MB)")

    job_id = str(uuid.uuid4())
    save_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"original{ext}")

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    db.create_job(job_id, file.filename, save_path)
    worker.submit_job(job_id)

    return {"id": job_id, "status": "queued"}


@app.get("/transcribe/{job_id}")
async def get_transcription(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/transcribe/{job_id}/status")
async def get_status(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"id": job["id"], "status": job["status"], "error": job.get("error")}


@app.get("/transcribe/{job_id}/segments")
async def get_segments(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job is '{job['status']}', not completed yet")
    return {"job_id": job_id, "segments": job.get("segments", [])}


@app.delete("/transcribe/{job_id}")
async def delete_transcription(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    upload_dir = os.path.join(UPLOAD_DIR, job_id)
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)

    db.delete_job(job_id)
    return {"detail": "Job deleted", "job_id": job_id}


@app.post("/transcribe/{job_id}/retry")
async def retry_transcription(job_id: str):
    success = worker.retry_failed_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Job not found or not failed")
    return {"id": job_id, "status": "queued"}


@app.get("/jobs")
async def list_jobs(status: str = None):
    jobs = db.get_all_jobs(status=status)
    return {"count": len(jobs), "jobs": jobs}


@app.get("/health")
async def health():
    return {"status": "ok"}