"""tls: a locally self-signed certificate, created once and reused. Carried from
ai_project_planning_server/tls.py (RSA 2048, CN/SAN localhost + 127.0.0.1, 10 years, key 0600)."""
from __future__ import annotations

import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CERT_NAME, KEY_NAME = "server.crt", "server.key"


def ensure_self_signed_cert(cert_dir: Path) -> tuple[Path, Path]:
    cert_dir = Path(cert_dir)
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert, key = cert_dir / CERT_NAME, cert_dir / KEY_NAME
    if cert.exists() and key.exists():
        return cert, key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(
            [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .sign(private_key, hashes.SHA256())
    )
    key.write_bytes(private_key.private_bytes(serialization.Encoding.PEM,
                                              serialization.PrivateFormat.TraditionalOpenSSL,
                                              serialization.NoEncryption()))
    try:
        key.chmod(0o600)
    except OSError:
        pass
    cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return cert, key
