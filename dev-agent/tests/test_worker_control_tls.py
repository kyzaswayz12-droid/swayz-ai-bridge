import ipaddress
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from agent.worker_control_tls import verify_control_tls_identity


class ControlTLSIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.cert_path = self.root / "cert.pem"
        self.key_path = self.root / "key.pem"
        self.key_path.write_bytes(self.key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))

    def tearDown(self):
        self.tmp.cleanup()

    def write_cert(self, ip="10.106.0.3", expired=False):
        now = datetime.now(timezone.utc)
        builder = (x509.CertificateBuilder()
                   .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "swayz-worker")]))
                   .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "swayz-worker")]))
                   .public_key(self.key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - timedelta(days=10))
                   .not_valid_after(now - timedelta(days=1) if expired else now + timedelta(days=1))
                   .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))]),
                                  critical=False))
        self.cert_path.write_bytes(builder.sign(self.key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM))

    def test_matching_certificate(self):
        self.write_cert()
        self.assertTrue(verify_control_tls_identity(self.cert_path, self.key_path))

    def test_wrong_ip_rejected(self):
        self.write_cert("10.106.0.2")
        with self.assertRaises(PermissionError):
            verify_control_tls_identity(self.cert_path, self.key_path)

    def test_expired_certificate_rejected(self):
        self.write_cert(expired=True)
        with self.assertRaises(PermissionError):
            verify_control_tls_identity(self.cert_path, self.key_path)

    def test_wrong_private_key_rejected(self):
        self.write_cert()
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.key_path.write_bytes(other.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
        with self.assertRaises(PermissionError):
            verify_control_tls_identity(self.cert_path, self.key_path)
