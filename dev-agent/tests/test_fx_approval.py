import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from decimal import Decimal as D
from agent.fx_approval import load_approved_gbp_per_usd


class FXApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "fx.json"
        self.data = {
            "base": "USD", "quote": "GBP", "gbp_per_usd": "1.00",
            "verified_by_owner": True, "verified_on": "2026-10-12",
            "expires_on": "2026-10-13", "source_url": "https://example.org/fx"
        }

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        self.path.write_text(json.dumps(self.data), encoding="utf-8")

    def test_valid_approved_record(self):
        self.write()
        self.assertEqual(load_approved_gbp_per_usd(self.path, today=date(2026,10,12)), D("1.00"))

    def test_expired_record_rejected(self):
        self.write()
        with self.assertRaises(PermissionError):
            load_approved_gbp_per_usd(self.path, today=date(2026,10,14))

    def test_unapproved_record_rejected(self):
        self.data["verified_by_owner"] = False
        self.write()
        with self.assertRaises(PermissionError):
            load_approved_gbp_per_usd(self.path, today=date(2026,10,12))

    def test_invalid_rate_rejected(self):
        self.data["gbp_per_usd"] = "NaN"
        self.write()
        with self.assertRaises(ValueError):
            load_approved_gbp_per_usd(self.path, today=date(2026,10,12))
