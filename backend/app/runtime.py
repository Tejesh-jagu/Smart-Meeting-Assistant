import hashlib
import hmac
import json
import re
import secrets
import smtplib
import ssl
import tempfile
from typing import Optional
from email.message import EmailMessage
from pathlib import Path

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException, Request

from psycopg.rows import dict_row
from pydantic import BaseModel, Field, field_validator
from report_safety import sanitize_report
from .config import (
    ALLOWED_AUDIO_SUFFIXES,
    CSRF_COOKIE_NAME,
    DB_CONFIG,
    FRONTEND_ORIGINS,
    AI_REQUESTS_PER_HOUR,
    AI_REQUEST_COOLDOWN_SECONDS,
    MAX_AUDIO_UPLOAD_BYTES,
    MAX_GROQ_AUDIO_UPLOAD_BYTES,
    AUDIO_CHUNK_SECONDS,
    MAX_TRANSCRIPT_CHARACTERS,
    GROQ_API_KEY,
    GROQ_MODEL,
    OTP_HASH_SECRET,
    SMTP_FROM_EMAIL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_SSL,
    SMTP_USERNAME,
    SIGNUPS_PER_HOUR,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SECURE,
    SESSION_MAX_AGE,
)


password_hasher = PasswordHasher()


class TranscriptRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=MAX_TRANSCRIPT_CHARACTERS)
    title: Optional[str] = Field(default=None, max_length=200)

    @field_validator("transcript")
    @classmethod
    def reject_blank_transcript(cls, value):
        if not value.strip():
            raise ValueError("Transcript cannot be blank.")
        return value

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        if value is not None:
            value = value.strip()
            return value if value else None
        return None


class UpdateTitleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Title cannot be blank.")
        return value


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        value = " ".join(value.split())
        if not value:
            raise ValueError("Enter your name.")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        value = value.strip().casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class VerificationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(pattern=r"^\d{8}$")
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class ResendVerificationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class PasswordResetRequest(ResendVerificationRequest):
    code: str = Field(pattern=r"^\d{8}$")
    password: str = Field(min_length=8, max_length=128)



def create_table():
    with psycopg.connect(**DB_CONFIG) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_users (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT,
                email_verified_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                next_session_number BIGINT NOT NULL DEFAULT 1 CHECK (next_session_number > 0),
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            ALTER TABLE app_users
            ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        """)
        connection.execute("ALTER TABLE app_users ALTER COLUMN email_verified_at DROP DEFAULT")
        connection.execute("ALTER TABLE app_users ALTER COLUMN password_hash DROP NOT NULL")
        connection.execute("UPDATE app_users SET password_hash = NULL WHERE email_verified_at IS NULL")

        connection.execute("""
            ALTER TABLE app_users
            ADD COLUMN IF NOT EXISTS next_session_number BIGINT NOT NULL DEFAULT 1
            CHECK (next_session_number > 0)
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                csrf_token TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMPTZ NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS auth_login_limits (
                address_hash TEXT PRIMARY KEY,
                window_started_at TIMESTAMPTZ NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                blocked_until TIMESTAMPTZ
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS email_verification_codes (
                user_id BIGINT PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,
                code_hash TEXT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                failed_attempts SMALLINT NOT NULL DEFAULT 0,
                sent_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_codes (
                user_id BIGINT PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,
                code_hash TEXT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                failed_attempts SMALLINT NOT NULL DEFAULT 0,
                sent_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS api_rate_limits (
                bucket_key TEXT PRIMARY KEY,
                window_started_at TIMESTAMPTZ NOT NULL,
                last_request_at TIMESTAMPTZ NOT NULL,
                request_count INTEGER NOT NULL CHECK (request_count > 0)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                transcript TEXT NOT NULL,
                session_number BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            ALTER TABLE meetings
            ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES app_users(id) ON DELETE CASCADE
        """)
        connection.execute("""
            ALTER TABLE meetings
            ADD COLUMN IF NOT EXISTS session_number BIGINT
        """)
        connection.execute("""
            ALTER TABLE meetings
            ADD COLUMN IF NOT EXISTS title TEXT
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS meetings_user_id_created_at_idx
            ON meetings (user_id, created_at DESC)
        """)
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS meetings_user_session_number_idx
            ON meetings (user_id, session_number)
            WHERE user_id IS NOT NULL AND session_number IS NOT NULL
        """)

        connection.execute("""
            WITH unnumbered AS (
                SELECT id, user_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY user_id ORDER BY created_at ASC, id ASC
                       ) AS row_number
                FROM meetings
                WHERE user_id IS NOT NULL AND session_number IS NULL
            ), numbered AS (
                SELECT unnumbered.id,
                       unnumbered.row_number + COALESCE(MAX(existing.session_number), 0)
                           AS session_number
                FROM unnumbered
                LEFT JOIN meetings AS existing
                    ON existing.user_id = unnumbered.user_id
                   AND existing.session_number IS NOT NULL
                GROUP BY unnumbered.id, unnumbered.row_number
            )
            UPDATE meetings
            SET session_number = numbered.session_number
            FROM numbered
            WHERE meetings.id = numbered.id
        """)
        connection.execute("""
            UPDATE app_users AS users
            SET next_session_number = GREATEST(
                users.next_session_number,
                COALESCE((
                    SELECT MAX(meetings.session_number) + 1
                    FROM meetings
                    WHERE meetings.user_id = users.id
                ), 1)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS meeting_reports (
                meeting_id BIGINT PRIMARY KEY REFERENCES meetings(id) ON DELETE CASCADE,
                summary TEXT NOT NULL,
                decisions JSONB NOT NULL DEFAULT '[]'::jsonb,
                tasks JSONB NOT NULL DEFAULT '[]'::jsonb,
                generator TEXT NOT NULL,
                generated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def save_meeting(connection, user_id, transcript, title=None):
    counter = connection.execute(
        """
        UPDATE app_users
        SET next_session_number = next_session_number + 1
        WHERE id = %s
        RETURNING next_session_number - 1
        """,
        (user_id,),
    ).fetchone()
    if counter is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    session_num = counter[0]
    final_title = title.strip() if title and title.strip() else f"Session {session_num}"

    return connection.execute(
        """
        INSERT INTO meetings (transcript, user_id, session_number, title)
        VALUES (%s, %s, %s, %s)
        RETURNING id, session_number, title
        """,
        (transcript, user_id, session_num, final_title),
    ).fetchone()



def csrf_cookie_value(request):
    return request.cookies.get(CSRF_COOKIE_NAME)


def require_csrf(request, token):
    origin = request.headers.get("origin")
    cookie_token = csrf_cookie_value(request)
    if (
        origin not in FRONTEND_ORIGINS
        or not cookie_token
        or not hmac.compare_digest(cookie_token, token or "")
    ):
        raise HTTPException(status_code=403, detail="Request verification failed. Refresh the page and try again.")


def set_auth_cookies(response, session_token, csrf_token):
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def create_session(connection, user_id):
    connection.execute("DELETE FROM app_sessions WHERE expires_at <= CURRENT_TIMESTAMP")
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
    connection.execute(
        """
        INSERT INTO app_sessions (token_hash, user_id, csrf_token, expires_at)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP + INTERVAL '7 days')
        """,
        (token_hash, user_id, csrf_token),
    )
    return session_token, csrf_token


def verification_configured():
    return bool(
        len(OTP_HASH_SECRET) >= 32
        and SMTP_HOST
        and 0 < SMTP_PORT < 65536
        and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", SMTP_FROM_EMAIL)
        and bool(SMTP_USERNAME) == bool(SMTP_PASSWORD)
    )


def hash_verification_code(code):
    return hmac.new(OTP_HASH_SECRET.encode("utf-8"), code.encode("ascii"), hashlib.sha256).hexdigest()


def hash_email_identifier(email):
    return hmac.new(OTP_HASH_SECRET.encode("utf-8"), email.encode("utf-8"), hashlib.sha256).hexdigest()


def new_verification_code():
    return f"{secrets.randbelow(100_000_000):08d}"


def send_verification_email(email, code):
    send_auth_code_email(
        email,
        code,
        "Verify your Smart Meeting Assistant email",
        "verification",
    )


def send_password_reset_email(email, code):
    send_auth_code_email(
        email,
        code,
        "Reset your Smart Meeting Assistant password",
        "password reset",
    )


def send_auth_code_email(email, code, subject, purpose):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = email
    message.set_content(
        f"Your Smart Meeting Assistant {purpose} code is {code}. "
        "It expires in 10 minutes. If you did not request this, ignore this email."
    )

    if SMTP_USE_SSL:
        smtp = smtplib.SMTP_SSL(
            SMTP_HOST, SMTP_PORT, timeout=10, context=ssl.create_default_context()
        )
    else:
        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
    with smtp:
        if not SMTP_USE_SSL:
            smtp.starttls(context=ssl.create_default_context())
        if SMTP_USERNAME:
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(message)


def get_current_user(request: Request):
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
    with psycopg.connect(**DB_CONFIG, row_factory=dict_row) as connection:
        user = connection.execute(
            """
            SELECT app_users.id, app_users.name, app_users.email, app_sessions.csrf_token
            FROM app_sessions
            JOIN app_users ON app_users.id = app_sessions.user_id
            WHERE app_sessions.token_hash = %s
              AND app_sessions.expires_at > CURRENT_TIMESTAMP
              AND app_users.email_verified_at IS NOT NULL
            """,
            (token_hash,),
        ).fetchone()

    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def client_address_hash(request):
    address = request.client.host if request.client else "unknown"
    return hashlib.sha256(address.encode("utf-8")).hexdigest()


def register_login_attempt(connection, address_hash):
    row = connection.execute(
        """
        INSERT INTO auth_login_limits
            (address_hash, window_started_at, attempt_count)
        VALUES (%s, CURRENT_TIMESTAMP, 1)
        ON CONFLICT (address_hash) DO UPDATE SET
            attempt_count = CASE
                WHEN auth_login_limits.blocked_until > CURRENT_TIMESTAMP
                    THEN auth_login_limits.attempt_count
                WHEN auth_login_limits.window_started_at <= CURRENT_TIMESTAMP - INTERVAL '15 minutes'
                    THEN 1
                ELSE auth_login_limits.attempt_count + 1
            END,
            window_started_at = CASE
                WHEN auth_login_limits.blocked_until > CURRENT_TIMESTAMP
                    THEN auth_login_limits.window_started_at
                WHEN auth_login_limits.window_started_at <= CURRENT_TIMESTAMP - INTERVAL '15 minutes'
                    THEN CURRENT_TIMESTAMP
                ELSE auth_login_limits.window_started_at
            END,
            blocked_until = CASE
                WHEN auth_login_limits.blocked_until > CURRENT_TIMESTAMP
                    THEN auth_login_limits.blocked_until
                WHEN auth_login_limits.window_started_at <= CURRENT_TIMESTAMP - INTERVAL '15 minutes'
                    THEN NULL
                WHEN auth_login_limits.attempt_count + 1 >= 6
                    THEN CURRENT_TIMESTAMP + INTERVAL '15 minutes'
                ELSE NULL
            END
        RETURNING blocked_until > CURRENT_TIMESTAMP AS is_blocked
        """,
        (address_hash,),
    ).fetchone()
    return bool(row["is_blocked"])


def consume_rate_limit(connection, bucket_key, limit, window_seconds, cooldown_seconds=0):
    row = connection.execute(
        """
        INSERT INTO api_rate_limits
            (bucket_key, window_started_at, last_request_at, request_count)
        VALUES (%s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
        ON CONFLICT (bucket_key) DO UPDATE SET
            window_started_at = CASE
                WHEN api_rate_limits.window_started_at <= CURRENT_TIMESTAMP - (%s * INTERVAL '1 second')
                    THEN CURRENT_TIMESTAMP
                ELSE api_rate_limits.window_started_at
            END,
            last_request_at = CURRENT_TIMESTAMP,
            request_count = CASE
                WHEN api_rate_limits.window_started_at <= CURRENT_TIMESTAMP - (%s * INTERVAL '1 second')
                    THEN 1
                ELSE api_rate_limits.request_count + 1
            END
        WHERE api_rate_limits.window_started_at <= CURRENT_TIMESTAMP - (%s * INTERVAL '1 second')
           OR (
                api_rate_limits.request_count < %s
                AND api_rate_limits.last_request_at <= CURRENT_TIMESTAMP - (%s * INTERVAL '1 second')
           )
        RETURNING request_count
        """,
        (bucket_key, window_seconds, window_seconds, window_seconds, limit, cooldown_seconds),
    ).fetchone()
    return row is not None
