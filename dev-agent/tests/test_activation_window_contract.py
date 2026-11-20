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


class LegacySnapshotRootTests(unittest.TestCase):
    """Legacy metadata may be interpreted, never rewritten or trusted broadly."""

    def test_legacy_job_directory_root(self):
        from deployment.swayz_one_shot_window import validated_snapshot_root
        job = "swayzoffline20261120a"
        snapshot = "/var/lib/swayz-executor/snapshots/" + job
        self.assertEqual(validated_snapshot_root(job, {
            "snapshot": snapshot, "snapshot_root": snapshot
        }), "/var/lib/swayz-executor/snapshots")

    def test_canonical_parent_root(self):
        from deployment.swayz_one_shot_window import validated_snapshot_root
        job = "swayzoffline20261120a"
        root = "/var/lib/swayz-executor/snapshots"
        self.assertEqual(validated_snapshot_root(job, {
            "snapshot": root + "/" + job, "snapshot_root": root
        }), root)

    def test_reject_other_snapshot_and_root(self):
        from deployment.swayz_one_shot_window import validated_snapshot_root
        job = "swayzoffline20261120a"
        root = "/var/lib/swayz-executor/snapshots"
        for snapshot, supplied_root in (
            (root + "/different", root + "/different"),
            (root + "/" + job, "/tmp"),
            ("/tmp/" + job, "/tmp"),
        ):
            with self.subTest(snapshot=snapshot, supplied_root=supplied_root):
                with self.assertRaises(PermissionError):
                    validated_snapshot_root(job, {
                        "snapshot": snapshot, "snapshot_root": supplied_root
                    })
