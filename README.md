# Arabic Content Analyzer

Een tool die Arabische YouTube-video's automatisch transcribeert en samenvat.
Geef een YouTube-link op, en de tool downloadt de audio, transcribeert deze
naar Arabische tekst (via Whisper) en genereert een samenvatting met
belangrijkste punten (via een lokaal LLM met Ollama).

Inclusief een dashboard in manuscript-stijl met live voortgang en een
geschiedenis van eerdere analyses, elk met een detailpagina die het volledige
transcript toont.

## Waarom dit project?

Arabische NLP-tools zijn schaars vergeleken met Engelstalige tools. Dit project
combineert speech-to-text en samenvatting specifiek geoptimaliseerd voor
Arabische content (podcasts, lezingen, interviews, nieuws).

## Architectuur

```
YouTube URL --> yt-dlp (audio download) --> faster-whisper (transcriptie)
            --> Ollama / lokaal LLM (samenvatting) --> SQLite (opslag)
                                                     --> Dashboard (HTML/JS)
```

De verwerking draait asynchroon: je krijgt direct een `job_id` terug en kunt
de status pollen totdat de job klaar is. Alle jobs worden persistent
opgeslagen in SQLite, dus de geschiedenis blijft bestaan tussen herstarts.

## Vereisten

- Python 3.10+ (voor lokaal draaien) of Docker (voor containerized draaien)
- [Ollama](https://ollama.com) geinstalleerd en draaiend op de hostmachine
- ffmpeg geinstalleerd (nodig voor audio-extractie door yt-dlp) — alleen bij lokaal draaien; in Docker is dit al meegenomen

## Optie A: Lokaal draaien

```bash
# 1. Virtuele omgeving aanmaken
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Dependencies installeren
pip install -r requirements.txt

# 3. Ollama model downloaden
ollama pull qwen2.5:7b

# 4. .env aanmaken (optioneel, anders worden defaults gebruikt)
cp .env.example .env
```

Start de server:

```bash
uvicorn app.main:app --reload
```

Open het dashboard door `dashboard/index.html` in je browser te openen
(bijvoorbeeld via `open dashboard/index.html` op macOS).

## Optie B: Draaien met Docker

Ollama draait op de hostmachine (niet in de container), omdat het GPU/Metal-
acceleratie nodig heeft die in een container op macOS niet goed werkt. De
container praat met Ollama via `host.docker.internal`.

```bash
# 1. Zorg dat Ollama op je host draait met het juiste model
ollama pull qwen2.5:7b
ollama serve

# 2. Build en start de container
docker compose up --build
```

De API draait nu op `http://localhost:8000`, met dezelfde endpoints als bij
lokaal draaien. Audio-bestanden en de database worden opgeslagen in `./storage`
op je host (gemount als volume), dus je verliest geen data bij een restart.

Stoppen:
```bash
docker compose down
```

Het dashboard (`dashboard/index.html`) werkt op precies dezelfde manier,
onafhankelijk van of de backend in Docker of lokaal draait — open het bestand
gewoon in je browser.

## De API

Interactieve documentatie (Swagger) is te vinden op `http://localhost:8000/docs`.

### 1. Start een analyse

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID"}'
```

Antwoord:
```json
{"job_id": "abc-123", "status": "pending"}
```

### 2. Status checken

```bash
curl http://localhost:8000/status/abc-123
```

### 3. Resultaat ophalen (zodra status "done" is)

```bash
curl http://localhost:8000/result/abc-123
```

Antwoord:
```json
{
  "job_id": "abc-123",
  "status": "done",
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "video_title": "...",
  "transcript": "...",
  "summary": "...",
  "key_points": ["...", "..."],
  "created_at": "2026-06-21T00:04:27.697618"
}
```

### 4. Geschiedenis van alle analyses

```bash
curl http://localhost:8000/jobs
```

## Tests

Het project heeft twee soorten tests:

- **Unit- en API-tests** (`tests/test_job_store.py`, `tests/test_api.py`):
  snel, geen externe dependencies, mocken de pipeline. Draaien standaard mee.
- **Integratietests** (`tests/test_pipeline_integration.py`): roepen de
  echte yt-dlp, Whisper en Ollama aan. Traag, vereisen netwerk en een
  draaiende Ollama-server. Draaien NIET standaard mee.

Dependencies installeren:
```bash
pip install -r requirements-dev.txt
```

Snelle tests draaien (dit is wat je normaal gebruikt):
```bash
pytest
```

Integratietests draaien (vereist een korte, publieke Arabische YouTube-link):
```bash
TEST_YOUTUBE_URL="https://www.youtube.com/watch?v=..." pytest -m integration
```

## Roadmap

- [x] Persistente opslag (SQLite i.p.v. in-memory)
- [x] Dashboard met geschiedenis
- [x] Detailpagina met volledig transcript
- [x] Docker-ondersteuning
- [ ] Sentiment-analyse van reacties/transcript
- [ ] Ondersteuning voor meerdere Arabische dialecten
- [ ] Ondersteuning voor lokale audiobestanden naast YouTube-links
- [ ] Timestamps koppelen aan key points

## Licentie

MIT
