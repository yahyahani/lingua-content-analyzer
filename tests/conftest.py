"""
Gedeelde pytest-fixtures.

Belangrijk: we zetten STORAGE_DIR naar een tijdelijke map VOORDAT de app
of job_store geïmporteerd wordt, zodat tests nooit de echte storage/jobs.db
aanraken.
"""
import os
import shutil
import tempfile
import pytest

# Moet vóór elke import van app.* gebeuren, anders pakt pydantic-settings
# de echte storage_dir uit .env of de default.
_TEST_STORAGE_DIR = tempfile.mkdtemp(prefix="arabic_analyzer_test_")
os.environ["STORAGE_DIR"] = _TEST_STORAGE_DIR


@pytest.fixture(autouse=True)
def clean_database():
    """
    Zorgt dat elke test met een schone database begint.
    autouse=True betekent dat dit voor ELKE test automatisch draait.
    """
    from app.services import job_store

    job_store.init_db()
    yield
    # Opruimen na de test: verwijder en heranmaak de db-file
    db_path = job_store._DB_PATH
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def client():
    """FastAPI test client, gebruikt requests-achtige syntax zonder een echte server te starten."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def pytest_sessionfinish(session, exitstatus):
    """Opruimen van de tijdelijke test-storage-map na de volledige testrun."""
    shutil.rmtree(_TEST_STORAGE_DIR, ignore_errors=True)
