"""Call the Flask app through Flask's test client: no server, no port. Run: python3 flask_check.py"""

import time

from flask_app import app

client = app.test_client()
time.sleep(0.4)  # let the acquisition thread store a few samples
for method, path, body in [
    ("GET", "/api/status", None),
    ("GET", "/api/telemetry?last=2", None),
    ("POST", "/api/rate", {"period_ms": 250}),
    ("POST", "/api/rate", {"period_ms": 5}),
    ("POST", "/api/rate", {"period_ms": "50"}),
    ("POST", "/api/rate", {"period_ms": 25.0}),
    ("GET", "/api/telemetry?last=abc", None),
    ("GET", "/openapi.json", None),  # Flask generates no schema
]:
    r = client.open(path, method=method, json=body)
    text = "no schema" if r.status_code == 404 else r.get_data(as_text=True).strip()
    print(f"{method:<5}{path:<26}{r.status_code}  {text[:68]}")
