import unittest
from agent.change_set import validate_change_set

class ChangeSetTests(unittest.TestCase):
    def test_safe_changes(self):
        self.assertEqual(validate_change_set({"tests/test_risk.py":"assert True"}),{"tests/test_risk.py":"assert True"})
    def test_traversal_rejected(self):
        for path in ("../secret.py","tests/../secret.py","/tmp/file.py","tests//bad.py"):
            with self.subTest(path=path),self.assertRaises(ValueError):
                validate_change_set({path:"x"})
    def test_secret_path_rejected(self):
        with self.assertRaises(ValueError):
            validate_change_set({"secrets/keys.json":"key"})
    def test_executable_extension_rejected(self):
        with self.assertRaises(ValueError):
            validate_change_set({"script.sh":"echo hi"})
    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            validate_change_set({})
