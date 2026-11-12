"""The nanobind package telemetry_log: calls, exceptions and who owns what.

Run: uv run python telemetry_log_demo.py   (after uv sync builds the extension)
"""

import binascii
import gc
from collections.abc import Callable

import numpy as np

import telemetry_log as tl

WIRE = bytes.fromhex("40e201002efbe50c02")  # the 9-byte record of the ctypes example

print("1. Calls: any bytes-like object, one C++ decoder")
rec = tl.decode_record(WIRE)
print(" ", rec)
print(
    " ",
    tl.decode_record(bytearray(WIRE)).supply_mv,
    "mV from a bytearray,",
    tl.decode_record(memoryview(WIRE)).supply_mv,
    "mV from a memoryview",
)
try:
    tl.decode_record(np.arange(9, dtype=np.int16))  # nine values, but not uint8
except TypeError:
    print("  an int16 array of nine values: TypeError, not a converted Record")


def overfill() -> None:
    small = tl.make_log(1)
    small.add(rec)
    small.add(rec)  # one slot too many


print("2. C++ exceptions become Python exceptions")
cases: list[tuple[str, Callable[[], object]]] = [
    ("FrameError", lambda: tl.decode_record(WIRE[:5])),
    ("std::length_error", overfill),
    ("std::out_of_range", lambda: tl.make_log(1).at(3)),
]
for label, call in cases:
    try:
        call()
    except (ValueError, IndexError) as exc:
        names = " <- ".join(c.__name__ for c in type(exc).__mro__[:2])
        print(f"  {label:18s}{names}: {exc}")

print("3. unique_ptr: Python owns the log, and a reference into it keeps it alive")
log = tl.make_log(4)
log.add(rec)
first = log.at(0)  # a reference into the C++ vector, not a copy
print("  C++ logs alive:", tl.live_logs())
del log
gc.collect()
print("  after del log, first still holds one:", tl.live_logs(), "alive;", first.supply_mv, "mV")
del first
gc.collect()
print("  after del first:", tl.live_logs(), "alive")

print("4. shared_ptr: the C++ Recorder and Python share one log")
shared = tl.RecordLog(4)
recorder = tl.Recorder(shared)
recorder.record(rec)
print("  same object:", recorder.log is shared, "| records seen from Python:", len(shared))
del shared
gc.collect()
print(
    "  after del shared, the Recorder keeps it:",
    tl.live_logs(),
    "alive,",
    len(recorder.log),
    "record",
)
del recorder
gc.collect()
print("  after del recorder:", tl.live_logs(), "alive")

print("5. The C++ CRC against Python's binascii")
log = tl.RecordLog(2)
log.add(rec)
log.add(rec)
print(f"  C++ {log.crc:#06x}, binascii.crc_hqx {binascii.crc_hqx(WIRE * 2, 0xFFFF):#06x}")
