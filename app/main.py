"""
FastAPI applicatie: endpoints voor het analyseren van Arabische YouTube content.
"""
import uuid
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    StatusResponse,
    ResultResponse,
    JobStatus,
)
from app.services import job_store
from app.services.pipeline import run_pipeline

app = FastAPI(
    title="Arabic Content Analyzer",
    description="Download, transcribeer en vat Arabische YouTube-content samen.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    job_store.init_db()


@app.get("/")
def root():
    return {"message": "Arabic Content Analyzer API is actief."}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    job_store.create_job(job_id, str(request.youtube_url))
    background_tasks.add_task(run_pipeline, job_id, str(request.youtube_url))
    return AnalyzeResponse(job_id=job_id, status=JobStatus.PENDING)


@app.get("/status/{job_id}", response_model=StatusResponse)
def get_status(job_id: str):
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job niet gevonden.")
    return StatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress_message=job.progress_message,
        error=job.error,
    )


@app.get("/result/{job_id}", response_model=ResultResponse)
def get_result(job_id: str):
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job niet gevonden.")
    if job.status != JobStatus.DONE:
        raise HTTPException(
            status_code=409,
            detail=f"Job is nog niet klaar (huidige status: {job.status}).",
        )
    return ResultResponse(
        job_id=job.job_id,
        status=job.status,
        video_title=job.video_title,
        transcript=job.transcript,
        summary=job.summary,
        key_points=job.key_points,
    )


@app.get("/jobs")
def list_jobs(limit: int = 50):
    jobs = job_store.list_jobs(limit=limit)
    return [
        {
            "job_id": job.job_id,
            "status": job.status,
            "video_title": job.video_title,
            "youtube_url": job.youtube_url,
            "summary": job.summary,
            "key_points": job.key_points,
            "created_at": job.created_at.isoformat(),
        }
        for job in jobs
    ]
