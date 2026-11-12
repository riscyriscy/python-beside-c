"""TLS cases a device fleet meets: IP address, clock, key usage, no SAN, mutual TLS, stalled clients.

Run: python3 tls_fleet_cases.py  (needs the cryptography package)
"""

from __future__ import annotations

import datetime as dt
import http.server
import ipaddress
import socket
import ssl
import sys
import tempfile
import textwrap
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID as EKU
from cryptography.x509.oid import NameOID

PEM = serialization.Encoding.PEM
NOW = dt.datetime.now(dt.UTC)
NAME = "tlm-100.local"
Key = ec.EllipticCurvePrivateKey
Pair = tuple[x509.Certificate, Key]


def issue(
    cn: str,
    key: Key,
    ca: Pair | None = None,
    *,
    san: list[x509.GeneralName] | None = None,
    eku: list[x509.ObjectIdentifier] | None = None,
    start: dt.datetime = NOW,
) -> x509.Certificate:
    """A CA certificate when ca is None, else a leaf with the given names and purpose."""
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    b = (
        x509.CertificateBuilder()
        .subject_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(start)
        .not_valid_after(start + dt.timedelta(days=365))
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
    )
    if ca is None:
        usage = x509.KeyUsage(False, False, False, False, False, True, True, False, False)
        b = b.issuer_name(name).add_extension(x509.BasicConstraints(True, 0), True)
        b = b.add_extension(usage, True)
    else:
        aki = x509.AuthorityKeyIdentifier.from_issuer_public_key(ca[1].public_key())
        b = b.issuer_name(ca[0].subject).add_extension(aki, False)
        if san:
            b = b.add_extension(x509.SubjectAlternativeName(san), False)
        if eku:
            b = b.add_extension(x509.ExtendedKeyUsage(eku), False)
    return b.sign(ca[1] if ca else key, hashes.SHA256())


class Pki:
    """A private CA and the files that ssl wants."""

    def __init__(self, folder: str) -> None:
        self.folder, self.key = folder, ec.generate_private_key(ec.SECP256R1())
        self.cert = issue("Test CA", self.key)
        self.ca_pem = self._write("ca", self.cert)[0]

    def _write(self, stem: str, cert: x509.Certificate, key: Key | None = None) -> tuple[str, str]:
        pem, kf = Path(self.folder, stem + ".pem"), Path(self.folder, stem + ".key")
        pem.write_bytes(cert.public_bytes(PEM))
        if key:
            fmt = serialization.PrivateFormat.PKCS8
            kf.write_bytes(key.private_bytes(PEM, fmt, serialization.NoEncryption()))
        return str(pem), str(kf)

    def leaf(self, stem: str, cn: str, **kw: Any) -> tuple[str, str]:
        key = ec.generate_private_key(ec.SECP256R1())
        return self._write(stem, issue(cn, key, (self.cert, self.key), **kw), key)

    def client_ctx(self, cert: tuple[str, str] | None = None) -> ssl.SSLContext:
        ctx = ssl.create_default_context(cafile=self.ca_pem)
        if cert:
            ctx.load_cert_chain(*cert)
        return ctx


def show(label: str, text: str) -> None:
    print(textwrap.fill(f"{label}: {text}", 84, subsequent_indent="    "))


def one_shot(
    pki: Pki,
    cert: tuple[str, str],
    name: str,
    *,
    mutual: bool = False,
    client_cert: tuple[str, str] | None = None,
) -> str:
    """One handshake against a one-connection server; report both ends."""
    sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    sctx.load_cert_chain(*cert)
    if mutual:
        sctx.verify_mode = ssl.CERT_REQUIRED
        sctx.load_verify_locations(pki.ca_pem)
    lst = socket.create_server(("127.0.0.1", 0))
    seen: list[str] = []

    def serve() -> None:
        conn, _ = lst.accept()
        try:
            with sctx.wrap_socket(conn, server_side=True) as tls:
                der = tls.getpeercert(binary_form=True)
                subject = x509.load_der_x509_certificate(der).subject if der else None
                cn = (
                    subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value if subject else b""
                )
                seen.append("server ok" + (f", peer {cn!s}" if cn else ""))
                tls.sendall(b"ok\n")
        except ssl.SSLError as e:
            seen.append(f"server {e.reason}")
        except OSError as e:
            seen.append(f"server {type(e).__name__}")

    t = threading.Thread(target=serve)
    t.start()
    try:
        with (
            socket.create_connection(lst.getsockname(), timeout=3) as raw,
            pki.client_ctx(client_cert).wrap_socket(raw, server_hostname=name) as tls,
        ):
            out = "client handshake ok"
            try:
                out += f", read {tls.recv(8)!r}"
            except OSError as e:
                out += f", first read raised {type(e).__name__}"
    except ssl.SSLCertVerificationError as e:
        out = f"client: {e.verify_message}"
    t.join()
    lst.close()
    return out + " | " + "; ".join(seen)


def stalled_client(pki: Pki, label: str, make: Callable[[], http.server.HTTPServer]) -> None:
    """Open a TCP connection that sends nothing, then try a good client, with a 2 s limit."""

    srv = make()
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    silent = socket.create_connection(("127.0.0.1", port))
    time.sleep(0.2)
    t0 = time.perf_counter()
    try:
        with (
            socket.create_connection(("127.0.0.1", port), timeout=2) as raw,
            pki.client_ctx().wrap_socket(raw, server_hostname=NAME) as tls,
        ):
            tls.sendall(b"GET / HTTP/1.0\r\n\r\n")
            res = tls.recv(64).split(b"\r\n")[0].decode()
    except OSError as e:
        res = type(e).__name__
    show(label, f"{res} after {time.perf_counter() - t0:.2f} s")
    silent.close()
    srv.shutdown()
    srv.server_close()


class Status(http.server.BaseHTTPRequestHandler):
    timeout = 2  # seconds a connection may stay silent once the handler owns it

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Length", "3")
        self.end_headers()
        self.wfile.write(b"ok\n")

    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        pki = Pki(folder)
        dns: list[x509.GeneralName] = [x509.DNSName(NAME)]
        addr = x509.IPAddress(ipaddress.ip_address("127.0.0.1"))
        day = dt.timedelta(days=1)
        both = [*dns, addr]
        cases: list[tuple[str, dict[str, Any], str]] = [
            ("DNS-only SAN, client connects by IP", {"san": dns}, "127.0.0.1"),
            ("SAN has the IP address too", {"san": both}, "127.0.0.1"),
            ("notBefore is tomorrow", {"san": dns, "start": NOW + day}, NAME),
            ("expired 35 days ago", {"san": dns, "start": NOW - 400 * day}, NAME),
            ("clientAuth only, used as a server", {"san": dns, "eku": [EKU.CLIENT_AUTH]}, NAME),
            ("CN only, no SAN", {}, NAME),
        ]
        for i, (label, kw, name) in enumerate(cases):
            show(f"{i + 1} {label}", one_shot(pki, pki.leaf(f"c{i}", NAME, **kw), name))
        server = pki.leaf("srv", NAME, san=both, eku=[EKU.SERVER_AUTH])
        station = pki.leaf("station", "station-01", eku=[EKU.CLIENT_AUTH])
        show(
            "7 mutual TLS, client has a certificate",
            one_shot(pki, server, NAME, mutual=True, client_cert=station),
        )
        show("8 mutual TLS, client has none", one_shot(pki, server, NAME, mutual=True))

        def https(
            cls: type[http.server.HTTPServer], lazy: bool
        ) -> Callable[[], http.server.HTTPServer]:
            def make() -> http.server.HTTPServer:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(*server)
                srv = cls(("127.0.0.1", 0), Status)
                srv.socket = ctx.wrap_socket(
                    srv.socket, server_side=True, do_handshake_on_connect=not lazy
                )
                return srv

            return make

        stalled_client(
            pki, "9 HTTPServer, handshake in accept()", https(http.server.HTTPServer, False)
        )
        stalled_client(
            pki,
            "10 ThreadingHTTPServer, lazy handshake",
            https(http.server.ThreadingHTTPServer, True),
        )
        if sys.version_info >= (3, 14):
            stalled_client(
                pki,
                "11 ThreadingHTTPSServer (3.14)",
                lambda: http.server.ThreadingHTTPSServer(
                    ("127.0.0.1", 0), Status, certfile=server[0], keyfile=server[1]
                ),
            )


if __name__ == "__main__":
    main()
