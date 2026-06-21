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
