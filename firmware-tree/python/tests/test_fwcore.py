"""The Python module and a pure-Python reference must agree. The limits come from the firmware."""

import binascii
import random

import fwcore
import pytest


def cobs_reference(src: bytes) -> bytes:
    out = bytearray(b"\x00")
    code_index, code = 0, 1
    for b in src:
        if b == 0:
            out[code_index] = code
            code_index, code = len(out), 1
            out.append(0)
            continue
        out.append(b)
        code += 1
        if code == 0xFF:
            out[code_index] = code
            code_index, code = len(out), 1
            out.append(0)
    out[code_index] = code
    return bytes(out)


def test_crc16_check_value() -> None:
    assert fwcore.crc16(b"123456789") == 0x29B1


def test_crc16_matches_binascii() -> None:
    rng = random.Random(1)
    for n in (0, 1, 9, 100, fwcore.MAX_FRAME):
        data = rng.randbytes(n)
        assert fwcore.crc16(data) == binascii.crc_hqx(data, 0xFFFF)


def test_cobs_matches_reference_and_round_trips() -> None:
    rng = random.Random(2)
    cases = [b"", b"\x00", b"\x00\x00", bytes(range(1, 255)), b"\xff" * 254, b"\xff" * 255]
    cases += [rng.randbytes(rng.randrange(0, fwcore.MAX_FRAME + 1)) for _ in range(200)]
    for data in cases:
        enc = fwcore.cobs_encode(data)
        assert enc == cobs_reference(data)
        assert b"\x00" not in enc
        assert fwcore.cobs_decode(enc) == data


def test_accepts_any_buffer() -> None:
    data = bytes([1, 0, 2])
    assert fwcore.cobs_encode(bytearray(data)) == fwcore.cobs_encode(memoryview(data))


def test_bad_cobs_data() -> None:
    with pytest.raises(ValueError, match="invalid COBS"):
        fwcore.cobs_decode(b"\x05\x01")  # the code byte promises more bytes than there are
    with pytest.raises(ValueError, match="invalid COBS"):
        fwcore.cobs_decode(b"\x00")


def test_firmware_frame_limit_is_visible_in_python() -> None:
    assert fwcore.MAX_FRAME == 256
    fwcore.crc16(bytes(fwcore.MAX_FRAME))
    with pytest.raises(
        ValueError, match="257 bytes is longer than the limit of 256 for FW_MAX_FRAME"
    ):
        fwcore.crc16(bytes(fwcore.MAX_FRAME + 1))
    with pytest.raises(ValueError, match="FW_MAX_FRAME"):
        fwcore.cobs_encode(bytes(fwcore.MAX_FRAME + 1))
    # a full frame still encodes, and the encoded form (a little longer) still decodes
    full = bytes(range(1, 256)) + b"\x01"
    assert len(full) == fwcore.MAX_FRAME
    assert fwcore.cobs_decode(fwcore.cobs_encode(full)) == full


def test_str_is_rejected() -> None:
    with pytest.raises(TypeError):
        fwcore.crc16("abc")  # type: ignore[arg-type]
