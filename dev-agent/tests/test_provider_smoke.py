import tempfile
import unittest
from pathlib import Path
from agent.provider_smoke import smoke
from agent.emergency_stop import EmergencyStop

class ProviderSmokeTests(unittest.TestCase):
    def test_disabled_mode_never_loads_secrets_or_calls_provider(self):
        with tempfile.TemporaryDirectory() as d:
            def forbidden(*args,**kwargs):
                raise AssertionError("network attempted")
            result=smoke("openai",secrets=Path(d)/"missing.env",
                         budget_db=Path(d)/"ledger.db",model="test",
                         execute=False,transport=forbidden)
            self.assertEqual(result["state"],"disabled")
            self.assertFalse((Path(d)/"ledger.db").exists())

    def test_explicit_mock_request_reserves_budget(self):
        with tempfile.TemporaryDirectory() as d:
            secret=Path(d)/"providers.env"
            secret.write_text("OPENAI_API_KEY=example-a\nANTHROPIC_API_KEY=example-b\n")
            secret.chmod(0o600)
            budget=Path(d)/"budget.db"
            control=Path(d)/"control.db"
            stop=EmergencyStop(str(control))
            self.assertTrue(stop.is_stopped())
            stop.close()
            def mock(provider,payload,key):
                self.assertEqual(key,"example-a")
                return b'{"output":[{"content":[{"type":"output_text","text":"OK"}]}],"usage":{"input_tokens":5,"output_tokens":1}}'
            result=smoke("openai",secrets=secret,budget_db=budget,
                         model="test-model",control_db=control,execute=True,transport=mock)
            self.assertEqual(result["state"],"responded")
            self.assertEqual(result["reservation_usd"],"0.10")
            self.assertTrue(budget.is_file())

    def test_failed_request_retains_reservation(self):
        with tempfile.TemporaryDirectory() as d:
            secret=Path(d)/"providers.env"
            secret.write_text("OPENAI_API_KEY=example-a\nANTHROPIC_API_KEY=example-b\n")
            secret.chmod(0o600)
            budget=Path(d)/"budget.db"
            control=Path(d)/"control.db"
            stop=EmergencyStop(str(control))
            self.assertTrue(stop.is_stopped())
            stop.close()
            def fail(*args):
                raise TimeoutError("provider unavailable")
            with self.assertRaises(TimeoutError):
                smoke("openai",secrets=secret,budget_db=budget,
                      model="test-model",control_db=control,execute=True,transport=fail)
            import sqlite3
            with sqlite3.connect(budget) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0],1)

    def test_missing_stop_rejected_without_spend(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PermissionError):
                smoke("openai",secrets=Path(d)/"missing.env",
                      budget_db=Path(d)/"budget.db",
                      control_db=Path(d)/"missing-control.db",
                      model="test-model",execute=True,
                      transport=lambda *args:None)
            self.assertFalse((Path(d)/"budget.db").exists())

    def test_disengaged_stop_rejected_without_spend(self):
        with tempfile.TemporaryDirectory() as d:
            control=Path(d)/"control.db"
            stop=EmergencyStop(str(control))
            stop.enable(owner_authorised=True)
            stop.close()
            with self.assertRaises(PermissionError):
                smoke("openai",secrets=Path(d)/"missing.env",
                      budget_db=Path(d)/"budget.db",control_db=control,
                      model="test-model",execute=True,
                      transport=lambda *args:None)
            self.assertFalse((Path(d)/"budget.db").exists())
