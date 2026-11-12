"""Exercise the status server with urllib (stdlib). Run: python3 http_client.py"""

from __future__ import annotations

import http.client
import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any

import status_server

server = status_server.serve(port=0)  # port 0: any free port, handy for tests
BASE = f"http://127.0.0.1:{server.server_address[1]}"
time.sleep(0.35)  # let a few samples accumulate


def call(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:  # always set a timeout
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as e:  # 4xx/5xx arrive as exceptions in urllib
        return e.code, json.load(e)


for method, path, body in [
    ("GET", "/api/status", None),
    ("GET", "/api/telemetry?last=3", None),
    ("POST", "/api/rate", {"period_ms": 250}),
    ("POST", "/api/rate", {"period_ms": 5}),
    ("POST", "/api/rate", {"period_ms": 25.7}),
    ("POST", "/api/rate", {"period_ms": "50"}),
    ("POST", "/api/rate", {"rate": 1}),
    ("GET", "/api/telemetry?last=abc", None),
    ("GET", "/api/nothing", None),
]:
    status, reply = call(method, path, body)
    print(f"{method:<5}{path:<26}{status}  {json.dumps(reply)[:68]}")

# urllib always sends a correct Content-Length, so a bad one needs http.client
for length in ("abc", "-1"):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
    conn.putrequest("POST", "/api/rate")
    conn.putheader("Content-Length", length)
    conn.endheaders()
    answer = conn.getresponse()
    print(f"POST /api/rate, Content-Length {length:<4}  {answer.status}  {answer.read().decode()}")
    conn.close()

# a client that declares a body and then goes quiet: Handler.timeout ends the wait
stalled = socket.create_connection(("127.0.0.1", server.server_address[1]))
stalled.sendall(b"POST /api/rate HTTP/1.1\r\nContent-Length: 100\r\n\r\n" + b'{"period_ms":')
started = time.monotonic()
stalled.settimeout(10)
reply = stalled.recv(4096)  # b"" means the server closed the connection
print(
    f"POST /api/rate, 13 of 100 body bytes, then silence: "
    f"{len(reply)} reply bytes after {time.monotonic() - started:.0f} s"
)
stalled.close()

with urllib.request.urlopen(BASE + "/", timeout=2) as resp:
    print(
        f"GET  /                         {resp.status}  {resp.headers['Content-Type']}, "
        f"{len(resp.read())} bytes of HTML"
    )
server.shutdown()
