"""
Transcribeert audio naar tekst met faster-whisper.
Het model wordt één keer geladen en herbruikt (lazy singleton),
zodat je niet bij elke request opnieuw een groot model laadt.
"""
from faster_whisper import WhisperModel
from app.config import settings

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(
            settings.whisper_model_size,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    return _model


def transcribe_audio(audio_path: str) -> tuple[str, str]:
    """
    Transcribeert een audiobestand naar tekst.
    De taal wordt automatisch gedetecteerd door Whisper (geen vast taalcode),
    zodat dezelfde pipeline elke door Whisper ondersteunde taal kan verwerken.

    Returns:
        (transcript, detected_language_code) — bv. ("Hello world", "en")
    """
    model = _get_model()

    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        vad_filter=True,  # filtert stiltes/ruis eruit, beter voor lange audio
    )

    full_text = " ".join(segment.text.strip() for segment in segments)
    return full_text.strip(), info.language
