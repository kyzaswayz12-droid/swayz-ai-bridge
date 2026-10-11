import json
import unittest
from datetime import datetime,timezone
from decimal import Decimal as D
from agent.budget import BudgetStore,BudgetLimits
from agent.dispatcher import DispatchPolicy,dispatch_review_request

NOW=datetime(2026,10,11,tzinfo=timezone.utc)

class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.budget=BudgetStore()
        self.limits=BudgetLimits(D("1"),3,D("0.5"))
        self.calls=0

    def tearDown(self):
        self.budget.close()

    def transport(self,provider,payload,key):
        self.calls+=1
        self.assertEqual(key,"dummy-key")
        return json.dumps({"output":[{"content":[{"type":"output_text","text":"Proposal"}]}],
            "usage":{"input_tokens":10,"output_tokens":2}}).encode()

    def call(self,request_id="one",policy=DispatchPolicy(True),transport=None):
        return dispatch_review_request(provider="openai",request_id=request_id,
            model="test-model",instruction="Review",task="Mock code",
            api_key="dummy-key",transport=transport or self.transport,
            budget=self.budget,limits=self.limits,
            estimated_cost_usd=D("0.2"),now=NOW,policy=policy)

    def test_disabled_does_not_reserve_or_call(self):
        with self.assertRaises(PermissionError):
            self.call(policy=DispatchPolicy())
        self.assertEqual(self.calls,0)
        self.assertEqual(self.budget.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0],0)

    def test_mock_dispatch_and_duplicate_rejection(self):
        self.assertEqual(self.call().text,"Proposal")
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            self.call()
        self.assertEqual(self.calls,1)

    def test_transport_failure_retains_reservation(self):
        def broken(provider,payload,key):
            raise TimeoutError("unknown billing outcome")
        with self.assertRaises(TimeoutError):
            self.call(transport=broken)
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            self.call()
        self.assertEqual(self.calls,0)

    def test_invalid_response_retains_reservation(self):
        with self.assertRaises(ValueError):
            self.call(transport=lambda provider,payload,key:b"{}")
        self.assertEqual(self.budget.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0],1)
