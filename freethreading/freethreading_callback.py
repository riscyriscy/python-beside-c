"""A C update that calls back into Python is not one step, even with the GIL.

Run (build as for freethreading_demo.py; the module is _counter):
    python3.14 freethreading_callback.py
    python3.14t freethreading_callback.py
"""

import sys
import threading

import _counter  # type: ignore[import-not-found]  # the extension built by CMakeLists.txt

THREADS = 4
PER_THREAD = 1_000_000


def tick() -> None:
    """The Python function that the C code calls between reading and storing the counter."""


def main() -> None:
    _counter.reset()
    threads = [
        threading.Thread(target=_counter.bump_callback, args=(PER_THREAD, tick))
        for _ in range(THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    got = _counter.values()[3]
    expected = THREADS * PER_THREAD
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    print(f"Python {sys.version.split()[0]}, GIL enabled: {gil}")
    print(f"  callback  {got:,} of {expected:,}  lost {expected - got:,}")


main()
