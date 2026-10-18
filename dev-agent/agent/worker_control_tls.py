"""TLS certificate checks for the Swayz private worker control endpoint.

Rejects expired certificates, wrong IP identities, and mismatched private keys.
"""
import ipaddress
from datetime import datetime, timezone
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtensionOID


def verify_control_tls_identity(cert_path, key_path, *, expected_ip="10.106.0.3"):
    certificate = x509.load_pem_x509_certificate(Path(cert_path).read_bytes())
    key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
    now = datetime.now(timezone.utc)
    if not certificate.not_valid_before_utc <= now <= certificate.not_valid_after_utc:
        raise PermissionError("Control TLS certificate outside validity period")
    try:
        san = certificate.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
    except x509.ExtensionNotFound:
        raise PermissionError("Control TLS certificate missing IP SAN") from None
    if ipaddress.ip_address(expected_ip) not in san.get_values_for_type(x509.IPAddress):
        raise PermissionError("Control TLS IP identity mismatch")
    cert_public = certificate.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    key_public = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    if cert_public != key_public:
        raise PermissionError("Control TLS private key mismatch")
    return True
