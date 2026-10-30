import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app import runtime

with patch("psycopg.connect"):
    import main


class AuthenticationEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.csrf_token = "test-csrf-token"
        self.client.cookies.set(main.CSRF_COOKIE_NAME, self.csrf_token)
        self.headers = {
            "Origin": main.FRONTEND_ORIGINS[0],
            "X-CSRF-Token": self.csrf_token,
        }

    def tearDown(self):
        main.app.dependency_overrides.pop(main.get_current_user, None)
        self.client.close()

    def test_meetings_are_protected_without_a_session(self):
        for response in (
            self.client.get("/transcripts"),
            self.client.get("/reports"),
            self.client.post("/transcripts", json={"transcript": "No session."}, headers=self.headers),
        ):
            self.assertEqual(response.status_code, 401)

    def test_listed_meetings_are_scoped_to_the_signed_in_user(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.fetchall.return_value = []
        main.app.dependency_overrides[main.get_current_user] = lambda: {"id": 12}

        with patch.object(main.psycopg, "connect", return_value=connection):
            response = self.client.get("/transcripts")

        self.assertEqual(response.status_code, 200)
        self.assertIn("WHERE user_id = %s", str(connection.execute.call_args.args[0]))
        self.assertEqual(connection.execute.call_args.args[1], (12,))

    def test_current_user_restores_session_and_logout_revokes_it(self):
        user = {
            "id": 12,
            "name": "Priya Shah",
            "email": "priya@example.com",
            "csrf_token": self.csrf_token,
        }
        main.app.dependency_overrides[main.get_current_user] = lambda: user
        self.client.cookies.set(main.SESSION_COOKIE_NAME, "session-token")

        restored = self.client.get("/auth/me")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["user"]["email"], "priya@example.com")

        connection = MagicMock()
        connection.__enter__.return_value = connection
        with patch.object(main.psycopg, "connect", return_value=connection):
            signed_out = self.client.post("/auth/logout", headers=self.headers)

        self.assertEqual(signed_out.status_code, 200)
        self.assertEqual(signed_out.json()["message"], "Signed out.")
        self.assertIn("max-age=0", signed_out.headers["set-cookie"].casefold())

    def test_registration_sends_code_without_storing_a_password_or_creating_a_session(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection

        def execute(query, params=None):
            cursor = MagicMock()
            query = " ".join(str(query).split())
            if query.startswith("INSERT INTO app_users"):
                cursor.fetchone.return_value = {
                    "id": 12,
                    "name": "Priya Shah",
                    "email": "priya@example.com",
                }
            return cursor

        connection.execute.side_effect = execute
        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "consume_rate_limit", return_value=True),
            patch.object(runtime, "verification_configured", return_value=True),
            patch.object(runtime, "send_verification_email") as send_email,
        ):
            response = self.client.post(
                "/auth/register",
                json={
                    "name": " Priya   Shah ",
                    "email": "PRIYA@example.com",
                },
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertTrue(response.json()["verification_required"])
        self.assertEqual(response.json()["email"], "priya@example.com")
        self.assertNotIn("password", response.json())
        self.assertFalse(response.cookies.get(main.SESSION_COOKIE_NAME))
        send_email.assert_called_once()
        self.assertEqual(send_email.call_args.args[0], "priya@example.com")
        self.assertRegex(send_email.call_args.args[1], r"^\d{8}$")
        insert_call = next(
            call for call in connection.execute.call_args_list
            if "INSERT INTO app_users" in str(call.args[0])
        )
        self.assertEqual(insert_call.args[1], ("Priya Shah", "priya@example.com"))

    def test_verification_consumes_code_and_creates_session(self):
        code = "48201937"
        connection = MagicMock()
        connection.__enter__.return_value = connection

        def execute(query, params=None):
            cursor = MagicMock()
            query = " ".join(str(query).split())
            if query.startswith("SELECT users.id"):
                cursor.fetchone.return_value = {
                    "id": 12,
                    "name": "Priya Shah",
                    "email": "priya@example.com",
                    "code_hash": runtime.hash_verification_code(code),
                    "is_valid": True,
                    "failed_attempts": 0,
                }
            elif query.startswith("SELECT NOT EXISTS"):
                cursor.fetchone.return_value = {"is_first": False}
            return cursor

        connection.execute.side_effect = execute
        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "consume_rate_limit", return_value=True),
            patch.object(runtime, "OTP_HASH_SECRET", "integration-test-otp-secret-000000000000"),
            patch.object(runtime, "create_session", return_value=("session", "csrf-session")),
        ):
            response = self.client.post(
                "/auth/verify-email",
                json={"email": "PRIYA@example.com", "code": code, "password": "secure-pass-123"},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user"]["email"], "priya@example.com")
        self.assertTrue(response.cookies.get(main.SESSION_COOKIE_NAME))
        self.assertIn("DELETE FROM email_verification_codes", str(connection.execute.call_args_list))
        password_update = next(
            call for call in connection.execute.call_args_list
            if "SET password_hash =" in str(call.args[0])
        )
        self.assertTrue(main.password_hasher.verify(password_update.args[1][0], "secure-pass-123"))

    def test_wrong_verification_code_is_rejected(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = {
            "id": 12,
            "name": "Priya Shah",
            "email": "priya@example.com",
            "code_hash": runtime.hash_verification_code("00000000"),
            "is_valid": True,
            "failed_attempts": 0,
        }

        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "consume_rate_limit", return_value=True),
            patch.object(runtime, "OTP_HASH_SECRET", "integration-test-otp-secret-000000000000"),
        ):
            response = self.client.post(
                "/auth/verify-email",
                json={"email": "priya@example.com", "code": "12345678", "password": "secure-pass-123"},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.cookies.get(main.SESSION_COOKIE_NAME))
        self.assertIn("failed_attempts = failed_attempts + 1", str(connection.execute.call_args_list))

    def test_resend_verification_sends_a_rotated_code_without_exposing_it(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = {
            "id": 12,
            "email": "priya@example.com",
        }

        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "consume_rate_limit", return_value=True),
            patch.object(runtime, "verification_configured", return_value=True),
            patch.object(runtime, "send_verification_email") as send_email,
        ):
            response = self.client.post(
                "/auth/resend-verification",
                json={"email": "PRIYA@example.com"},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("code", response.json())
        self.assertRegex(send_email.call_args.args[1], r"^\d{8}$")
        self.assertIn("failed_attempts = 0", str(connection.execute.call_args_list))

    def test_password_reset_request_sends_a_code_without_disclosing_account_existence(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = {
            "id": 12,
            "email": "priya@example.com",
        }

        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "consume_rate_limit", return_value=True),
            patch.object(runtime, "verification_configured", return_value=True),
            patch.object(runtime, "send_password_reset_email") as send_email,
        ):
            response = self.client.post(
                "/auth/request-password-reset",
                json={"email": "PRIYA@example.com"},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("priya@example.com", response.text)
        self.assertNotIn("code", response.json())
        send_email.assert_called_once_with("priya@example.com", send_email.call_args.args[1])
        self.assertRegex(send_email.call_args.args[1], r"^\d{8}$")
        self.assertIn("password_reset_codes", str(connection.execute.call_args_list))

    def test_password_reset_request_for_unknown_email_returns_the_same_response(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = None

        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "consume_rate_limit", return_value=True),
            patch.object(runtime, "verification_configured", return_value=True),
            patch.object(runtime, "send_password_reset_email") as send_email,
        ):
            response = self.client.post(
                "/auth/request-password-reset",
                json={"email": "unknown@example.com"},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("unknown@example.com", response.text)
        send_email.assert_not_called()

    def test_password_reset_changes_the_password_and_revokes_existing_sessions(self):
        code = "48201937"
        otp_secret = "integration-test-otp-secret-000000000000"
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = {
            "id": 12,
            "code_hash": runtime.hmac.new(
                otp_secret.encode("utf-8"), code.encode("ascii"), runtime.hashlib.sha256
            ).hexdigest(),
            "is_valid": True,
            "failed_attempts": 0,
        }

        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "consume_rate_limit", return_value=True),
            patch.object(runtime, "OTP_HASH_SECRET", otp_secret),
        ):
            response = self.client.post(
                "/auth/reset-password",
                json={"email": "PRIYA@example.com", "code": code, "password": "new-secure-pass-456"},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["message"],
            "Password reset. Sign in with your new password.",
        )
        password_update = next(
            call for call in connection.execute.call_args_list
            if "UPDATE app_users SET password_hash" in str(call.args[0])
        )
        self.assertTrue(main.password_hasher.verify(password_update.args[1][0], "new-secure-pass-456"))
        queries = str(connection.execute.call_args_list)
        self.assertIn("DELETE FROM password_reset_codes", queries)
        self.assertIn("DELETE FROM app_sessions", queries)
        self.assertFalse(response.cookies.get(main.SESSION_COOKIE_NAME))

    def test_password_reset_rejects_an_invalid_code_without_changing_the_password(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = {
            "id": 12,
            "code_hash": runtime.hash_verification_code("00000000"),
            "is_valid": True,
            "failed_attempts": 0,
        }

        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "consume_rate_limit", return_value=True),
            patch.object(runtime, "OTP_HASH_SECRET", "integration-test-otp-secret-000000000000"),
        ):
            response = self.client.post(
                "/auth/reset-password",
                json={"email": "priya@example.com", "code": "12345678", "password": "new-secure-pass-456"},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 400)
        queries = str(connection.execute.call_args_list)
        self.assertIn("failed_attempts = failed_attempts + 1", queries)
        self.assertNotIn("UPDATE app_users SET password_hash", queries)

    def test_registration_rate_limit_rejects_before_hashing_or_inserting(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "consume_rate_limit", return_value=False),
            patch.object(runtime, "verification_configured", return_value=True),
        ):
            response = self.client.post(
                "/auth/register",
                json={
                    "name": "Priya Shah",
                    "email": "priya@example.com",
                },
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 429)
        connection.execute.assert_not_called()

    def test_login_restores_session_and_rejects_bad_credentials(self):
        password_hash = main.password_hasher.hash("secure-pass-123")
        connection = MagicMock()
        connection.__enter__.return_value = connection

        def execute(query, params=None):
            cursor = MagicMock()
            query = " ".join(str(query).split())
            if query.startswith("INSERT INTO auth_login_limits"):
                cursor.fetchone.return_value = {"is_blocked": False}
            elif query.startswith("SELECT id, name, email, password_hash"):
                cursor.fetchone.return_value = {
                    "id": 12,
                    "name": "Priya Shah",
                    "email": "priya@example.com",
                    "password_hash": password_hash,
                }
            return cursor

        connection.execute.side_effect = execute
        with patch.object(main.psycopg, "connect", return_value=connection):
            bad_response = self.client.post(
                "/auth/login",
                json={"email": "priya@example.com", "password": "incorrect-password"},
                headers=self.headers,
            )
            good_response = self.client.post(
                "/auth/login",
                json={"email": "priya@example.com", "password": "secure-pass-123"},
                headers=self.headers,
            )

        self.assertEqual(bad_response.status_code, 401)
        self.assertEqual(good_response.status_code, 200, good_response.text)
        self.assertEqual(good_response.json()["user"]["email"], "priya@example.com")
        self.assertTrue(good_response.cookies.get(main.SESSION_COOKIE_NAME))

    def test_login_rejects_pending_signup_without_creating_a_session(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection

        def execute(query, params=None):
            cursor = MagicMock()
            normalized_query = " ".join(str(query).split())
            if normalized_query.startswith("INSERT INTO auth_login_limits"):
                cursor.fetchone.return_value = {"is_blocked": False}
            elif normalized_query.startswith("SELECT id, name, email, password_hash"):
                cursor.fetchone.return_value = {
                    "id": 12,
                    "name": "Priya Shah",
                    "email": "priya@example.com",
                    "password_hash": None,
                }
            return cursor

        connection.execute.side_effect = execute
        with patch.object(main.psycopg, "connect", return_value=connection):
            response = self.client.post(
                "/auth/login",
                json={"email": "priya@example.com", "password": "secure-pass-123"},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.cookies.get(main.SESSION_COOKIE_NAME))

    def test_csrf_mismatch_rejects_registration_before_database_access(self):
        with patch.object(main.psycopg, "connect") as connect:
            response = self.client.post(
                "/auth/register",
                json={"name": "Test", "email": "test@example.com", "password": "password-123"},
                headers={**self.headers, "X-CSRF-Token": "wrong-token"},
            )

        self.assertEqual(response.status_code, 403)
        connect.assert_not_called()

    def test_ngrok_origin_passes_csrf_validation(self):
        ngrok_origin = "https://meeting-test.ngrok-free.dev"
        with (
            patch.object(runtime, "FRONTEND_ORIGINS", [ngrok_origin]),
            patch.object(runtime, "verification_configured", return_value=False),
            patch.object(main.psycopg, "connect") as connect,
        ):
            response = self.client.post(
                "/auth/register",
                json={"name": "Test", "email": "test@example.com"},
                headers={**self.headers, "Origin": ngrok_origin},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("Email verification is not configured", response.json()["detail"])
        connect.assert_not_called()

    def test_validation_response_does_not_echo_password(self):
        response = self.client.post(
            "/auth/verify-email",
            json={"email": "test@example.com", "code": "12345678", "password": "secret"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("secret", response.text)


if __name__ == "__main__":
    unittest.main()
