"""Which Python views of a receive buffer copy the data, and which share it?

A copy is easy to see by changing the buffer and then looking at the object that was made from it.
Run:   python zero_copy.py        (needs numpy)
"""

import ctypes
import socket
import struct
import timeit
from typing import Any

import numpy as np

print("1. after buf[0] changes, does the object see the new byte?")
buf = bytearray(range(64))
objects: dict[str, Any] = {
    "bytearray slice buf[0:16]": buf[0:16],
    "bytes(buf[0:16])": bytes(buf[0:16]),
    "memoryview(buf)[0:16]": memoryview(buf)[0:16],
    "ctypes (c_uint8 * 16).from_buffer": (ctypes.c_uint8 * 16).from_buffer(buf),
    "ctypes (c_uint8 * 16).from_buffer_copy": (ctypes.c_uint8 * 16).from_buffer_copy(
        buf
    ),
    "numpy.frombuffer(buf, uint8)": np.frombuffer(buf, dtype=np.uint8),
    "numpy.array(buf, uint8)": np.array(buf, dtype=np.uint8),
}
buf[0] = 0xFF
for name, obj in objects.items():
    seen = obj[0] == 0xFF
    print(f"   {name:40} {'shares the memory' if seen else 'is a copy'}")

print("2. read-only sources")
frozen = bytes(64)
try:
    ctypes.c_uint8.from_buffer(frozen)
except TypeError as exc:
    print(f"   ctypes from_buffer(bytes): TypeError, {exc}")
print(
    f"   numpy.frombuffer(bytes).flags.writeable: {np.frombuffer(frozen, np.uint8).flags.writeable}"
)
print(
    f"   numpy.frombuffer(bytearray).flags.writeable: {np.frombuffer(buf, np.uint8).flags.writeable}"
)

print("3. a live view stops the buffer from being resized")
data = bytearray(8)
view = memoryview(data)
try:
    data.extend(b"\x00")
except BufferError as exc:
    print(f"   extend with a view alive: BufferError, {exc}")
view.release()
data.extend(b"\x00")
print(f"   extend after release(): ok, length {len(data)}")

print("4. read into a buffer that you own")
a, b = socket.socketpair()
a.send(bytes(range(1, 10)))
rx = bytearray(64)
n = b.recv_into(memoryview(rx)[16:])
print(f"   recv_into put {n} bytes at offset 16: {bytes(rx[16 : 16 + n]).hex(' ')}")
a.close()
b.close()

print("5. cost on a 1 MiB receive buffer, us per call (best of 5)")
big = bytearray(1 << 20)
off = 500_000
fmt = struct.Struct("<IhHB")


def best(stmt: str) -> float:
    runs = timeit.repeat(stmt, globals={**globals(), "big": big}, number=200, repeat=5)
    return min(runs) / 200 * 1e6


rows = {
    "big[off:] (copies 548,576 bytes)": "big[off:]",
    "struct.unpack(big[off:off + 9])": "fmt.unpack(big[off:off + 9])",
    "struct.unpack_from(big, off)": "fmt.unpack_from(big, off)",
    "bytes(big) (copies 1 MiB)": "bytes(big)",
    "memoryview(big)[off:]": "memoryview(big)[off:]",
}
for label, stmt in rows.items():
    print(f"   {label:36} {best(stmt):9.2f} us")
