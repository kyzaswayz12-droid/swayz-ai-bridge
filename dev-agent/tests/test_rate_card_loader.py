import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from decimal import Decimal as D
from agent.rate_card_loader import load_rate_card

class RateCardLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"rates.json"
        self.data={"provider":"openai","model":"example-model",
                   "verified_by_owner":True,"verified_on":"2026-10-11",
                   "expires_on":"2026-10-18",
                   "input_per_million_usd":"1.00",
                   "output_per_million_usd":"4.00",
                   "source_url":"https://example.com/pricing"}
    def save(self):
        self.path.write_text(json.dumps(self.data))
    def test_verified_rate_card(self):
        self.save()
        card=load_rate_card(self.path,"openai","example-model",today=date(2026,10,11))
        self.assertEqual(card.output_per_million,D("4.00"))
    def test_expired_card_rejected(self):
        self.save()
        with self.assertRaises(PermissionError):
            load_rate_card(self.path,"openai","example-model",today=date(2026,10,19))
    def test_unverified_card_rejected(self):
        self.data["verified_by_owner"]=False
        self.save()
        with self.assertRaises(PermissionError):
            load_rate_card(self.path,"openai","example-model",today=date(2026,10,11))
    def test_wrong_model_rejected(self):
        self.save()
        with self.assertRaises(ValueError):
            load_rate_card(self.path,"openai","other",today=date(2026,10,11))
