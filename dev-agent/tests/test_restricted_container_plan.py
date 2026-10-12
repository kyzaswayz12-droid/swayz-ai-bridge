import unittest
from agent.restricted_container_plan import restricted_plan

IMAGE="python:3.12.7-slim@sha256:"+"a"*64

class RestrictedContainerPlanTests(unittest.TestCase):
    def test_restrictions(self):
        plan=restricted_plan(IMAGE)
        args=plan.argv
        self.assertTrue(plan.ready)
        for token in ("none","--read-only","ALL","no-new-privileges","--pids-limit","--memory","--cpus","65534:65534"):
            self.assertIn(token,args)
    def test_mutable_image_rejected(self):
        with self.assertRaises(ValueError):
            restricted_plan("python:latest")
    def test_resource_override_rejected(self):
        with self.assertRaises(ValueError):
            restricted_plan(IMAGE,cpu="4")
