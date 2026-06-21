"""
Tests voor app.services.job_store — de persistente SQLite-laag.
"""
from app.services import job_store
from app.models.schemas import JobStatus


def test_create_job_returns_pending_job():
    job = job_store.create_job("job-1", "https://youtube.com/watch?v=abc")

    assert job.job_id == "job-1"
    assert job.youtube_url == "https://youtube.com/watch?v=abc"
    assert job.status == JobStatus.PENDING


def test_get_job_returns_none_for_unknown_id():
    assert job_store.get_job("does-not-exist") is None


def test_get_job_returns_created_job():
    job_store.create_job("job-2", "https://youtube.com/watch?v=xyz")

    fetched = job_store.get_job("job-2")

    assert fetched is not None
    assert fetched.job_id == "job-2"
    assert fetched.status == JobStatus.PENDING


def test_update_job_changes_status():
    job_store.create_job("job-3", "https://youtube.com/watch?v=1")
    job_store.update_job("job-3", status=JobStatus.DOWNLOADING)

    job = job_store.get_job("job-3")
    assert job.status == JobStatus.DOWNLOADING


def test_update_job_persists_key_points_as_list():
    job_store.create_job("job-4", "https://youtube.com/watch?v=2")
    job_store.update_job(
        "job-4",
        status=JobStatus.DONE,
        summary="Een testsamenvatting.",
        key_points=["punt een", "punt twee", "punt drie"],
    )

    job = job_store.get_job("job-4")
    assert job.status == JobStatus.DONE
    assert job.summary == "Een testsamenvatting."
    assert job.key_points == ["punt een", "punt twee", "punt drie"]


def test_update_job_on_unknown_id_does_not_raise():
    # Moet stil niets doen, geen exception, want er is geen rij om te updaten.
    job_store.update_job("ghost-job", status=JobStatus.FAILED)
    assert job_store.get_job("ghost-job") is None


def test_update_job_with_no_fields_is_noop():
    job_store.create_job("job-5", "https://youtube.com/watch?v=3")
    job_store.update_job("job-5")  # geen kwargs

    job = job_store.get_job("job-5")
    assert job.status == JobStatus.PENDING


def test_list_jobs_returns_newest_first():
    job_store.create_job("older", "https://youtube.com/watch?v=old")
    job_store.create_job("newer", "https://youtube.com/watch?v=new")

    jobs = job_store.list_jobs()

    assert len(jobs) == 2
    assert jobs[0].job_id == "newer"
    assert jobs[1].job_id == "older"


def test_list_jobs_respects_limit():
    for i in range(5):
        job_store.create_job(f"job-{i}", f"https://youtube.com/watch?v={i}")

    jobs = job_store.list_jobs(limit=3)

    assert len(jobs) == 3


def test_list_jobs_empty_database_returns_empty_list():
    assert job_store.list_jobs() == []


def test_job_data_persists_across_new_connections():
    """
    Regressietest voor de oorspronkelijke --reload bug: data moet persistent
    zijn, niet afhankelijk van een in-memory dict die bij een nieuw proces leeg is.
    """
    job_store.create_job("persistent-job", "https://youtube.com/watch?v=persist")
    job_store.update_job("persistent-job", status=JobStatus.DONE, summary="Blijft bestaan")

    # Simuleer een "nieuwe request" door een verse connectie te openen
    # (get_job opent zelf altijd een nieuwe sqlite3.connect, dus dit dekt het al af)
    job = job_store.get_job("persistent-job")
    assert job.status == JobStatus.DONE
    assert job.summary == "Blijft bestaan"


def test_create_job_with_explicit_summary_language():
    from app.models.schemas import SummaryLanguage

    job = job_store.create_job(
        "lang-job", "https://youtube.com/watch?v=x", summary_language=SummaryLanguage.FRENCH
    )

    assert job.summary_language == SummaryLanguage.FRENCH
    fetched = job_store.get_job("lang-job")
    assert fetched.summary_language == SummaryLanguage.FRENCH


def test_create_job_without_summary_language_defaults_to_english():
    from app.models.schemas import SummaryLanguage

    job = job_store.create_job("default-lang-job", "https://youtube.com/watch?v=y")

    assert job.summary_language == SummaryLanguage.ENGLISH


def test_update_job_persists_detected_language():
    job_store.create_job("detect-job", "https://youtube.com/watch?v=z")
    job_store.update_job("detect-job", detected_language="fr")

    job = job_store.get_job("detect-job")
    assert job.detected_language == "fr"


def test_migration_adds_missing_columns_to_old_schema(tmp_path, monkeypatch):
    """
    Regressietest: een database aangemaakt vóór de taalondersteuning (zonder
    summary_language/detected_language kolommen) moet zonder crash migreren,
    en bestaande rijen moeten een zinnige default krijgen.
    """
    import sqlite3
    from app.config import settings

    old_db_path = settings.storage_dir / "jobs.db"

    # Verwijder de huidige (al gemigreerde) db en bouw een "oude" variant op.
    if old_db_path.exists():
        old_db_path.unlink()

    conn = sqlite3.connect(old_db_path)
    conn.execute("""
        CREATE TABLE jobs (
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
    conn.execute("""
        INSERT INTO jobs (job_id, status, youtube_url, created_at)
        VALUES ('legacy-job', 'done', 'https://youtube.com/watch?v=legacy', '2026-01-01T00:00:00')
    """)
    conn.commit()
    conn.close()

    # init_db() moet de ontbrekende kolommen toevoegen zonder de oude rij te verliezen
    job_store.init_db()

    job = job_store.get_job("legacy-job")
    assert job is not None
    assert job.summary_language.value == "en"  # default voor bestaande rijen
    assert job.detected_language is None


def test_delete_job_returns_true_when_deleted():
    job_store.create_job("delete-me", "https://youtube.com/watch?v=x")

    result = job_store.delete_job("delete-me")

    assert result is True
    assert job_store.get_job("delete-me") is None


def test_delete_job_returns_false_for_unknown_id():
    result = job_store.delete_job("never-existed")
    assert result is False


def test_delete_job_does_not_affect_other_jobs():
    job_store.create_job("keep-me", "https://youtube.com/watch?v=keep")
    job_store.create_job("remove-me", "https://youtube.com/watch?v=remove")

    job_store.delete_job("remove-me")

    assert job_store.get_job("keep-me") is not None
    assert job_store.get_job("remove-me") is None
