import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from app import runtime


class BrevoEmailDeliveryTests(unittest.TestCase):
    def test_email_verification_requires_brevo_key_and_verified_sender(self):
        with (
            patch.object(runtime, "OTP_HASH_SECRET", "test-otp-secret-" + "x" * 32),
            patch.object(runtime, "BREVO_API_KEY", "test-brevo-key"),
            patch.object(runtime, "BREVO_SENDER_EMAIL", "sender@example.com"),
        ):
            self.assertTrue(runtime.verification_configured())

        with patch.object(runtime, "BREVO_API_KEY", ""):
            self.assertFalse(runtime.verification_configured())

    def test_sends_auth_code_through_brevo_https_api(self):
        response = MagicMock()
        with (
            patch.object(runtime, "BREVO_API_KEY", "test-brevo-key"),
            patch.object(runtime, "BREVO_SENDER_EMAIL", "sender@example.com"),
            patch.object(runtime.urlrequest, "urlopen") as urlopen,
        ):
            urlopen.return_value.__enter__.return_value = response
            runtime.send_auth_code_email(
                "recipient@example.com",
                "12345678",
                "Verify your email",
                "verification",
            )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 15)
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(headers["api-key"], "test-brevo-key")
        payload = json.loads(request.data)
        self.assertEqual(payload["sender"], {"email": "sender@example.com"})
        self.assertEqual(payload["to"], [{"email": "recipient@example.com"}])
        self.assertIn("12345678", payload["textContent"])

    def test_reports_brevo_http_failures_without_exposing_response_body(self):
        error = HTTPError(
            "https://api.brevo.com/v3/smtp/email",
            401,
            "Unauthorized",
            {},
            None,
        )
        with (
            patch.object(runtime, "BREVO_API_KEY", "test-brevo-key"),
            patch.object(runtime, "BREVO_SENDER_EMAIL", "sender@example.com"),
            patch.object(runtime.urlrequest, "urlopen", side_effect=error),
            self.assertLogs("app.runtime", level="ERROR") as logs,
        ):
            with self.assertRaisesRegex(OSError, "HTTP 401"):
                runtime.send_auth_code_email(
                    "recipient@example.com",
                    "12345678",
                    "Verify your email",
                    "verification",
                )

        self.assertIn("HTTP 401", logs.output[0])
        self.assertNotIn("12345678", logs.output[0])
        self.assertNotIn("test-brevo-key", logs.output[0])
