"""Offline acceptance contract for a supervised activation window.

No server changes, no stop release, no systemd or Docker. The tests specify
the required sequencing for the eventual privileged operator entrypoint.
"""
import unittest
from unittest.mock import Mock


def simulate_window(*, arm_watchdog, release, prepare, dispatch, restore):
    """Test-only orchestration; NEVER deploy as an operator entrypoint."""
    armed = False
    try:
        arm_watchdog()
        armed = True
        release()
        prepare()
        return dispatch()
    finally:
        # Restore even when watchdog setup fails: fail closed.
        restore()


class ActivationWindowContractTests(unittest.TestCase):
    def setUp(self):
        self.events = []

    def step(self, name, failure=None):
        def action():
            self.events.append(name)
            if failure == name:
                raise RuntimeError(name)
            if name == "dispatch":
                return {"state": "passed", "cleanup_verified": True}
        return action

    def invoke(self, failure=None):
        return simulate_window(
            arm_watchdog=self.step("watchdog", failure),
            release=self.step("release", failure),
            prepare=self.step("prepare", failure),
            dispatch=self.step("dispatch", failure),
            restore=self.step("restore", failure))

    def test_successful_order_and_restoration(self):
        self.assertEqual(self.invoke()["state"], "passed")
        self.assertEqual(self.events, ["watchdog","release","prepare","dispatch","restore"])

    def test_watchdog_failure_never_releases(self):
        with self.assertRaises(RuntimeError):
            self.invoke("watchdog")
        self.assertEqual(self.events, ["watchdog","restore"])

    def test_release_failure_never_prepares(self):
        with self.assertRaises(RuntimeError):
            self.invoke("release")
        self.assertEqual(self.events, ["watchdog","release","restore"])

    def test_preparation_failure_never_dispatches(self):
        with self.assertRaises(RuntimeError):
            self.invoke("prepare")
        self.assertEqual(self.events, ["watchdog","release","prepare","restore"])

    def test_dispatch_failure_restores_without_retry(self):
        with self.assertRaises(RuntimeError):
            self.invoke("dispatch")
        self.assertEqual(self.events, ["watchdog","release","prepare","dispatch","restore"])
