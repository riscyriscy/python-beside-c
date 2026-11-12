"""A C function with a static buffer, called from four Python threads, against one without.

ctypes releases the GIL during every call, so the threads really do overlap in C.
Run:   python thread_safety.py        (build: cc -shared -fPIC -o libfw_describe.so fw_describe.c)
"""

import ctypes
import sys
import sysconfig
import threading
from collections.abc import Callable
from pathlib import Path

lib = ctypes.CDLL(str(Path(__file__).with_name("libfw_describe.so")))
lib.fw_describe_static.argtypes = [ctypes.c_uint, ctypes.c_uint]
lib.fw_describe_static.restype = ctypes.c_char_p
lib.fw_describe.argtypes = [
    ctypes.c_char_p,
    ctypes.c_size_t,
    ctypes.c_uint,
    ctypes.c_uint,
]
lib.fw_describe.restype = ctypes.c_int

THREADS = 4
CALLS = 50_000
lock = threading.Lock()


def shared_buffer(uid: int, mv: int) -> bytes:
    return lib.fw_describe_static(uid, mv)  # type: ignore[no-any-return]


def locked_shared_buffer(uid: int, mv: int) -> bytes:
    with lock:  # the fix when the C library cannot be changed
        return lib.fw_describe_static(uid, mv)  # type: ignore[no-any-return]


def caller_buffer(uid: int, mv: int) -> bytes:
    out = ctypes.create_string_buffer(48)  # one buffer per call, owned by this thread
    lib.fw_describe(out, len(out), uid, mv)
    return out.value


def run(fn: Callable[[int, int], bytes], label: str) -> None:
    wrong = [0] * THREADS

    def work(t: int) -> None:
        uid, mv = 10 + t, 3300 + t
        want = f"unit {uid} reads {mv} mV".encode()
        wrong[t] = sum(fn(uid, mv) != want for _ in range(CALLS))

    threads = [threading.Thread(target=work, args=(t,)) for t in range(THREADS)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    print(f"{label:34} wrong results: {sum(wrong):6d} of {THREADS * CALLS}")


gil = getattr(sys, "_is_gil_enabled", lambda: True)()
print(f"python {sysconfig.get_python_version()}, GIL enabled: {gil}")
run(shared_buffer, "static buffer in the C library")
run(locked_shared_buffer, "static buffer, call under a lock")
run(caller_buffer, "buffer from the caller")
