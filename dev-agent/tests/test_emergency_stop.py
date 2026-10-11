import tempfile
import unittest
from pathlib import Path
from agent.emergency_stop import EmergencyStop

class EmergencyStopTests(unittest.TestCase):
    def test_default_stopped_and_restart_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            path=str(Path(folder)/"control.db")
            first=EmergencyStop(path)
            self.assertTrue(first.is_stopped())
            with self.assertRaises(PermissionError):
                first.require_running()
            with self.assertRaises(PermissionError):
                first.enable()
            first.enable(owner_authorised=True)
            first.close()
            second=EmergencyStop(path)
            self.assertFalse(second.is_stopped())
            second.stop()
            second.close()
            third=EmergencyStop(path)
            self.assertTrue(third.is_stopped())
            third.close()

    def test_missing_record_fails_closed(self):
        stop=EmergencyStop(":memory:")
        stop.db.execute("DELETE FROM agent_control")
        self.assertTrue(stop.is_stopped())
        with self.assertRaises(ValueError):
            stop.enable(owner_authorised=True)
        stop.close()
