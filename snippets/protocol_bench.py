"""How fast is each way to decode a binary record? One 9-byte record, and a 252-byte frame.

The record is telemetry_t of the document: u32 timestamp, i16 temperature, u16 supply, u8 status,
little-endian. Every method returns the same 4 integers for the same bytes, and the script checks
that before it times anything. Run: python3 protocol_bench.py   (needs: uv sync)
"""

import ctypes
import struct
import sys
import timeit
from collections.abc import Callable

import construct as c  # type: ignore[import-untyped]  # construct has no type stubs
import numpy as np

RECORDS = 28  # 28 records of 9 bytes: a 252-byte payload
REPEAT = 5  # the best of 5 runs is reported, because noise only ever adds time

Record = tuple[int, int, int, int]


class Wire(ctypes.LittleEndianStructure):
    _pack_ = 1
    _layout_ = "ms"
    _fields_ = [
        ("timestamp_ms", ctypes.c_uint32),
        ("temperature_cdeg", ctypes.c_int16),
        ("supply_mv", ctypes.c_uint16),
        ("status", ctypes.c_uint8),
    ]


STRUCT = struct.Struct("<IhHB")
RECORD = c.Struct(
    "timestamp_ms" / c.Int32ul,
    "temperature_cdeg" / c.Int16sl,
    "supply_mv" / c.Int16ul,
    "status" / c.Int8ul,
)
RECORD_COMPILED = RECORD.compile()
DTYPE = np.dtype([("t", "<u4"), ("temp", "<i2"), ("mv", "<u2"), ("status", "u1")], align=False)
assert STRUCT.size == ctypes.sizeof(Wire) == DTYPE.itemsize == 9


def harness_only(buf: bytes, off: int) -> None:  # the cost of the lambda and the call, no decoding
    return None


def by_struct(buf: bytes, off: int) -> Record:
    return STRUCT.unpack_from(buf, off)


def by_shifts(buf: bytes, off: int) -> Record:  # the C way, indexing single bytes
    t = buf[off] | buf[off + 1] << 8 | buf[off + 2] << 16 | buf[off + 3] << 24
    temp = buf[off + 4] | buf[off + 5] << 8
    if temp & 0x8000:
        temp -= 0x10000
    return t, temp, buf[off + 6] | buf[off + 7] << 8, buf[off + 8]


def by_from_bytes(mv: memoryview, off: int) -> Record:  # slices of a memoryview copy nothing
    return (
        int.from_bytes(mv[off : off + 4], "little"),
        int.from_bytes(mv[off + 4 : off + 6], "little", signed=True),
        int.from_bytes(mv[off + 6 : off + 8], "little"),
        mv[off + 8],
    )


def by_ctypes(buf: bytearray, off: int) -> Record:  # an overlay: no copy, fields read on access
    w = Wire.from_buffer(buf, off)
    return w.timestamp_ms, w.temperature_cdeg, w.supply_mv, w.status


def by_ctypes_once(w: Wire) -> Record:  # the overlay was made once, over a receive buffer
    return w.timestamp_ms, w.temperature_cdeg, w.supply_mv, w.status


def by_construct(buf: bytes, off: int) -> Record:
    r = RECORD.parse(buf[off : off + 9])
    return r.timestamp_ms, r.temperature_cdeg, r.supply_mv, r.status


def by_construct_compiled(buf: bytes, off: int) -> Record:
    r = RECORD_COMPILED.parse(buf[off : off + 9])
    return r.timestamp_ms, r.temperature_cdeg, r.supply_mv, r.status


def make_frame() -> bytes:
    return b"".join(
        STRUCT.pack(1000 * i + 7, 2350 - 97 * i, 3300 - i, i % 7) for i in range(RECORDS)
    )


# ---- whole-frame decoders: all 28 records, as a list of 4-tuples ----------------------------
def frame_loop_unpack_from(buf: bytes) -> list[Record]:
    return [STRUCT.unpack_from(buf, 9 * i) for i in range(RECORDS)]


def frame_iter_unpack(buf: bytes) -> list[Record]:
    return list(STRUCT.iter_unpack(buf))


def frame_ctypes_array(buf: bytearray) -> list[Record]:
    arr = (Wire * RECORDS).from_buffer(buf)
    return [(w.timestamp_ms, w.temperature_cdeg, w.supply_mv, w.status) for w in arr]


def frame_construct(buf: bytes) -> list[Record]:
    return [
        (r.timestamp_ms, r.temperature_cdeg, r.supply_mv, r.status)
        for r in c.Array(RECORDS, RECORD).parse(buf)
    ]


FRAME_COMPILED = c.Array(RECORDS, RECORD).compile()


def frame_construct_compiled(buf: bytes) -> list[Record]:
    return [
        (r.timestamp_ms, r.temperature_cdeg, r.supply_mv, r.status)
        for r in FRAME_COMPILED.parse(buf)
    ]


def frame_numpy(buf: bytes) -> list[Record]:
    a = np.frombuffer(buf, dtype=DTYPE)  # a view of the bytes, nothing is decoded yet
    return list(
        zip(
            a["t"].tolist(), a["temp"].tolist(), a["mv"].tolist(), a["status"].tolist(), strict=True
        )
    )


def frame_iter_unpack_max(buf: bytes) -> int:  # the same answer as frame_numpy_view
    return int(max(r[1] for r in STRUCT.iter_unpack(buf)))


def frame_numpy_view(buf: bytes) -> int:
    a = np.frombuffer(buf, dtype=DTYPE)
    return int(a["temp"].max())  # the case where NumPy fits: one reduction, no Python objects


def best_ns(fn: Callable[[], object], number: int) -> float:
    return min(timeit.repeat(fn, number=number, repeat=REPEAT)) / number * 1e9


def main() -> None:
    frame = make_frame()
    frame_ba = bytearray(frame)
    mv = memoryview(frame)
    expected = list(STRUCT.iter_unpack(frame))

    # Every decoder must agree with struct before any number is believed
    for off in (0, 9, 9 * (RECORDS - 1)):
        want = STRUCT.unpack_from(frame, off)
        for dec in (by_struct, by_shifts, by_construct, by_construct_compiled):
            assert dec(frame, off) == want, (dec.__name__, off)
        assert by_from_bytes(mv, off) == want and by_ctypes(frame_ba, off) == want
    for fdec in (
        frame_loop_unpack_from,
        frame_iter_unpack,
        frame_construct,
        frame_construct_compiled,
        frame_numpy,
    ):
        assert fdec(frame) == expected, fdec.__name__
    assert frame_ctypes_array(frame_ba) == expected
    assert frame_numpy_view(frame) == frame_iter_unpack_max(frame) == max(r[1] for r in expected)
    print(f"python {sys.version.split()[0]}, numpy {np.__version__}, construct {c.version_string}")
    print("all decoders agree with struct on the test data\n")

    overlay = Wire.from_buffer(frame_ba, 18)
    assert by_ctypes_once(overlay) == STRUCT.unpack_from(frame, 18)
    n = 100_000
    print("one 9-byte record, ns per record (best of 5)")
    single: list[tuple[str, float]] = [
        ("struct.Struct.unpack_from", best_ns(lambda: by_struct(frame, 18), n)),
        ("shifts on bytes, as in C", best_ns(lambda: by_shifts(frame, 18), n)),
        ("memoryview + int.from_bytes", best_ns(lambda: by_from_bytes(mv, 18), n)),
        ("ctypes overlay, from_buffer", best_ns(lambda: by_ctypes(frame_ba, 18), n)),
        ("ctypes overlay made once", best_ns(lambda: by_ctypes_once(overlay), n)),
        ("construct", best_ns(lambda: by_construct(frame, 18), n // 10)),
        ("construct, compiled", best_ns(lambda: by_construct_compiled(frame, 18), n // 10)),
    ]
    base = single[0][1]
    for name, ns in single:
        print(f"  {name:30s}{ns:9.0f} ns{ns / base:8.1f}x")
    # Every row above goes through a lambda and a function call. These two rows show what that
    # costs, so that the ratios can be read with it in mind.
    print("the timing harness itself, in ns")
    for name, ns in [
        ("empty function in a lambda", best_ns(lambda: harness_only(frame, 18), n)),
        ("unpack_from in a lambda", best_ns(lambda: STRUCT.unpack_from(frame, 18), n)),
    ]:
        print(f"  {name:30s}{ns:9.0f} ns")

    print(f"\none frame of {RECORDS} records ({len(frame)} bytes), us per frame (best of 5)")
    m = 5_000
    whole: list[tuple[str, float]] = [
        ("struct.iter_unpack", best_ns(lambda: frame_iter_unpack(frame), m)),
        ("loop of unpack_from", best_ns(lambda: frame_loop_unpack_from(frame), m)),
        ("ctypes array overlay", best_ns(lambda: frame_ctypes_array(frame_ba), m)),
        ("numpy.frombuffer + tolist", best_ns(lambda: frame_numpy(frame), m)),
        ("construct Array", best_ns(lambda: frame_construct(frame), m // 10)),
        ("construct Array, compiled", best_ns(lambda: frame_construct_compiled(frame), m // 10)),
        ("numpy view, max of one field", best_ns(lambda: frame_numpy_view(frame), m)),
        ("iter_unpack, max of one field", best_ns(lambda: frame_iter_unpack_max(frame), m)),
    ]
    base = whole[0][1]
    for name, ns in whole:
        print(f"  {name:30s}{ns / 1000:9.1f} us{ns / base:8.1f}x")


if __name__ == "__main__":
    main()
