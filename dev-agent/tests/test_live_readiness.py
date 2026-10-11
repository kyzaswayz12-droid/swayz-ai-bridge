import tempfile
import unittest
from pathlib import Path
from agent.live_readiness import check_readiness

class ReadinessTests(unittest.TestCase):
    def test_offline_readiness_keeps_stop_engaged(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"providers.env"
            p.write_text("OPENAI_API_KEY=example-a\nANTHROPIC_API_KEY=example-b\n")
            p.chmod(0o600)
            result=check_readiness(p,Path(folder)/"control.db")
            self.assertTrue(result.credentials_present)
            self.assertTrue(result.stopped)
            self.assertFalse(result.live_calls_enabled)
            self.assertEqual(result.budget_limit_usd,"5.0")
