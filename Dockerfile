# syntax=docker/dockerfile:1
FROM python:3.12-slim

# ffmpeg is nodig voor yt-dlp's audio-extractie (FFmpegExtractAudio postprocessor)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies eerst kopiëren en installeren, zodat Docker deze laag cachet
# en niet bij elke codewijziging opnieuw alle packages installeert.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY dashboard/ ./dashboard/

# Storage-map voor audio en de SQLite-database; wordt normaal als volume gemount
RUN mkdir -p storage

EXPOSE 8000

# Ollama draait op de hostmachine (heeft GPU/Metal-acceleratie nodig die niet
# goed werkt in een container op macOS), dus de container praat ermee via
# host.docker.internal. Dit kan overschreven worden via docker-compose of -e.
ENV OLLAMA_HOST=http://host.docker.internal:11434

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
