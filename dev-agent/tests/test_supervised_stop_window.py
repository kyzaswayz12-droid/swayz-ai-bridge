import unittest
from unittest.mock import patch
from agent.supervised_stop_window import run_supervised_window

class SupervisedStopWindowTests(unittest.TestCase):
    def setUp(self):
        self.events=[]
    def invoke(self,**overrides):
        class Control:
            def is_stopped(inner):
                self.events.append("initial_stop")
                return True
            def enable(inner,**kw):
                self.events.append("enable")
            def stop(inner):
                self.events.append("stop")
            def close(inner):
                self.events.append("close")
        args=dict(job_id="job1",stop_db="/var/lib/swayzcontrol/state/stop.db",
            verify_operator=lambda **kw:True,
            verify_prepared_job=lambda **kw:True,
            execute_once=lambda **kw:{"state":"passed","cleanup_verified":True})
        args.update(overrides)
        with patch("agent.supervised_stop_window.os.geteuid",return_value=0), \
             patch("agent.supervised_stop_window.EmergencyStop",return_value=Control()):
            return run_supervised_window(**args)
    def test_pass_restores_stop(self):
        self.assertEqual(self.invoke()["state"],"passed")
        self.assertEqual(self.events[-2:],["stop","close"])
    def test_failed_execution_restores_stop(self):
        self.assertEqual(self.invoke(execute_once=lambda **kw:{"state":"failed"})["state"],"blocked")
        self.assertEqual(self.events[-2:],["stop","close"])
    def test_exception_restores_stop(self):
        def fail(**kw):
            raise RuntimeError("executor failed")
        with self.assertRaises(RuntimeError):
            self.invoke(execute_once=fail)
        self.assertEqual(self.events[-2:],["stop","close"])
    def test_unauthorised_never_enables(self):
        with self.assertRaises(PermissionError):
            self.invoke(verify_operator=lambda **kw:False)
        self.assertEqual(self.events,[])
    def test_unprepared_never_enables(self):
        with self.assertRaises(PermissionError):
            self.invoke(verify_prepared_job=lambda **kw:False)
        self.assertEqual(self.events,[])
    def test_nonroot_rejected(self):
        with patch("agent.supervised_stop_window.os.geteuid",return_value=995):
            with self.assertRaises(PermissionError):
                run_supervised_window(job_id="job1",stop_db="/var/lib/swayzcontrol/state/stop.db",
                    verify_operator=lambda **kw:True,
                    verify_prepared_job=lambda **kw:True,
                    execute_once=lambda **kw:None)
