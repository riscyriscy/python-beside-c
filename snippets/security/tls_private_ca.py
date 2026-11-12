"""Private CA, device certificate and a TLS status server.

Run: python3 tls_private_ca.py
"""

from __future__ import annotations

import datetime as dt
import inspect
import socket
import ssl
import tempfile
import textwrap
import threading
from pathlib import Path

import httpx
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

HOST = "tlm-100.local"
PEM = serialization.Encoding.PEM


def issue(
    cn: str,
    key: ec.EllipticCurvePrivateKey,
    ca: tuple[x509.Certificate, ec.EllipticCurvePrivateKey] | None = None,
) -> x509.Certificate:
    """Self-signed CA certificate when ca is None, else a server certificate."""
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = dt.datetime.now(dt.UTC)
    b = (
        x509.CertificateBuilder()
        .subject_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + dt.timedelta(days=365))
    )
    ski = x509.SubjectKeyIdentifier.from_public_key(key.public_key())
    b = b.add_extension(ski, critical=False)
    if ca is None:
        b = b.issuer_name(name)
        b = b.add_extension(x509.BasicConstraints(True, 0), critical=True)
        usage = x509.KeyUsage(
            False, False, False, False, False, True, True, False, False
        )  # key_cert_sign and crl_sign
        b = b.add_extension(usage, critical=True)
    else:
        issuer, ca_key = ca
        aki = x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key())
        b = b.issuer_name(issuer.subject).add_extension(aki, critical=False)
        b = b.add_extension(x509.SubjectAlternativeName([x509.DNSName(cn)]), False)
    return b.sign(ca[1] if ca else key, hashes.SHA256())


def serve(ctx: ssl.SSLContext, listener: socket.socket, n: int) -> None:
    """Answer n connections with one status line; a failed handshake is dropped."""
    for _ in range(n):
        conn, _addr = listener.accept()
        try:
            with ctx.wrap_socket(conn, server_side=True) as tls:
                tls.sendall(b"TLM-100 ok\n")
        except OSError:
            pass


def ask(ctx: ssl.SSLContext, port: int, name: str) -> str:
    try:
        addr = ("127.0.0.1", port)
        with (
            socket.create_connection(addr, timeout=3) as raw,
            ctx.wrap_socket(raw, server_hostname=name) as tls,
        ):
            reply = tls.recv(64).decode().strip()
            cipher = tls.cipher()
            return f"{reply} via {tls.version()}, {cipher[0] if cipher else '?'}"
    except ssl.SSLCertVerificationError as e:
        return f"{type(e).__name__} {e.reason}: {e.verify_message}"


def show(label: str, text: str) -> None:
    print(textwrap.fill(f"{label}: {text}", 84, subsequent_indent="    "))


def main() -> None:
    ca_key = ec.generate_private_key(ec.SECP256R1())
    dev_key = ec.generate_private_key(ec.SECP256R1())
    ca_cert = issue("Test CA", ca_key)
    dev_cert = issue(HOST, dev_key, (ca_cert, ca_key))
    with tempfile.TemporaryDirectory() as d:
        ca_pem, crt, key = Path(d, "ca.pem"), Path(d, "dev.pem"), Path(d, "dev.key")
        ca_pem.write_bytes(ca_cert.public_bytes(PEM))
        crt.write_bytes(dev_cert.public_bytes(PEM))
        fmt = serialization.PrivateFormat.PKCS8
        key.write_bytes(dev_key.private_bytes(PEM, fmt, serialization.NoEncryption()))
        server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ctx.load_cert_chain(crt, key)
        listener = socket.create_server(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        t = threading.Thread(target=serve, args=(server_ctx, listener, 4))
        t.start()
        good = ssl.create_default_context(cafile=str(ca_pem))
        show("trusted CA", ask(good, port, HOST))
        show("wrong hostname", ask(good, port, "tlm-200.local"))
        show("CA not trusted", ask(ssl.create_default_context(), port, HOST))
        bad = ssl.create_default_context()
        bad.check_hostname, bad.verify_mode = False, ssl.CERT_NONE  # accepts anyone
        show("checks disabled", ask(bad, port, "anything.example"))
        t.join()
        listener.close()
    print("httpx default timeout:", httpx.Client().timeout)
    sig = inspect.signature(requests.Session.request)
    print("requests timeout default:", sig.parameters["timeout"].default)


if __name__ == "__main__":
    main()
