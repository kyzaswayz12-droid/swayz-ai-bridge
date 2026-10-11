import tempfile
import unittest
from pathlib import Path
from agent.collaboration_cli import main

class PaidRateGateTests(unittest.TestCase):
    def test_execute_without_approved_rate_cards_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                main(["--execute","--secrets",str(Path(d)/"missing.env"),
                      "--budget-db",str(Path(d)/"budget.db"),
                      "--control-db",str(Path(d)/"control.db")])
            self.assertFalse((Path(d)/"budget.db").exists())

    def test_disabled_mode_does_not_require_rate_cards(self):
        with tempfile.TemporaryDirectory() as d:
            import io
            from contextlib import redirect_stdout
            with redirect_stdout(io.StringIO()):
                main(["--secrets",str(Path(d)/"missing.env"),
                      "--budget-db",str(Path(d)/"budget.db"),
                      "--control-db",str(Path(d)/"control.db")])
            self.assertFalse((Path(d)/"budget.db").exists())
