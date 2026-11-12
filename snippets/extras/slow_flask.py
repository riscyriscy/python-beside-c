"""A route that blocks in a C call for 200 ms, under Flask. Run: waitress-serve --listen=127.0.0.1:8001 slow_flask:app"""

import ctypes

from flask import Flask

libc = ctypes.CDLL(None)  # the C library of the process (Linux); ctypes drops the GIL during a call
app = Flask(__name__)


@app.get("/slow")
def slow() -> dict[str, bool]:
    libc.usleep(200_000)  # stands in for a firmware call that waits on hardware
    return {"ok": True}
