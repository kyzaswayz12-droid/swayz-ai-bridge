import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from agent.collaboration_cli import main

class CollaborationCLITests(unittest.TestCase):
    def test_default_mode_no_credentials_no_network_no_db(self):
        with tempfile.TemporaryDirectory() as d:
            secret=Path(d)/"missing.env"
            budget=Path(d)/"budget.db"
            stop=Path(d)/"stop.db"
            out=io.StringIO()
            with redirect_stdout(out):
                main(["--secrets",str(secret),"--budget-db",str(budget),
                      "--control-db",str(stop)])
            self.assertEqual(json.loads(out.getvalue())["state"],"disabled")
            self.assertFalse(budget.exists())
            self.assertFalse(stop.exists())
