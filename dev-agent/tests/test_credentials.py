import unittest
from agent.credentials import credential_status,require_credentials

class CredentialsTests(unittest.TestCase):
    def test_status_only_returns_presence(self):
        status=credential_status({"OPENAI_API_KEY":"secret-1","ANTHROPIC_API_KEY":"secret-2"})
        self.assertTrue(status.openai_configured)
        self.assertTrue(status.anthropic_configured)
        self.assertNotIn("secret",repr(status))

    def test_missing_keys_fail_closed(self):
        with self.assertRaises(ValueError):
            require_credentials({"OPENAI_API_KEY":"present"})

    def test_whitespace_not_valid(self):
        status=credential_status({"OPENAI_API_KEY":" ","ANTHROPIC_API_KEY":""})
        self.assertFalse(status.openai_configured)
