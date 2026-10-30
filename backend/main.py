"""Compatibility entry point for ``uvicorn main:app`` and local scripts."""

from app import runtime
from app.main import app
from app.api.auth import (
    get_csrf_token,
    register,
    verify_email,
    resend_verification,
    login,
    current_user,
    logout,
)
from app.api.health import health_check
from app.api.meetings import (
    home,
    receive_transcript,
    update_transcript,
    delete_transcript,
    upload_audio,
    list_transcripts,
)
from app.api.reports import list_reports, generate_report

# Preserve the original import surface for local scripts and existing integrations.
DB_CONFIG = runtime.DB_CONFIG
GROQ_MODEL = runtime.GROQ_MODEL
SESSION_COOKIE_SECURE = runtime.SESSION_COOKIE_SECURE
SESSION_COOKIE_NAME = runtime.SESSION_COOKIE_NAME
CSRF_COOKIE_NAME = runtime.CSRF_COOKIE_NAME
SESSION_MAX_AGE = runtime.SESSION_MAX_AGE
FRONTEND_ORIGINS = runtime.FRONTEND_ORIGINS
MAX_AUDIO_UPLOAD_BYTES = runtime.MAX_AUDIO_UPLOAD_BYTES
MAX_TRANSCRIPT_CHARACTERS = runtime.MAX_TRANSCRIPT_CHARACTERS
ALLOWED_AUDIO_SUFFIXES = runtime.ALLOWED_AUDIO_SUFFIXES
password_hasher = runtime.password_hasher
TranscriptRequest = runtime.TranscriptRequest
UpdateTitleRequest = runtime.UpdateTitleRequest
SignupRequest = runtime.SignupRequest
LoginRequest = runtime.LoginRequest
create_table = runtime.create_table
csrf_cookie_value = runtime.csrf_cookie_value
require_csrf = runtime.require_csrf
set_auth_cookies = runtime.set_auth_cookies
create_session = runtime.create_session
get_current_user = runtime.get_current_user
client_address_hash = runtime.client_address_hash
register_login_attempt = runtime.register_login_attempt
psycopg = runtime.psycopg
sanitize_report = runtime.sanitize_report
