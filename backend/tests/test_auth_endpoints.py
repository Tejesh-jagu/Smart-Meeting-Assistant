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

    def test_registration_hashes_password_and_sets_http_only_session(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection

        def execute(query, params=None):
            cursor = MagicMock()
            query = " ".join(str(query).split())
            if query.startswith("SELECT NOT EXISTS"):
                cursor.fetchone.return_value = {"is_first_user": False}
            elif query.startswith("INSERT INTO app_users"):
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
        ):
            response = self.client.post(
                "/auth/register",
                json={
                    "name": " Priya   Shah ",
                    "email": "PRIYA@example.com",
                    "password": "secure-pass-123",
                },
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["user"]["name"], "Priya Shah")
        self.assertNotIn("password", response.json())
        self.assertTrue(response.cookies.get(main.SESSION_COOKIE_NAME))
        self.assertIn("httponly", response.headers["set-cookie"].casefold())
        insert_call = next(
            call for call in connection.execute.call_args_list
            if "INSERT INTO app_users" in str(call.args[0])
        )
        self.assertNotEqual(insert_call.args[1][2], "secure-pass-123")
        self.assertTrue(main.password_hasher.verify(insert_call.args[1][2], "secure-pass-123"))

    def test_registration_rate_limit_rejects_before_hashing_or_inserting(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        with (
            patch.object(main.psycopg, "connect", return_value=connection),
            patch.object(runtime, "consume_rate_limit", return_value=False),
        ):
            response = self.client.post(
                "/auth/register",
                json={
                    "name": "Priya Shah",
                    "email": "priya@example.com",
                    "password": "secure-pass-123",
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

    def test_csrf_mismatch_rejects_registration_before_database_access(self):
        with patch.object(main.psycopg, "connect") as connect:
            response = self.client.post(
                "/auth/register",
                json={"name": "Test", "email": "test@example.com", "password": "password-123"},
                headers={**self.headers, "X-CSRF-Token": "wrong-token"},
            )

        self.assertEqual(response.status_code, 403)
        connect.assert_not_called()

    def test_validation_response_does_not_echo_password(self):
        response = self.client.post(
            "/auth/register",
            json={"name": "Test", "email": "test@example.com", "password": "secret"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("secret", response.text)


if __name__ == "__main__":
    unittest.main()
