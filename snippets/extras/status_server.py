"""A JSON status API and web page using only the standard library. Run: python3 status_server.py"""

from __future__ import annotations

import json
import math
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


class DeviceState:
    """Shared between the HTTP threads and the acquisition thread, so every access takes the lock."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.started = time.monotonic()
        self.period_ms = 100
        self.samples: list[dict[str, float]] = []

    def acquire_forever(self) -> None:  # stands in for the frametool link
        while True:
            with self.lock:
                t = time.monotonic() - self.started
                self.samples.append({"t": round(t, 3), "temp_c": round(25 + 10 * math.sin(t), 2)})
                del self.samples[:-600]  # keep the last 600
                period = self.period_ms
            time.sleep(period / 1000)


STATE = DeviceState()
PAGE = """<!doctype html><title>TLM-100</title><h1>TLM-100 status</h1>
<p>Latest: <span id=t>...</span> C</p>
<script>setInterval(async () => {
  const s = await (await fetch('/api/status')).json();
  document.getElementById('t').textContent = s.latest.temp_c;
}, 1000)</script>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "TLM100/1.0"
    timeout = 5  # socket timeout in seconds: a client that stalls mid-request loses its thread

    def send_json(self, body: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == "/":
            data = PAGE.encode()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif url.path == "/api/status":
            with STATE.lock:
                if not STATE.samples:  # the acquisition thread has not produced a sample yet
                    self.send_json({"error": "no data yet"}, HTTPStatus.SERVICE_UNAVAILABLE)
                    return
                body = {
                    "uptime_s": round(time.monotonic() - STATE.started, 1),
                    "period_ms": STATE.period_ms,
                    "latest": STATE.samples[-1],
                }
            self.send_json(body)
        elif url.path == "/api/telemetry":
            try:
                last = int(parse_qs(url.query).get("last", ["5"])[0])
            except ValueError:  # an unhandled exception would just drop the connection
                self.send_json({"error": "last must be an integer"}, HTTPStatus.BAD_REQUEST)
                return
            with STATE.lock:
                self.send_json(STATE.samples[-max(1, min(last, 600)) :])  # clamp client input
        else:
            self.send_json({"error": f"no route {url.path}"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/api/rate":
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:  # missing or not a number: an unhandled exception drops the connection
            self.send_json({"error": "Content-Length required"}, HTTPStatus.LENGTH_REQUIRED)
            return
        if not 0 <= length <= 1024:  # never read a negative or unbounded body
            self.send_json({"error": "body too large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        try:
            period = json.loads(self.rfile.read(length))["period_ms"]
            if type(period) is not int or not 10 <= period <= 10_000:  # no floats, strings or bools
                raise ValueError("period_ms must be an integer from 10 to 10000")
        except KeyError:
            self.send_json({"error": "missing field period_ms"}, HTTPStatus.BAD_REQUEST)
            return
        except (ValueError, TypeError) as e:  # bad JSON, wrong type, out of range
            self.send_json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
            return
        with STATE.lock:
            STATE.period_ms = period
        self.send_json({"period_ms": period})

    def log_message(self, format: str, *args: Any) -> None:  # quieter than the default stderr log
        pass


def serve(port: int = 8080) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)  # localhost only: no auth here
    threading.Thread(target=STATE.acquire_forever, daemon=True).start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    srv = serve(8080)
    print("serving on http://127.0.0.1:8080/  (Ctrl+C to stop)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
