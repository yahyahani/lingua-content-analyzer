"""
Integratietests: roepen de ECHTE yt-dlp, faster-whisper en Ollama aan.

Deze tests zijn traag (downloaden audio, laden een Whisper-model, roepen een
lokaal LLM aan) en vereisen:
  - een werkende internetverbinding
  - een lokaal draaiende Ollama-server met het geconfigureerde model
  - ffmpeg geinstalleerd

Ze draaien NIET standaard mee met `pytest`. Draai ze expliciet met:

    pytest -m integration

Geef een eigen testvideo op via een environment variable, zodat de tests niet
afhankelijk zijn van een hardcoded video-ID dat ooit verwijderd kan worden:

    TEST_YOUTUBE_URL="https://www.youtube.com/watch?v=..." pytest -m integration

Als TEST_YOUTUBE_URL niet gezet is, worden deze tests overgeslagen.
"""
import os
import pytest

pytestmark = pytest.mark.integration

TEST_YOUTUBE_URL = os.environ.get("TEST_YOUTUBE_URL")

skip_reason = (
    "TEST_YOUTUBE_URL niet gezet. Geef een korte, publieke Arabische YouTube-link op "
    "via: TEST_YOUTUBE_URL='https://...' pytest -m integration"
)


@pytest.mark.skipif(TEST_YOUTUBE_URL is None, reason=skip_reason)
def test_download_audio_produces_mp3_file():
    from app.services.downloader import download_audio
    from pathlib import Path

    audio_path, video_title = download_audio(TEST_YOUTUBE_URL, "integration-test-download")

    assert Path(audio_path).exists()
    assert Path(audio_path).suffix == ".mp3"
    assert Path(audio_path).stat().st_size > 0
    assert isinstance(video_title, str) and len(video_title) > 0

    # Opruimen
    Path(audio_path).unlink(missing_ok=True)


@pytest.mark.skipif(TEST_YOUTUBE_URL is None, reason=skip_reason)
def test_transcribe_audio_returns_arabic_text():
    from app.services.downloader import download_audio
    from app.services.transcriber import transcribe_audio
    from pathlib import Path

    audio_path, _ = download_audio(TEST_YOUTUBE_URL, "integration-test-transcribe")

    try:
        transcript = transcribe_audio(audio_path)

        assert isinstance(transcript, str)
        assert len(transcript.strip()) > 0
        # Check dat er Arabische karakters in zitten (range U+0600–U+06FF)
        assert any("\u0600" <= ch <= "\u06ff" for ch in transcript)
    finally:
        Path(audio_path).unlink(missing_ok=True)


@pytest.mark.skipif(TEST_YOUTUBE_URL is None, reason=skip_reason)
def test_summarize_text_returns_summary_and_key_points():
    from app.services.summarizer import summarize_text

    sample_text = (
        "هذا نص تجريبي قصير لاختبار وظيفة التلخيص. "
        "يتحدث هذا النص عن أهمية اختبار البرمجيات بشكل جيد. "
        "كما يوضح أن الاختبارات تساعد في اكتشاف الأخطاء مبكرًا."
    )

    result = summarize_text(sample_text)

    assert "summary" in result
    assert "key_points" in result
    assert isinstance(result["summary"], str)
    assert len(result["summary"]) > 0
    assert isinstance(result["key_points"], list)


@pytest.mark.skipif(TEST_YOUTUBE_URL is None, reason=skip_reason)
def test_full_pipeline_end_to_end(client):
    """
    De ultieme test: roept de echte /analyze endpoint aan en polled tot de
    job klaar is, met de echte download/transcribe/summarize pipeline.
    Dit kan meerdere minuten duren afhankelijk van videolengte en hardware.
    """
    import time
    from app.models.schemas import JobStatus

    response = client.post("/analyze", json={"youtube_url": TEST_YOUTUBE_URL})
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    max_wait_seconds = 600  # 10 minuten, ruim voldoende voor een korte video
    poll_interval = 5
    elapsed = 0

    final_status = None
    while elapsed < max_wait_seconds:
        status_response = client.get(f"/status/{job_id}")
        assert status_response.status_code == 200
        final_status = status_response.json()["status"]

        if final_status in (JobStatus.DONE.value, JobStatus.FAILED.value):
            break

        time.sleep(poll_interval)
        elapsed += poll_interval

    assert final_status == JobStatus.DONE.value, (
        f"Pipeline eindigde met status '{final_status}' in plaats van 'done' "
        f"binnen {max_wait_seconds} seconden."
    )

    result_response = client.get(f"/result/{job_id}")
    assert result_response.status_code == 200
    result = result_response.json()
    assert result["transcript"]
    assert result["summary"]
    assert isinstance(result["key_points"], list)
