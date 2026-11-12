"""Run the FastAPI app under uvicorn and call it with httpx. Run: python3 fastapi_check.py"""

import subprocess
import sys
import time

import httpx

server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "fastapi_app:app", "--host", "127.0.0.1", "--port", "8765"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
try:
    with httpx.Client(base_url="http://127.0.0.1:8765", timeout=2) as client:
        for _ in range(50):  # wait for start-up
            try:
                client.get("/api/status")
                break
            except httpx.TransportError:
                time.sleep(0.1)
        time.sleep(0.3)
        for method, path, body in [
            ("GET", "/api/status", None),
            ("GET", "/api/telemetry?last=2", None),
            ("POST", "/api/rate", {"period_ms": 250}),
            ("POST", "/api/rate", {"period_ms": 5}),
            ("POST", "/api/rate", {"period_ms": "50"}),  # the stdlib server also says no
            ("POST", "/api/rate", {"period_ms": 25.0}),
            ("GET", "/api/telemetry?last=abc", None),
            ("GET", "/openapi.json", None),
        ]:
            r = client.request(method, path, json=body)
            text = r.text if path != "/openapi.json" else f"OpenAPI {r.json()['openapi']} schema"
            print(f"{method:<5}{path:<26}{r.status_code}  {text[:68]}")
finally:
    server.terminate()
    server.wait()
