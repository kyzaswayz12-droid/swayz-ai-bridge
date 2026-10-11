import tempfile
from pathlib import Path
import unittest
from agent.core import Policy, State, TaskStore

class CoordinatorTests(unittest.TestCase):
    def test_durable_claim_and_state_transitions(self):
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/"tasks.sqlite")
            first=TaskStore(path)
            self.assertTrue(first.enqueue("task-1","Review paper risk engine"))
            self.assertFalse(first.enqueue("task-1","Review paper risk engine"))
            first.close()
            store=TaskStore(path)
            self.assertEqual(store.claim_next(),("task-1","Review paper risk engine"))
            self.assertIsNone(store.claim_next())
            for before,after in [
                (State.CLAIMED,State.CODE_READY),
                (State.CODE_READY,State.REVIEW_REQUIRED),
                (State.REVIEW_REQUIRED,State.APPROVAL_REQUIRED),
                (State.APPROVAL_REQUIRED,State.COMPLETE),
            ]:
                store.transition("task-1",before,after)
            self.assertEqual(store.status(),{"complete":1})
            self.assertEqual(store.db.execute("SELECT COUNT(*) FROM audit").fetchone()[0],6)
            store.close()

    def test_invalid_transition_is_rejected(self):
        store=TaskStore()
        store.enqueue("task","Example")
        with self.assertRaises(ValueError):
            store.transition("task",State.PENDING,State.COMPLETE)
        self.assertEqual(store.status(),{"pending":1})
        store.close()

    def test_staging_policy_forbids_external_actions(self):
        Policy("owner/repo")
        for field in ("enable_model_calls","enable_git_writes","enable_deployment","enable_live_trading"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    Policy("owner/repo",**{field:True})
