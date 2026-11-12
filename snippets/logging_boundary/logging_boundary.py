"""Logging across the Python and C boundary: stdio ordering, a log callback, and a callback that raises.

Build: cc -shared -fPIC -o libfw_log.so fw_log.c -lpthread
Run:   python logging_boundary.py            (the ordering part starts child processes with a pipe on stdout)
"""

import ctypes
import logging
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG_FN = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p)


def load() -> ctypes.CDLL:
    lib = ctypes.CDLL(str(HERE / "libfw_log.so"))
    lib.fw_log_set.argtypes = [LOG_FN]
    lib.fw_log_set.restype = None
    lib.fw_printf_line.argtypes = [ctypes.c_int]
    return lib


def child(mode: str) -> None:
    """Prints Python and C lines alternately. mode: plain or flush."""
    lib = load()
    for n in (1, 2):
        print(f"Python line {n}")
        if mode == "flush":
            sys.stdout.flush()  # empty Python's buffer before C writes
        lib.fw_printf_line(n)
        if mode == "flush":
            lib.fw_printf_flush()  # empty the C library's buffer before Python writes


def ordering() -> None:
    py = sys.executable
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
    cases: list[tuple[str, list[str]]] = [
        ("plain", [py, __file__, "child", "plain"]),
        ("python -u", [py, "-u", __file__, "child", "plain"]),
        ("flush in the code", [py, __file__, "child", "flush"]),
        ("stdbuf -oL", ["stdbuf", "-oL", py, __file__, "child", "plain"]),
    ]
    for label, cmd in cases:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env).stdout
        print(f"{label:18} {' | '.join(out.splitlines())}")


def callback_demo() -> None:
    logging.basicConfig(
        format="%(levelname)-7s %(name)s [%(threadName)s] %(message)s",
        level=logging.DEBUG,
        stream=sys.stdout,
    )
    log = logging.getLogger("fw")
    lib = load()

    def handle(level: int, msg: bytes) -> None:
        try:
            log.log(level, msg.decode("ascii", "replace"))
        except Exception:  # an exception cannot cross back into C
            logging.getLogger("fw").exception("log callback failed")

    on_log = LOG_FN(handle)  # keep this name alive for as long as C may call it
    lib.fw_log_set(on_log)
    lib.fw_selftest()
    lib.fw_selftest_thread()

    def handle_bad(level: int, msg: bytes) -> None:
        raise ValueError("handler bug")

    on_log_bad = LOG_FN(handle_bad)
    lib.fw_log_set(on_log_bad)
    print("--- a callback that raises ---")
    sys.stdout.flush()
    lib.fw_selftest_thread()
    print("selftest returned; the run goes on")
    lib.fw_log_set(LOG_FN(0))  # remove the callback before the Python object goes away


if __name__ == "__main__":
    if sys.argv[1:2] == ["child"]:
        child(sys.argv[2])
    else:
        ordering()
        callback_demo()
