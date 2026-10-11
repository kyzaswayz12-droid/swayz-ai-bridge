import json
import unittest
from datetime import datetime,timezone
from decimal import Decimal as D
from agent.activation import Activation,run_provider_call
from agent.budget import BudgetStore,BudgetLimits

class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.budget=BudgetStore()
        self.called=0

    def tearDown(self):
        self.budget.close()

    def fake(self,provider,payload,key):
        self.called+=1
        return json.dumps({"output":[{"content":[{"type":"output_text","text":"OK"}]}],
            "usage":{"input_tokens":5,"output_tokens":1}}).encode()

    def call(self,activation):
        return run_provider_call(
            activation=activation,provider="openai",request_id="req-1",
            model="test",instruction="Review",task="Test",api_key="dummy",
            budget=self.budget,limits=BudgetLimits(D("1"),3,D("0.5")),
            estimate_usd=D("0.1"),
            now=datetime(2026,10,11,tzinfo=timezone.utc),transport=self.fake)

    def test_default_activation_fails_closed(self):
        with self.assertRaises(PermissionError):
            self.call(Activation())
        self.assertEqual(self.called,0)
        self.assertEqual(self.budget.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0],0)

    def test_owner_approval_alone_is_insufficient(self):
        with self.assertRaises(PermissionError):
            self.call(Activation(owner_approved=True))

    def test_approved_mock_call(self):
        result=self.call(Activation(owner_approved=True,provider_calls_enabled=True))
        self.assertEqual(result.text,"OK")
        self.assertEqual(self.called,1)

    def test_git_write_activation_rejected(self):
        with self.assertRaises(PermissionError):
            self.call(Activation(owner_approved=True,provider_calls_enabled=True,git_writes_enabled=True))
