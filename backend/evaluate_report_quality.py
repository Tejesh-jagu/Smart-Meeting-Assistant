"""Run a grounded-report quality check against Groq and an isolated test schema."""

import json
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from starlette.requests import Request

load_dotenv(Path(__file__).with_name(".env"))

test_database_url = os.getenv("SMART_MEETING_TEST_DATABASE_URL")
if not test_database_url:
    raise SystemExit("Set SMART_MEETING_TEST_DATABASE_URL to a dedicated PostgreSQL test database.")
if not os.getenv("GROQ_API_KEY"):
    raise SystemExit("Set GROQ_API_KEY in backend/.env before running the live report evaluation.")

db_config = conninfo_to_dict(test_database_url)
if "test" not in db_config.get("dbname", "").casefold():
    raise SystemExit("Refusing to run: the database name must contain 'test'.")

schema = f"sma_report_eval_{uuid4().hex}"
with psycopg.connect(test_database_url) as connection:
    connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

db_config["options"] = f"-c search_path={schema}"

# main.py initializes tables on import, so prevent it from touching the normal app database.
with patch("psycopg.connect"):
    import main
from app import runtime

cases_path = Path(__file__).parents[1] / "examples" / "report_evaluation_cases.json"
cases = json.loads(cases_path.read_text(encoding="utf-8"))

try:
    with (
        patch.object(runtime, "DB_CONFIG", db_config),
        patch.object(runtime, "consume_rate_limit", return_value=True),
    ):
        main.create_table()
        with psycopg.connect(**db_config) as connection:
            user_id = connection.execute(
                "INSERT INTO app_users (name, email, password_hash) "
                "VALUES (%s, %s, %s) RETURNING id",
                ("Report evaluation", f"{uuid4().hex}@example.test", "unused"),
            ).fetchone()[0]

        token = "report-evaluation-csrf"
        request = Request({
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [
                (b"origin", runtime.FRONTEND_ORIGINS[0].encode()),
                (b"cookie", f"{runtime.CSRF_COOKIE_NAME}={token}".encode()),
            ],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8000),
        })
        user = {"id": user_id}
        for case in cases:
            saved = main.receive_transcript(
                request,
                main.TranscriptRequest(transcript=case["transcript"]),
                token,
                user,
            )
            report = main.generate_report(saved["id"], request, token, user)

            for field in ("summary", "decisions", "tasks"):
                if report[field] != case[field]:
                    raise AssertionError(
                        f"{case['name']}: expected {field} {case[field]!r}, got {report[field]!r}"
                    )

            main.delete_transcript(saved["id"], request, token, user)
            print(f"PASS {case['name']}")

    print(f"Passed {len(cases)} report cases with Groq {runtime.GROQ_MODEL}.")
finally:
    with psycopg.connect(test_database_url) as connection:
        connection.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
        )
