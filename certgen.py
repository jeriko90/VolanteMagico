"""Genera un certificado autofirmado (CA local + hoja) para servir HTTPS.

Incluye un perfil .mobileconfig para instalar/confiar la CA en el iPhone con dos toques.
"""
import base64
import datetime
import ipaddress
import logging
import os
import plistlib
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

log = logging.getLogger("volante.certgen")

CA_COMMON_NAME = "Volante Local CA"


def _new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _san_entries(lan_ips):
    entries = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ]
    for ip in lan_ips or []:
        try:
            entries.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except Exception:
            continue
    return entries


def _write_pem(path, data):
    if isinstance(data, bytes):
        payload = data
    else:
        payload = data
    with open(path, "wb") as f:
        f.write(payload)


def ensure_certs(certs_dir, lan_ips, force=False):
    """Crea (si no existen) ca.pem/ca-key.pem/cert.pem/key.pem. Devuelve las rutas."""
    ca_cert_path = os.path.join(certs_dir, "ca.pem")
    ca_key_path = os.path.join(certs_dir, "ca-key.pem")
    cert_path = os.path.join(certs_dir, "cert.pem")
    key_path = os.path.join(certs_dir, "key.pem")

    existing = all(os.path.isfile(p) for p in (ca_cert_path, ca_key_path, cert_path, key_path))
    if existing and not force:
        log.info("Certificados existentes reutilizados en %s", certs_dir)
        return cert_path, key_path, ca_cert_path

    log.info("Generando certificados nuevos (CA + hoja) en %s | IPs en SAN: %s",
             certs_dir, lan_ips)
    now = datetime.datetime.now(datetime.timezone.utc)
    not_before = now - datetime.timedelta(days=1)
    not_after = now + datetime.timedelta(days=3650)

    ca_key = _new_key()
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, CA_COMMON_NAME)])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    leaf_key = _new_key()
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Volante")])
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(leaf_name)
        .issuer_name(ca_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName(_san_entries(lan_ips)), critical=False)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .sign(ca_key, hashes.SHA256())
    )

    _write_pem(
        ca_cert_path,
        ca_cert.public_bytes(serialization.Encoding.PEM),
    )
    _write_pem(
        ca_key_path,
        ca_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    _write_pem(cert_path, leaf_cert.public_bytes(serialization.Encoding.PEM))
    _write_pem(
        key_path,
        leaf_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    log.info("Certificados generados correctamente.")
    return cert_path, key_path, ca_cert_path


def ca_der(ca_cert_path):
    with open(ca_cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    return cert.public_bytes(serialization.Encoding.DER)


def ca_pem(ca_cert_path):
    with open(ca_cert_path, "rb") as f:
        return f.read()


def build_mobileconfig(ca_cert_path, display_name="Volante Local CA"):
    """Devuelve bytes de un .mobileconfig con la CA como payload de raiz (iOS)."""
    der = ca_der(ca_cert_path)
    payload_uuid = str(uuid.uuid4()).upper()
    profile_uuid = str(uuid.uuid4()).upper()
    payload = {
        "PayloadType": "com.apple.security.root",
        "PayloadVersion": 1,
        "PayloadIdentifier": "com.volante.ca",
        "PayloadUUID": payload_uuid,
        "PayloadDisplayName": display_name,
        "PayloadContent": der,
    }
    profile = {
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": "com.volante.profile",
        "PayloadUUID": profile_uuid,
        "PayloadDisplayName": display_name,
        "PayloadRemovalDisallowed": False,
        "PayloadContent": [payload],
    }
    return plistlib.dumps(profile, fmt=plistlib.FMT_XML)
