import unittest
from agent.unattended_activation_gate import RuntimeAuthorities, require_unattended_activation_ready

class UnattendedActivationGateTests(unittest.TestCase):
    def test_defaults_block_deployment(self):
        with self.assertRaises(PermissionError):
            require_unattended_activation_ready(RuntimeAuthorities())

    def test_partial_attestation_blocks_deployment(self):
        with self.assertRaises(PermissionError):
            require_unattended_activation_ready(RuntimeAuthorities(
                authenticated_intake=True,verified_executor=True))

    def test_untrusted_attestation_type_rejected(self):
        with self.assertRaises(PermissionError):
            require_unattended_activation_ready({"independent_signer":True})

    def test_complete_attestation_is_only_preflight(self):
        values={key:True for key in RuntimeAuthorities.__dataclass_fields__}
        self.assertTrue(require_unattended_activation_ready(RuntimeAuthorities(**values)))
