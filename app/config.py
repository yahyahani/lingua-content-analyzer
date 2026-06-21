"""
Centrale configuratie voor de applicatie.
Alle instellingen kunnen via een .env bestand overschreven worden.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # Map waar gedownloade audio en transcripten tijdelijk opgeslagen worden
    storage_dir: Path = Path("storage")

    # Whisper instellingen
    whisper_model_size: str = "medium"  # tiny, base, small, medium, large-v3
    whisper_device: str = "cpu"  # of "cuda" als je een GPU hebt
    whisper_compute_type: str = "int8"  # int8 is sneller op cpu, float16 voor gpu

    # Ollama instellingen
    ollama_model: str = "qwen2.5:7b"
    ollama_host: str = "http://localhost:11434"


settings = Settings()

# Zorg dat de storage map bestaat
settings.storage_dir.mkdir(parents=True, exist_ok=True)
