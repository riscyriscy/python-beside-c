import array
import binascii
import gc
from typing import Any

import numpy as np
import pytest

import telemetry_log as tl

WIRE = bytes.fromhex("40e201002efbe50c02")


def test_decode_matches_the_ctypes_example() -> None:
    rec = tl.decode_record(WIRE)
    assert (rec.timestamp_ms, rec.temperature_cdeg, rec.supply_mv, rec.status) == (
        123456,
        -1234,
        3301,
        2,
    )


@pytest.mark.parametrize("data", [WIRE, bytearray(WIRE), memoryview(WIRE)])
def test_decode_accepts_any_bytes_like_object(data: bytes | bytearray | memoryview) -> None:
    assert tl.decode_record(data).supply_mv == 3301


def test_uint8_arrays_are_accepted() -> None:
    assert tl.decode_record(np.frombuffer(WIRE, np.uint8)).supply_mv == 3301
    assert tl.decode_record(array.array("B", WIRE)).supply_mv == 3301


@pytest.mark.parametrize(
    "wrong",
    [
        np.arange(9, dtype=np.int16),  # nine values of the wrong width
        np.arange(9, dtype=np.float64),
        np.frombuffer(WIRE * 2, np.uint8)[::2],  # nine bytes, but strided
        array.array("H", range(9)),
        memoryview(WIRE * 2)[::2],
    ],
    ids=["int16", "float64", "strided", "array-H", "strided-memoryview"],
)
def test_other_dtypes_and_strides_are_rejected_not_converted(
    wrong: Any,
) -> None:  # Any: the call is wrong on purpose
    with pytest.raises(TypeError):
        tl.decode_record(wrong)


@pytest.mark.parametrize("bad", [b"", WIRE[:8], WIRE + b"\x00", WIRE[:8] + b"\xf2"])
def test_frame_error_is_a_value_error(bad: bytes) -> None:
    with pytest.raises(tl.FrameError):
        tl.decode_record(bad)
    with pytest.raises(ValueError):
        tl.decode_record(bad)


def test_standard_exceptions_are_translated() -> None:
    log = tl.RecordLog(1)
    log.add(tl.decode_record(WIRE))
    with pytest.raises(ValueError, match="full"):
        log.add(tl.decode_record(WIRE))
    with pytest.raises(IndexError):
        log.at(1)


def test_crc_matches_binascii() -> None:
    log = tl.RecordLog(3)
    for _ in range(3):
        log.add(tl.decode_record(WIRE))
    assert log.crc == binascii.crc_hqx(WIRE * 3, 0xFFFF)


def test_a_reference_into_the_log_keeps_it_alive() -> None:
    before = tl.live_logs()
    log = tl.make_log(2)
    log.add(tl.decode_record(WIRE))
    first = log.at(0)
    del log
    gc.collect()
    assert tl.live_logs() == before + 1
    assert first.supply_mv == 3301
    del first
    gc.collect()
    assert tl.live_logs() == before


def test_a_shared_ptr_keeps_the_log_alive_in_cpp() -> None:
    before = tl.live_logs()
    shared = tl.RecordLog(2)
    recorder = tl.Recorder(shared)
    del shared
    gc.collect()
    assert tl.live_logs() == before + 1
    recorder.record(tl.decode_record(WIRE))
    assert len(recorder.log) == 1
    del recorder
    gc.collect()
    assert tl.live_logs() == before
