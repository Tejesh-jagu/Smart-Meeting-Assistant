import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[1] / ".env")

REQUIRED_DATABASE_SETTINGS = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD")
missing_database_settings = [
    name for name in REQUIRED_DATABASE_SETTINGS
    if name not in os.environ or (name != "PGPASSWORD" and not os.environ[name])
]
if missing_database_settings:
    raise RuntimeError(
        "Missing required PostgreSQL settings: " + ", ".join(missing_database_settings)
    )

DB_CONFIG = {
    "host": os.environ["PGHOST"],
    "port": os.environ["PGPORT"],
    "dbname": os.environ["PGDATABASE"],
    "user": os.environ["PGUSER"],
    "password": os.environ["PGPASSWORD"],
}
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").casefold() == "true"
SESSION_COOKIE_NAME = "sma_session"
CSRF_COOKIE_NAME = "sma_csrf"
SESSION_MAX_AGE = 60 * 60 * 24 * 7
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
MAX_AUDIO_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_TRANSCRIPT_CHARACTERS = 200_000
SIGNUPS_PER_HOUR = 10
AI_REQUESTS_PER_HOUR = 5
AI_REQUEST_COOLDOWN_SECONDS = 60
ALLOWED_AUDIO_SUFFIXES = {
    ".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".ogg",
    ".wav", ".webm", ".wma",
}
