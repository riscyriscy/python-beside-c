"""The same API with Flask: a WSGI app, a thread for acquisition, validation by hand.

Run: waitress-serve --listen=127.0.0.1:8000 flask_app:app
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque

from flask import Flask, Response, jsonify, request
from flask.typing import ResponseReturnValue

app = Flask(__name__)
app.json.sort_keys = False  # type: ignore[attr-defined]  # keep the FastAPI field order

started = time.monotonic()
lock = threading.Lock()  # request threads and the acquisition thread share the state
period_ms = 100
samples: deque[dict[str, float]] = deque(maxlen=600)


def acquire() -> None:  # a plain thread: Flask has no event loop to host a task
    while True:
        t = time.monotonic() - started
        with lock:
            samples.append({"t": round(t, 3), "temp_c": round(25 + 10 * math.sin(t), 2)})
            wait = period_ms / 1000
        time.sleep(wait)


threading.Thread(target=acquire, daemon=True).start()


def bad_request(message: str) -> tuple[Response, int]:
    return jsonify(error=message), 400  # the format is ours: nothing describes it for the client


@app.get("/api/status")
def status() -> ResponseReturnValue:
    with lock:
        if not samples:
            return jsonify(error="no data yet"), 503
        return jsonify(
            uptime_s=round(time.monotonic() - started, 1), period_ms=period_ms, latest=samples[-1]
        )


@app.get("/api/telemetry")
def telemetry() -> ResponseReturnValue:
    try:
        last = int(request.args.get("last", "5"))  # a query string is always text
    except ValueError:
        return bad_request("last must be an integer")
    if not 1 <= last <= 600:
        return bad_request("last must be between 1 and 600")
    with lock:
        return jsonify(list(samples)[-last:])


@app.post("/api/rate")
def set_rate() -> ResponseReturnValue:
    global period_ms
    body = request.get_json(silent=True)  # None for a missing or malformed body
    value = body.get("period_ms") if isinstance(body, dict) else None
    if type(value) is not int:  # strict: a string, a float or a bool is refused, as in FastAPI
        return bad_request("period_ms must be an integer")
    if not 10 <= value <= 10_000:
        return bad_request("period_ms must be between 10 and 10000")
    with lock:
        period_ms = value
    return jsonify(period_ms=value)
