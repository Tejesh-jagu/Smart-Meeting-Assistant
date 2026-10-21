import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from fastapi.testclient import TestClient


with patch("psycopg.connect"):
    import main

from app import runtime


class ReportEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.csrf_token = "test-csrf-token"
        self.client.cookies.set(main.CSRF_COOKIE_NAME, self.csrf_token)
        self.headers = {
            "Origin": main.FRONTEND_ORIGINS[0],
            "X-CSRF-Token": self.csrf_token,
        }
        main.app.dependency_overrides[main.get_current_user] = lambda: {
            "id": 7,
            "name": "Test User",
            "email": "test@example.com",
            "csrf_token": self.csrf_token,
        }

    def tearDown(self):
        main.app.dependency_overrides.pop(main.get_current_user, None)
        self.client.close()

    def test_generate_report_sanitizes_and_persists_the_result(self):
        transcript = (
            "Thanks for joining. We agreed to launch the pilot next month. "
            "Priya will send the onboarding guide by Friday. "
            "The dashboard could show weekly attendance."
        )
        generated_at = datetime(2026, 10, 17, tzinfo=timezone.utc)
        meeting_cursor = MagicMock()
        meeting_cursor.fetchone.return_value = {"id": 42, "transcript": transcript}
        saved_cursor = MagicMock()
        saved_cursor.fetchone.return_value = (generated_at,)
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.side_effect = [meeting_cursor, saved_cursor]

        ollama_response = MagicMock()
        ollama_response.__enter__.return_value = ollama_response
        ollama_response.read.return_value = json.dumps({
            "response": json.dumps({
                "summary": "Thanks for joining.",
                "decisions": ["We agreed to launch the pilot next month."],
                "tasks": [
                    "Priya will send the onboarding guide by Friday.",
                    "The dashboard could show weekly attendance.",
                ],
            })
        }).encode()

        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "urlopen", return_value=ollama_response),
            patch.object(runtime, "consume_rate_limit", return_value=True),
        ):
            response = self.client.post("/transcripts/42/report", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["summary"], "We agreed to launch the pilot next month.")
        self.assertEqual(result["decisions"], ["We agreed to launch the pilot next month."])
        self.assertEqual(result["tasks"], ["Priya will send the onboarding guide by Friday."])
        self.assertEqual(result["generator"], f"Ollama {main.OLLAMA_MODEL}")
        self.assertEqual(result["generated_at"], "2026-10-17T00:00:00+00:00")
        self.assertEqual(connection.execute.call_count, 2)

    def test_ollama_connection_error_is_returned_as_actionable_api_error(self):
        meeting_cursor = MagicMock()
        meeting_cursor.fetchone.return_value = {"id": 43, "transcript": "The team met today."}
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value = meeting_cursor

        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "urlopen", side_effect=URLError("offline")),
            patch.object(runtime, "consume_rate_limit", return_value=True),
        ):
            response = self.client.post("/transcripts/43/report", headers=self.headers)

        self.assertEqual(response.status_code, 502)
        self.assertIn("Could not connect to Ollama", response.json()["detail"])

    def test_upload_rejects_unsupported_file_extension(self):
        response = self.client.post(
            "/transcripts/upload",
            files={"file": ("notes.txt", b"not audio", "text/plain")},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 415)

    def test_saving_transcript_returns_its_session_number(self):
        transcript = "The team agreed to review the proposal."
        connection = MagicMock()
        connection.__enter__.return_value = connection

        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "save_meeting", return_value=(88, 4)) as save_meeting,
        ):
            response = self.client.post(
                "/transcripts", json={"transcript": transcript}, headers=self.headers
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session_number"], 4)
        save_meeting.assert_called_once_with(connection, 7, transcript)

    def test_upload_saves_the_transcript_with_its_session_number(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        model = MagicMock()
        model.transcribe.return_value = ([MagicMock(text="The team will share the agenda.")], None)

        with (
            patch.object(runtime, "get_whisper_model", return_value=model),
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "save_meeting", return_value=(89, 5)) as save_meeting,
            patch.object(runtime, "consume_rate_limit", return_value=True),
        ):
            response = self.client.post(
                "/transcripts/upload",
                files={"file": ("meeting.wav", b"audio bytes", "audio/wav")},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session_number"], 5)
        self.assertEqual(response.json()["transcript"], "The team will share the agenda.")
        save_meeting.assert_called_once_with(connection, 7, "The team will share the agenda.")

    def test_upload_enforces_size_limit(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        with (
            patch.object(runtime, "MAX_AUDIO_UPLOAD_BYTES", 3),
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "consume_rate_limit", return_value=True),
        ):
            response = self.client.post(
                "/transcripts/upload",
                files={"file": ("meeting.wav", b"1234", "audio/wav")},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 413)

    def test_audio_transcription_rate_limit_rejects_before_loading_whisper(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "consume_rate_limit", return_value=False),
            patch.object(runtime, "get_whisper_model") as get_model,
        ):
            response = self.client.post(
                "/transcripts/upload",
                files={"file": ("meeting.wav", b"audio bytes", "audio/wav")},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 429)
        get_model.assert_not_called()

    def test_report_generation_rate_limit_rejects_before_calling_ollama(self):
        meeting_cursor = MagicMock()
        meeting_cursor.fetchone.return_value = {"id": 44, "transcript": "The team met today."}
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value = meeting_cursor
        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "consume_rate_limit", return_value=False),
            patch.object(runtime, "urlopen") as urlopen,
        ):
            response = self.client.post("/transcripts/44/report", headers=self.headers)

        self.assertEqual(response.status_code, 429)
        urlopen.assert_not_called()

    def test_transcript_endpoint_rejects_blank_or_oversized_text(self):
        with patch.object(main.psycopg, "connect") as connect:
            blank_response = self.client.post(
                "/transcripts", json={"transcript": "   "}, headers=self.headers
            )
            long_response = self.client.post(
                "/transcripts",
                json={"transcript": "x" * (main.MAX_TRANSCRIPT_CHARACTERS + 1)},
                headers=self.headers,
            )

        self.assertEqual(blank_response.status_code, 422)
        self.assertEqual(long_response.status_code, 422)
        connect.assert_not_called()

    def test_health_endpoint_checks_database_and_configured_model(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        ollama_response = MagicMock()
        ollama_response.__enter__.return_value = ollama_response
        ollama_response.read.return_value = json.dumps({
            "models": [{"name": main.OLLAMA_MODEL}],
        }).encode()

        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "urlopen", return_value=ollama_response),
        ):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_health_endpoint_fails_when_database_is_unavailable(self):
        with patch.object(main.psycopg, "connect", side_effect=OSError("offline")):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "PostgreSQL is unavailable.")


TEST_DATABASE_URL = os.getenv("SMART_MEETING_TEST_DATABASE_URL", "")


@unittest.skipUnless(TEST_DATABASE_URL, "Set SMART_MEETING_TEST_DATABASE_URL to run PostgreSQL integration tests")
class PostgresReportIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_config = conninfo_to_dict(TEST_DATABASE_URL)
        if "test" not in cls.db_config.get("dbname", "").casefold():
            raise RuntimeError("Integration tests require a PostgreSQL database name containing 'test'.")

        cls.schema = f"sma_test_{uuid4().hex}"
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            connection.execute(
                sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema))
            )

        cls.db_config["options"] = f"-c search_path={cls.schema}"
        with patch.object(runtime, "DB_CONFIG", cls.db_config):
            main.create_table()

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(cls.schema))
            )

    def setUp(self):
        self.db_config_patch = patch.object(runtime, "DB_CONFIG", self.db_config)
        self.db_config_patch.start()
        self.addCleanup(self.db_config_patch.stop)
        self.client = TestClient(main.app)
        csrf_response = self.client.get("/auth/csrf")
        self.assertEqual(csrf_response.status_code, 200)
        signup_response = self.client.post(
            "/auth/register",
            json={
                "name": "Integration User",
                "email": f"{uuid4().hex}@example.com",
                "password": "test-password-123",
            },
            headers={
                "Origin": main.FRONTEND_ORIGINS[0],
                "X-CSRF-Token": csrf_response.json()["csrf_token"],
            },
        )
        self.assertEqual(signup_response.status_code, 201, signup_response.text)
        self.headers = {
            "Origin": main.FRONTEND_ORIGINS[0],
            "X-CSRF-Token": signup_response.json()["csrf_token"],
        }
        self.user_id = signup_response.json()["user"]["id"]

    def test_session_numbers_are_sequential_and_never_reused_after_deletion(self):
        first = self.client.post(
            "/transcripts", json={"transcript": "First meeting."}, headers=self.headers
        ).json()
        second = self.client.post(
            "/transcripts", json={"transcript": "Second meeting."}, headers=self.headers
        ).json()
        self.assertEqual((first["session_number"], second["session_number"]), (1, 2))

        deleted = self.client.delete(f"/transcripts/{first['id']}", headers=self.headers)
        self.assertEqual(deleted.status_code, 200)
        third = self.client.post(
            "/transcripts", json={"transcript": "Third meeting."}, headers=self.headers
        ).json()
        self.assertEqual(third["session_number"], 3)

        listed = self.client.get("/transcripts").json()
        self.assertEqual({row["session_number"] for row in listed}, {2, 3})

    def test_session_numbers_are_unique_when_saved_concurrently(self):
        def save(index):
            with psycopg.connect(**self.db_config) as connection:
                return runtime.save_meeting(connection, self.user_id, f"Concurrent meeting {index}.")[1]

        with ThreadPoolExecutor(max_workers=8) as executor:
            numbers = list(executor.map(save, range(8)))

        self.assertEqual(sorted(numbers), list(range(1, 9)))

    def test_ai_usage_limit_enforces_cooldown_and_window_budget(self):
        bucket = f"test-rate-limit:{self.user_id}:{uuid4().hex}"
        with psycopg.connect(**self.db_config) as connection:
            self.assertTrue(runtime.consume_rate_limit(connection, bucket, 2, 3600, 60))
            self.assertFalse(runtime.consume_rate_limit(connection, bucket, 2, 3600, 60))
            connection.execute(
                "UPDATE api_rate_limits SET last_request_at = CURRENT_TIMESTAMP - INTERVAL '61 seconds' WHERE bucket_key = %s",
                (bucket,),
            )
            self.assertTrue(runtime.consume_rate_limit(connection, bucket, 2, 3600, 60))
            connection.execute(
                "UPDATE api_rate_limits SET last_request_at = CURRENT_TIMESTAMP - INTERVAL '61 seconds' WHERE bucket_key = %s",
                (bucket,),
            )
            self.assertFalse(runtime.consume_rate_limit(connection, bucket, 2, 3600, 60))
            connection.execute(
                "UPDATE api_rate_limits SET window_started_at = CURRENT_TIMESTAMP - INTERVAL '1 hour 1 second' WHERE bucket_key = %s",
                (bucket,),
            )
            self.assertTrue(runtime.consume_rate_limit(connection, bucket, 2, 3600, 60))

    def test_legacy_meetings_are_backfilled_by_date_without_losing_reports(self):
        dates = [
            datetime(2025, 3, 2, tzinfo=timezone.utc),
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            datetime(2025, 2, 1, tzinfo=timezone.utc),
        ]
        saved_rows = []
        with psycopg.connect(**self.db_config) as connection:
            connection.execute("DROP INDEX IF EXISTS meetings_user_session_number_idx")
            connection.execute("ALTER TABLE meetings DROP COLUMN session_number")
            connection.execute("ALTER TABLE app_users DROP COLUMN next_session_number")
            for index, created_at in enumerate(dates):
                meeting_id = connection.execute(
                    "INSERT INTO meetings (user_id, transcript, created_at) VALUES (%s, %s, %s) RETURNING id",
                    (self.user_id, f"Legacy transcript {index}.", created_at),
                ).fetchone()[0]
                saved_rows.append((meeting_id, index, created_at))
            connection.execute(
                "INSERT INTO meeting_reports (meeting_id, summary, generator) VALUES (%s, %s, %s)",
                (saved_rows[0][0], "Existing report summary.", "test model"),
            )

        main.create_table()

        with psycopg.connect(**self.db_config) as connection:
            rows = connection.execute(
                "SELECT id, session_number, transcript FROM meetings WHERE user_id = %s ORDER BY created_at, id",
                (self.user_id,),
            ).fetchall()
            next_number = connection.execute(
                "SELECT next_session_number FROM app_users WHERE id = %s", (self.user_id,)
            ).fetchone()[0]
            report = connection.execute(
                "SELECT summary FROM meeting_reports WHERE meeting_id = %s", (saved_rows[0][0],)
            ).fetchone()

        self.assertEqual([row[1] for row in rows], [1, 2, 3])
        self.assertEqual({row[2] for row in rows}, {f"Legacy transcript {index}." for index in range(3)})
        self.assertEqual(next_number, 4)
        self.assertEqual(report[0], "Existing report summary.")

    def test_first_account_claims_legacy_meetings_in_chronological_order(self):
        schema = f"sma_claim_{uuid4().hex}"
        db_config = {**self.db_config, "options": f"-c search_path={schema}"}
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            with psycopg.connect(**db_config) as connection:
                connection.execute("""
                    CREATE TABLE meetings (
                        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        transcript TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                connection.execute(
                    "INSERT INTO meetings (transcript, created_at) VALUES (%s, %s), (%s, %s)",
                    (
                        "Older legacy transcript.", datetime(2024, 1, 1, tzinfo=timezone.utc),
                        "Newer legacy transcript.", datetime(2024, 2, 1, tzinfo=timezone.utc),
                    ),
                )
            with patch.object(runtime, "DB_CONFIG", db_config):
                main.create_table()
                client = TestClient(main.app)
                try:
                    csrf = client.get("/auth/csrf").json()["csrf_token"]
                    signup = client.post(
                        "/auth/register",
                        json={
                            "name": "First Account",
                            "email": f"{uuid4().hex}@example.com",
                            "password": "test-password-123",
                        },
                        headers={
                            "Origin": main.FRONTEND_ORIGINS[0],
                            "X-CSRF-Token": csrf,
                        },
                    )
                    self.assertEqual(signup.status_code, 201, signup.text)
                    listed = client.get("/transcripts").json()
                    self.assertEqual(
                        [(row["session_number"], row["transcript"]) for row in reversed(listed)],
                        [(1, "Older legacy transcript."), (2, "Newer legacy transcript.")],
                    )
                finally:
                    client.close()
        finally:
            with psycopg.connect(TEST_DATABASE_URL) as connection:
                connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))

    def test_session_list_and_delete_remain_scoped_to_the_owner(self):
        own_meeting = self.client.post(
            "/transcripts", json={"transcript": "Private meeting."}, headers=self.headers
        ).json()
        other_client = TestClient(main.app)
        self.addCleanup(other_client.close)
        csrf = other_client.get("/auth/csrf").json()["csrf_token"]
        signup = other_client.post(
            "/auth/register",
            json={
                "name": "Another User",
                "email": f"{uuid4().hex}@example.com",
                "password": "test-password-123",
            },
            headers={"Origin": main.FRONTEND_ORIGINS[0], "X-CSRF-Token": csrf},
        )
        other_headers = {
            "Origin": main.FRONTEND_ORIGINS[0],
            "X-CSRF-Token": signup.json()["csrf_token"],
        }

        self.assertEqual(other_client.get("/transcripts").json(), [])
        self.assertEqual(other_client.get("/reports").json(), [])
        self.assertEqual(
            other_client.put(
                f"/transcripts/{own_meeting['id']}",
                json={"transcript": "Attempted change."},
                headers=other_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            other_client.delete(f"/transcripts/{own_meeting['id']}", headers=other_headers).status_code,
            404,
        )
        self.assertEqual(
            other_client.post(f"/transcripts/{own_meeting['id']}/report", headers=other_headers).status_code,
            404,
        )
        self.assertEqual(len(self.client.get("/transcripts").json()), 1)

    def test_report_is_saved_and_listed_from_postgres_with_ollama_mocked(self):
        transcript = (
            "We agreed to launch the customer pilot next month. "
            "Priya will send the onboarding guide by Friday."
        )
        save_response = self.client.post(
            "/transcripts", json={"transcript": transcript}, headers=self.headers
        )
        self.assertEqual(save_response.status_code, 200)
        meeting_id = save_response.json()["id"]

        ollama_response = MagicMock()
        ollama_response.__enter__.return_value = ollama_response
        ollama_response.read.return_value = json.dumps({
            "response": json.dumps({
                "summary": "The pilot launches in one month.",
                "decisions": ["We agreed to launch the customer pilot next month."],
                "tasks": ["Priya will send the onboarding guide by Friday."],
            })
        }).encode()

        with patch.object(runtime, "urlopen", return_value=ollama_response):
            report_response = self.client.post(
                f"/transcripts/{meeting_id}/report", headers=self.headers
            )

        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(
            report_response.json()["summary"],
            "We agreed to launch the customer pilot next month.",
        )
        listed_reports = self.client.get("/reports")
        self.assertEqual(listed_reports.status_code, 200)
        self.assertEqual(listed_reports.json()[0]["meeting_id"], meeting_id)
        self.assertEqual(
            listed_reports.json()[0]["tasks"],
            ["Priya will send the onboarding guide by Friday."],
        )


if __name__ == "__main__":
    unittest.main()
