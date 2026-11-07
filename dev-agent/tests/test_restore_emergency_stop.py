import unittest
from unittest.mock import patch
from agent.restore_emergency_stop import main

class RestoreEmergencyStopTests(unittest.TestCase):
    def test_root_engages_and_verifies(self):
        events=[]
        class Stop:
            def stop(self): events.append("stop")
            def is_stopped(self): events.append("verify"); return True
            def close(self): events.append("close")
        with patch("agent.restore_emergency_stop.os.geteuid",return_value=0), \
             patch("agent.restore_emergency_stop.EmergencyStop",return_value=Stop()):
            self.assertEqual(main(),0)
        self.assertEqual(events,["stop","verify","close"])
    def test_nonroot_rejected(self):
        with patch("agent.restore_emergency_stop.os.geteuid",return_value=995):
            with self.assertRaises(PermissionError):
                main()
    def test_unconfirmed_stop_fails(self):
        class Stop:
            def stop(self): pass
            def is_stopped(self): return False
            def close(self): pass
        with patch("agent.restore_emergency_stop.os.geteuid",return_value=0), \
             patch("agent.restore_emergency_stop.EmergencyStop",return_value=Stop()):
            with self.assertRaises(PermissionError):
                main()
