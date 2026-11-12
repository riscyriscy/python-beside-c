"""Shared state in a C extension, with and without the GIL.

Run (the extension must be built for the interpreter that runs it, see CMakeLists.txt):
    python3.14 freethreading_demo.py _counter         normal build
    python3.14t freethreading_demo.py _counter        free-threaded build
    python3.14t freethreading_demo.py _counter_gil    a module that does not declare support
"""

import importlib
import sys
import textwrap
import threading
import time
import warnings
from collections.abc import Callable

THREADS = 4
PER_THREAD = 1_000_000


def timed_run(bump: Callable[[int], None]) -> float:
    """Start THREADS threads that each call bump(PER_THREAD). Return the time taken in ms."""
    threads = [threading.Thread(target=bump, args=(PER_THREAD,)) for _ in range(THREADS)]
    start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return (time.perf_counter() - start) * 1000


def main() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        mod = importlib.import_module(sys.argv[1])
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    print(f"Python {sys.version.split()[0]}, module {sys.argv[1]}, GIL enabled after import: {gil}")
    for w in caught:
        text = f"{w.category.__name__}: {str(w.message).split('. ')[0]}."
        print(textwrap.fill(text, width=95, initial_indent="  ", subsequent_indent="    "))
    expected = THREADS * PER_THREAD
    for label, bump, index in [
        ("plain ++", mod.bump_plain, 0),
        ("atomic", mod.bump_atomic, 1),
        ("PyMutex", mod.bump_locked, 2),
    ]:
        mod.reset()
        ms = timed_run(bump)
        got = mod.values()[index]
        status = "exact" if got == expected else f"lost {expected - got:,}"
        print(f"  {label:9s}{got:>10,} of {expected:,}  {status:>14s}  {ms:6.1f} ms")


main()
