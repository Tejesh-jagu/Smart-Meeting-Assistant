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
    "sslmode": os.getenv("PGSSLMODE", "require"),
}
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_NAME = "sma_session"
CSRF_COOKIE_NAME = "sma_csrf"
SESSION_MAX_AGE = 60 * 60 * 24 * 7
OTP_HASH_SECRET = os.getenv("OTP_HASH_SECRET", "")
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", os.getenv("SMTP_FROM_EMAIL", ""))
FRONTEND_ORIGINS = list(dict.fromkeys(
    origin.strip().rstrip("/")
    for origin in (
        os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        + [os.getenv("VERCEL_FRONTEND_ORIGIN", "")]
    )
    if origin.strip()
))
MAX_AUDIO_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_GROQ_AUDIO_UPLOAD_BYTES = 25_000_000
AUDIO_CHUNK_SECONDS = 300
MAX_TRANSCRIPT_CHARACTERS = 200_000
SIGNUPS_PER_HOUR = 10
AI_REQUESTS_PER_HOUR = 5
AI_REQUEST_COOLDOWN_SECONDS = 60
ALLOWED_AUDIO_SUFFIXES = {
    ".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".ogg",
    ".wav", ".webm", ".wma",
}
