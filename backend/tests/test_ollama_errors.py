import unittest

from ollama_errors import connection_error_message, http_error_message


class OllamaErrorMessageTests(unittest.TestCase):
    def test_missing_model_message_suggests_pull_command(self):
        message = http_error_message(404, "llama3.2:3b")
        self.assertIn("llama3.2:3b", message)
        self.assertIn("ollama pull llama3.2:3b", message)

    def test_other_http_errors_include_status(self):
        self.assertIn("HTTP 500", http_error_message(500, "llama3.2:3b"))

    def test_connection_error_hides_credentials_and_query_parameters(self):
        message = connection_error_message(
            "https://private-user:secret-value@ollama.example:11434/api?token=secret-token"
        )
        self.assertIn("https://ollama.example:11434", message)
        self.assertNotIn("private-user", message)
        self.assertNotIn("secret-value", message)
        self.assertNotIn("secret-token", message)
        self.assertNotIn("/api", message)
        self.assertIn("Ollama is running", message)


if __name__ == "__main__":
    unittest.main()
