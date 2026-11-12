"""Garbage-collector pauses in a timing-sensitive host tool, and what to do about them.

CPython frees most objects at once by reference counting. The cyclic garbage collector (GC)
runs on top of that to find reference cycles, and a full collection must visit every tracked
object. With a large live data set that is a pause of milliseconds, at a moment you do not choose.
Run: python3 gc_pause.py
"""

import gc
import time
from collections.abc import Callable


class Node:
    """A sample record. Instances are GC-tracked, as every object with attributes is."""

    def __init__(self, i: int) -> None:
        self.i = i
        self.me = self  # a reference cycle: reference counting alone can never free it


def pauses_during(work: Callable[[], object]) -> list[tuple[int, float]]:
    """Return (generation, duration in ms) of every collection that happens while work() runs."""
    pauses: list[tuple[int, float]] = []
    start = 0.0

    def callback(phase: str, info: dict[str, int]) -> None:
        nonlocal start
        if phase == "start":
            start = time.perf_counter()
        else:
            pauses.append((info["generation"], (time.perf_counter() - start) * 1e3))

    gc.callbacks.append(callback)
    try:
        work()
    finally:
        gc.callbacks.remove(callback)
    return pauses


def load_records(n: int) -> list[Node]:
    """Build a large data set, as loading a capture or a parsed log does."""
    return [Node(i) for i in range(n)]


def full(pauses: list[tuple[int, float]]) -> list[float]:
    return [ms for generation, ms in pauses if generation == 2]


def main() -> None:
    print(
        "thresholds for generations 1 and 2:", gc.get_threshold()[1:], "| enabled:", gc.isenabled()
    )

    # 1. Loading 1.5 M records with default settings: the live set grows, so the collector
    #    runs full collections, and each one visits everything loaded so far
    default = pauses_during(lambda: load_records(1_500_000))
    gc.collect()
    print("default load ran full collections:", len(full(default)) >= 1)
    print("the longest pause was over 5 ms:", max(ms for _, ms in default) > 5)

    # 2. The same load with the collector switched off, then one collection at a safe moment
    gc.disable()
    off = pauses_during(lambda: load_records(1_500_000))
    gc.enable()
    print("load with gc.disable() ran no collection:", off == [])

    # 3. A big live set already exists. A forced full collection is the pause you cannot afford
    live = load_records(1_000_000)
    forced = full(pauses_during(gc.collect))

    # 4. gc.freeze() moves every existing object into a permanent generation that the
    #    collector no longer visits. Do it once, after start-up
    gc.freeze()
    frozen = full(pauses_during(gc.collect))
    print("objects frozen:", gc.get_freeze_count() >= len(live))
    gc.unfreeze()
    print("full collection with 1 M live objects took over 5 ms:", max(forced) > 5)
    print("after gc.freeze() it was at least 10 times shorter:", max(frozen) * 10 < max(forced))


if __name__ == "__main__":
    main()
