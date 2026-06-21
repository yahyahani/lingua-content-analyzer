"""
Orkestreert de volledige pipeline: download -> transcribe -> summarize.
Wordt als background task aangeroepen vanuit de API.
"""
from app.models.schemas import JobStatus, SummaryLanguage
from app.services import job_store
from app.services.downloader import download_audio
from app.services.transcriber import transcribe_audio
from app.services.summarizer import summarize_text


def run_pipeline(
    job_id: str,
    youtube_url: str,
    summary_language: SummaryLanguage = SummaryLanguage.ENGLISH,
) -> None:
    try:
        job_store.update_job(
            job_id,
            status=JobStatus.DOWNLOADING,
            progress_message="Downloading audio from the video...",
        )
        audio_path, video_title = download_audio(youtube_url, job_id)
        job_store.update_job(job_id, audio_path=audio_path, video_title=video_title)

        job_store.update_job(
            job_id,
            status=JobStatus.TRANSCRIBING,
            progress_message="Transcribing audio to text...",
        )
        transcript, detected_language = transcribe_audio(audio_path)
        job_store.update_job(job_id, transcript=transcript, detected_language=detected_language)

        job_store.update_job(
            job_id,
            status=JobStatus.SUMMARIZING,
            progress_message="Summarizing the text...",
        )
        result = summarize_text(transcript, summary_language=summary_language)

        job_store.update_job(
            job_id,
            status=JobStatus.DONE,
            summary=result["summary"],
            key_points=result["key_points"],
            progress_message="Completed successfully.",
        )

    except Exception as e:
        job_store.update_job(
            job_id,
            status=JobStatus.FAILED,
            error=str(e),
        )
