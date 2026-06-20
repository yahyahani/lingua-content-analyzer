"""
Persistente opslag van jobs in SQLite.
"""
import json
import sqlite3
from datetime import datetime
from threading import Lock

from app.models.schemas import Job, JobStatus
from app.config import settings

_DB_PATH = settings.storage_dir / "jobs.db"
_lock = Lock()


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _lock, _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                youtube_url TEXT NOT NULL,
                video_title TEXT,
                audio_path TEXT,
                transcript TEXT,
                summary TEXT,
                key_points TEXT,
                error TEXT,
                progress_message TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        job_id=row["job_id"],
        status=JobStatus(row["status"]),
        youtube_url=row["youtube_url"],
        video_title=row["video_title"],
        audio_path=row["audio_path"],
        transcript=row["transcript"],
        summary=row["summary"],
        key_points=json.loads(row["key_points"]) if row["key_points"] else None,
        error=row["error"],
        progress_message=row["progress_message"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def create_job(job_id: str, youtube_url: str) -> Job:
    job = Job(job_id=job_id, youtube_url=youtube_url)
    with _lock, _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_id, status, youtube_url, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (job.job_id, job.status.value, job.youtube_url, job.created_at.isoformat()),
        )
        conn.commit()
    return job


def get_job(job_id: str) -> Job | None:
    with _lock, _get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None


def list_jobs(limit: int = 50) -> list[Job]:
    with _lock, _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_job(row) for row in rows]


def update_job(job_id: str, **fields) -> None:
    if not fields:
        return

    if "key_points" in fields and fields["key_points"] is not None:
        fields["key_points"] = json.dumps(fields["key_points"], ensure_ascii=False)

    if "status" in fields and isinstance(fields["status"], JobStatus):
        fields["status"] = fields["status"].value

    set_clause = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [job_id]

    with _lock, _get_connection() as conn:
        conn.execute(f"UPDATE jobs SET {set_clause} WHERE job_id = ?", values)
        conn.commit()
