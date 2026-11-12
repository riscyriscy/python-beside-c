import binascii

from frametool import cobs as py_cobs
from hypothesis import given, settings
from hypothesis import strategies as st

import fw


@given(st.binary(max_size=600))
@settings(max_examples=300, deadline=None)
def test_cobs_c_matches_python_and_round_trips(data: bytes) -> None:
    encoded = fw.cobs_encode(data)
    assert encoded == py_cobs.encode(data)  # differential: firmware C against frametool
    assert b"\x00" not in encoded
    assert fw.cobs_decode(encoded) == data


@given(st.binary(max_size=64))
@settings(max_examples=300, deadline=None)
def test_cobs_decode_never_overruns_on_noise(noise: bytes) -> None:
    result = fw.cobs_decode(noise)  # random bytes: either an error or some bytes, never a crash
    assert result is None or len(result) <= len(noise)


@given(st.binary(max_size=300))
def test_crc_matches_the_standard_library(data: bytes) -> None:
    assert fw.lib.crc16_ccitt(data, len(data)) == binascii.crc_hqx(data, 0xFFFF)


def test_sensor_with_a_mock_adc() -> None:
    assert fw.millivolts({0: 4095, 1: 2048}, 0, 256) == 3300
    assert fw.millivolts({0: 4095, 1: 2048}, 1, 256) == 1650


def test_sensor_with_a_large_gain() -> None:
    # 4095 counts at a gain of 4096.0 (Q8 value 1048576): the product does not fit in 32 bits
    assert fw.millivolts({0: 4095}, 0, 4096 * 256) == 3300 * 4096


@given(st.lists(st.integers(1, 255), min_size=250, max_size=600).map(bytes))
@settings(max_examples=100, deadline=None)
def test_cobs_runs_of_254_or_more_non_zero_bytes(data: bytes) -> None:
    encoded = fw.cobs_encode(data)  # a code byte of 0xFF closes a block with no implied zero after it
    assert encoded == py_cobs.encode(data)
    assert fw.cobs_decode(encoded) == data
