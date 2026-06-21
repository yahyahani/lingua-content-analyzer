"""
Persistente opslag van jobs in SQLite.

We gebruiken een echte database (i.p.v. een in-memory dict) om twee redenen:
1. Robuustheid: bij een server-restart (bijv. door --reload tijdens
   ontwikkelen) gaat de geschiedenis niet verloren.
2. Het dashboard heeft een geschiedenis van analyses nodig; die moet
   blijven bestaan tussen sessies.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock

from app.models.schemas import Job, JobStatus, SummaryLanguage
from app.config import settings

_DB_PATH = settings.storage_dir / "jobs.db"
_lock = Lock()


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """
    Voegt kolommen toe die in een latere versie zijn geïntroduceerd, zodat
    een bestaande database (van vóór de taalondersteuning) niet stuk loopt.
    SQLite heeft geen "ADD COLUMN IF NOT EXISTS", dus we checken het schema zelf.
    """
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}

    if "summary_language" not in existing_columns:
        conn.execute(
            f"ALTER TABLE jobs ADD COLUMN summary_language TEXT NOT NULL DEFAULT '{SummaryLanguage.ENGLISH.value}'"
        )
    if "detected_language" not in existing_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN detected_language TEXT")

    conn.commit()


def init_db() -> None:
    """Maakt de jobs-tabel aan als die nog niet bestaat, en migreert bestaande tabellen. Wordt bij app-startup aangeroepen."""
    with _lock, _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                youtube_url TEXT NOT NULL,
                summary_language TEXT NOT NULL DEFAULT 'en',
                video_title TEXT,
                audio_path TEXT,
                detected_language TEXT,
                transcript TEXT,
                summary TEXT,
                key_points TEXT,
                error TEXT,
                progress_message TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        _migrate_schema(conn)


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        job_id=row["job_id"],
        status=JobStatus(row["status"]),
        youtube_url=row["youtube_url"],
        summary_language=SummaryLanguage(row["summary_language"]),
        video_title=row["video_title"],
        audio_path=row["audio_path"],
        detected_language=row["detected_language"],
        transcript=row["transcript"],
        summary=row["summary"],
        key_points=json.loads(row["key_points"]) if row["key_points"] else None,
        error=row["error"],
        progress_message=row["progress_message"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def create_job(
    job_id: str,
    youtube_url: str,
    summary_language: SummaryLanguage = SummaryLanguage.ENGLISH,
) -> Job:
    job = Job(job_id=job_id, youtube_url=youtube_url, summary_language=summary_language)
    with _lock, _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_id, status, youtube_url, summary_language, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                job.job_id,
                job.status.value,
                job.youtube_url,
                job.summary_language.value,
                job.created_at.isoformat(),
            ),
        )
        conn.commit()
    return job


def get_job(job_id: str) -> Job | None:
    with _lock, _get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None


def list_jobs(limit: int = 50) -> list[Job]:
    """Geeft de meest recente jobs terug, nieuwste eerst. Gebruikt door het dashboard."""
    with _lock, _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_job(row) for row in rows]


def update_job(job_id: str, **fields) -> None:
    if not fields:
        return

    # key_points is een lijst in Python maar moet als JSON-string opgeslagen worden
    if "key_points" in fields and fields["key_points"] is not None:
        fields["key_points"] = json.dumps(fields["key_points"], ensure_ascii=False)

    # status en summary_language kunnen enums zijn; sqlite wil de string-waarde
    if "status" in fields and isinstance(fields["status"], JobStatus):
        fields["status"] = fields["status"].value
    if "summary_language" in fields and isinstance(fields["summary_language"], SummaryLanguage):
        fields["summary_language"] = fields["summary_language"].value

    set_clause = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [job_id]

    with _lock, _get_connection() as conn:
        conn.execute(f"UPDATE jobs SET {set_clause} WHERE job_id = ?", values)
        conn.commit()


def delete_job(job_id: str) -> bool:
    """
    Verwijdert een job uit de database.
    Geeft True terug als er een rij verwijderd is, False als de job niet bestond.
    """
    with _lock, _get_connection() as conn:
        cursor = conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        conn.commit()
        return cursor.rowcount > 0
