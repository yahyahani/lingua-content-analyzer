"""
Tests voor de FastAPI endpoints in app.main.

De pipeline (download/transcribe/summarize) wordt hier gemockt zodat deze
tests snel en zonder externe dependencies (YouTube, Whisper, Ollama) draaien.
Voor tests die de echte pipeline aanroepen, zie test_pipeline_integration.py.
"""
from unittest.mock import patch
from app.models.schemas import JobStatus, SummaryLanguage


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "actief" in response.json()["message"]


def test_analyze_returns_job_id_and_pending_status(client):
    with patch("app.main.run_pipeline") as mock_pipeline:
        response = client.post(
            "/analyze",
            json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"
    # De pipeline wordt aangeroepen als background task; met TestClient
    # draait die synchroon na de response, dus we checken dat hij is aangeroepen
    # met de juiste argumenten in plaats van de echte download/transcribe/summarize.
    mock_pipeline.assert_called_once()
    called_job_id, called_url, called_language = mock_pipeline.call_args[0]
    assert called_job_id == data["job_id"]
    assert called_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert called_language == SummaryLanguage.ENGLISH  # default


def test_analyze_accepts_explicit_summary_language(client):
    with patch("app.main.run_pipeline") as mock_pipeline:
        response = client.post(
            "/analyze",
            json={
                "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "summary_language": "fr",
            },
        )

    assert response.status_code == 200
    _, _, called_language = mock_pipeline.call_args[0]
    assert called_language == SummaryLanguage.FRENCH


def test_analyze_rejects_unsupported_summary_language(client):
    response = client.post(
        "/analyze",
        json={
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "summary_language": "ja",  # niet in de ondersteunde lijst
        },
    )
    assert response.status_code == 422


def test_analyze_rejects_invalid_url(client):
    response = client.post("/analyze", json={"youtube_url": "niet-een-url"})
    assert response.status_code == 422


def test_analyze_rejects_missing_url(client):
    response = client.post("/analyze", json={})
    assert response.status_code == 422


def test_status_for_unknown_job_returns_404(client):
    response = client.get("/status/does-not-exist")
    assert response.status_code == 404
    assert "niet gevonden" in response.json()["detail"]


def test_status_for_known_job_returns_its_status(client):
    from app.services import job_store

    job_store.create_job("known-job", "https://youtube.com/watch?v=abc")
    job_store.update_job("known-job", status=JobStatus.TRANSCRIBING, progress_message="bezig")

    response = client.get("/status/known-job")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "transcribing"
    assert data["progress_message"] == "bezig"


def test_result_for_unknown_job_returns_404(client):
    response = client.get("/result/does-not-exist")
    assert response.status_code == 404


def test_result_for_unfinished_job_returns_409(client):
    from app.services import job_store

    job_store.create_job("unfinished-job", "https://youtube.com/watch?v=abc")
    job_store.update_job("unfinished-job", status=JobStatus.DOWNLOADING)

    response = client.get("/result/unfinished-job")

    assert response.status_code == 409
    # De foutmelding moet de schone status-waarde tonen, niet de Python repr
    # zoals "JobStatus.DOWNLOADING" — regressietest voor die specifieke bug.
    assert "downloading" in response.json()["detail"]
    assert "JobStatus" not in response.json()["detail"]


def test_result_for_completed_job_returns_full_data(client):
    from app.services import job_store

    job_store.create_job("done-job", "https://youtube.com/watch?v=abc")
    job_store.update_job(
        "done-job",
        status=JobStatus.DONE,
        video_title="Testvideo",
        transcript="Dit is het transcript.",
        summary="Dit is de samenvatting.",
        key_points=["punt 1", "punt 2"],
    )

    response = client.get("/result/done-job")

    assert response.status_code == 200
    data = response.json()
    assert data["video_title"] == "Testvideo"
    assert data["transcript"] == "Dit is het transcript."
    assert data["summary"] == "Dit is de samenvatting."
    assert data["key_points"] == ["punt 1", "punt 2"]
    assert data["youtube_url"] == "https://youtube.com/watch?v=abc"
    assert "created_at" in data


def test_jobs_endpoint_returns_empty_list_when_no_jobs(client):
    response = client.get("/jobs")
    assert response.status_code == 200
    assert response.json() == []


def test_jobs_endpoint_returns_history_newest_first(client):
    from app.services import job_store

    job_store.create_job("old-job", "https://youtube.com/watch?v=old")
    job_store.create_job("new-job", "https://youtube.com/watch?v=new")

    response = client.get("/jobs")

    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 2
    assert jobs[0]["job_id"] == "new-job"


def test_jobs_endpoint_respects_limit_param(client):
    from app.services import job_store

    for i in range(5):
        job_store.create_job(f"job-{i}", f"https://youtube.com/watch?v={i}")

    response = client.get("/jobs?limit=2")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_cors_headers_present(client):
    response = client.get("/jobs", headers={"Origin": "http://localhost:5500"})
    assert response.headers.get("access-control-allow-origin") == "*"


def test_delete_job_removes_it_from_history(client):
    from app.services import job_store

    job_store.create_job("to-delete", "https://youtube.com/watch?v=del")

    response = client.delete("/jobs/to-delete")

    assert response.status_code == 200
    assert response.json() == {"job_id": "to-delete", "deleted": True}
    assert job_store.get_job("to-delete") is None


def test_delete_unknown_job_returns_404(client):
    response = client.delete("/jobs/does-not-exist")
    assert response.status_code == 404


def test_delete_job_removes_audio_file_if_present(client, tmp_path):
    from app.services import job_store

    audio_file = tmp_path / "fake-audio.mp3"
    audio_file.write_text("fake audio content")

    job_store.create_job("with-audio", "https://youtube.com/watch?v=audio")
    job_store.update_job("with-audio", audio_path=str(audio_file))

    response = client.delete("/jobs/with-audio")

    assert response.status_code == 200
    assert not audio_file.exists()
