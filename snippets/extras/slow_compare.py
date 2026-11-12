"""Send 20 concurrent requests to each server and time them. Run: python3 slow_compare.py"""

import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

CASES = [
    (
        "Flask, waitress, 4 threads (default)",
        ["-m", "waitress", "--listen=127.0.0.1:8001", "slow_flask:app"],
        8001,
        "/slow",
    ),
    (
        "Flask, waitress, 20 threads",
        ["-m", "waitress", "--threads=20", "--listen=127.0.0.1:8001", "slow_flask:app"],
        8001,
        "/slow",
    ),
    (
        "FastAPI, async def handler",
        ["-m", "uvicorn", "slow_fastapi:app", "--port", "8002"],
        8002,
        "/slow_async",
    ),
    (
        "FastAPI, def handler",
        ["-m", "uvicorn", "slow_fastapi:app", "--port", "8002"],
        8002,
        "/slow_def",
    ),
]


def burst(port: int, path: str, n: int = 20) -> float:
    url = f"http://127.0.0.1:{port}{path}"
    with httpx.Client(limits=httpx.Limits(max_connections=n)) as client:
        start = time.perf_counter()
        with ThreadPoolExecutor(n) as pool:
            codes = list(pool.map(lambda _: client.get(url, timeout=30).status_code, range(n)))
        elapsed = time.perf_counter() - start
    assert codes == [200] * n
    return elapsed


for name, args, port, path in CASES:
    server = subprocess.Popen(
        [sys.executable, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        for _ in range(100):  # wait for start-up
            try:
                httpx.get(f"http://127.0.0.1:{port}{path}", timeout=5)
                break
            except httpx.TransportError:
                time.sleep(0.1)
        times = [burst(port, path) for _ in range(5)]
        print(
            f"{name:<40}median {statistics.median(times):5.2f} s   min {min(times):5.2f} s   max {max(times):5.2f} s"
        )
    finally:
        server.terminate()
        server.wait()
