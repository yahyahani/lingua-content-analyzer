"""
Data modellen voor requests, responses en interne job-state.
"""
from pydantic import BaseModel, HttpUrl, Field
from enum import Enum
from typing import Optional
from datetime import datetime


class JobStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    SUMMARIZING = "summarizing"
    DONE = "done"
    FAILED = "failed"


class SummaryLanguage(str, Enum):
    """
    Talen waarin de samenvatting geschreven kan worden, los van de taal
    van de video zelf (die Whisper automatisch detecteert).
    """
    ENGLISH = "en"
    FRENCH = "fr"
    SPANISH = "es"
    GERMAN = "de"
    ARABIC = "ar"
    DUTCH = "nl"


# Mensleesbare namen per taal, gebruikt in de prompt naar het samenvattingsmodel
SUMMARY_LANGUAGE_NAMES = {
    SummaryLanguage.ENGLISH: "English",
    SummaryLanguage.FRENCH: "French",
    SummaryLanguage.SPANISH: "Spanish",
    SummaryLanguage.GERMAN: "German",
    SummaryLanguage.ARABIC: "Arabic",
    SummaryLanguage.DUTCH: "Dutch",
}


class AnalyzeRequest(BaseModel):
    youtube_url: HttpUrl
    # Taal van de SAMENVATTING, niet van de video. De video-taal wordt
    # automatisch gedetecteerd door Whisper. Standaard Engels.
    summary_language: SummaryLanguage = SummaryLanguage.ENGLISH


class AnalyzeResponse(BaseModel):
    job_id: str
    status: JobStatus


class StatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress_message: Optional[str] = None
    error: Optional[str] = None


class ResultResponse(BaseModel):
    job_id: str
    status: JobStatus
    youtube_url: str
    video_title: Optional[str] = None
    detected_language: Optional[str] = None
    summary_language: Optional[SummaryLanguage] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    key_points: Optional[list[str]] = None
    created_at: datetime


class Job(BaseModel):
    """Interne representatie van een job, bijgehouden in memory."""
    job_id: str
    status: JobStatus = JobStatus.PENDING
    youtube_url: str
    summary_language: SummaryLanguage = SummaryLanguage.ENGLISH
    video_title: Optional[str] = None
    audio_path: Optional[str] = None
    detected_language: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    key_points: Optional[list[str]] = None
    error: Optional[str] = None
    progress_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
