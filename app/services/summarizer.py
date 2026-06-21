"""
Vat tekst samen met een lokaal LLM via Ollama, in een gekozen doeltaal.
De brontekst kan in elke taal zijn (die Whisper heeft gedetecteerd);
de samenvatting wordt geschreven in summary_language.
"""
import json
import ollama
from app.config import settings
from app.models.schemas import SummaryLanguage, SUMMARY_LANGUAGE_NAMES

SUMMARY_PROMPT = """You are an assistant specialized in summarizing transcripts.
The text below may be in any language. Read it and write your response
ENTIRELY in {target_language}, regardless of the source language:

1. A concise summary in 3-5 sentences.
2. A list of 3 to 6 key points.

Respond ONLY in this exact JSON format, with no extra text before or after:
{{"summary": "...", "key_points": ["...", "..."]}}

Text:
{text}
"""


def summarize_text(text: str, summary_language: SummaryLanguage = SummaryLanguage.ENGLISH) -> dict:
    """
    Stuurt de tekst naar het lokale Ollama model en parsed het
    JSON-antwoord met summary en key_points, geschreven in summary_language.
    """
    client = ollama.Client(host=settings.ollama_host)

    target_language_name = SUMMARY_LANGUAGE_NAMES[summary_language]

    response = client.chat(
        model=settings.ollama_model,
        messages=[{
            "role": "user",
            "content": SUMMARY_PROMPT.format(target_language=target_language_name, text=text),
        }],
        format="json",
    )

    content = response["message"]["content"]

    try:
        parsed = json.loads(content)
        return {
            "summary": parsed.get("summary", ""),
            "key_points": parsed.get("key_points", []),
        }
    except json.JSONDecodeError:
        # Fallback: als het model geen geldige JSON teruggeeft,
        # geven we de ruwe tekst terug als summary.
        return {"summary": content, "key_points": []}
