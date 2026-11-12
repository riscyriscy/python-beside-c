"""cffi binding of the firmware library, loaded from the file named by FW_LIB (ABI mode)."""

import os
from pathlib import Path
from typing import Any

from cffi import FFI

ffi = FFI()
ffi.cdef("""
    typedef struct { uint16_t (*read_adc)(void *ctx, uint8_t channel); void *ctx; } sensor_hw_t;
    size_t cobs_encode(const uint8_t *in, size_t len, uint8_t *out);
    size_t cobs_decode(const uint8_t *in, size_t len, uint8_t *out);
    uint16_t crc16_ccitt(const uint8_t *data, size_t len);
    int32_t sensor_millivolts(const sensor_hw_t *hw, uint8_t channel, int32_t gain_q8);
""")
LIB_PATH = os.environ.get("FW_LIB", str(Path(__file__).parent / "build" / "libfw_plain.so"))
lib: Any = ffi.dlopen(LIB_PATH)  # run build_host.sh first
COBS_ERROR = 2**64 - 1


def cobs_encode(data: bytes) -> bytes:
    out = ffi.new("uint8_t[]", len(data) + len(data) // 254 + 1)  # COBS_MAX_ENCODED(len)
    n = lib.cobs_encode(data, len(data), out)
    return bytes(ffi.buffer(out, n))


def cobs_decode(data: bytes) -> bytes | None:
    out = ffi.new("uint8_t[]", max(len(data), 1))
    n = lib.cobs_decode(data, len(data), out)
    return None if n == COBS_ERROR else bytes(ffi.buffer(out, n))


def millivolts(adc_values: dict[int, int], channel: int, gain_q8: int) -> int:
    """Run sensor_millivolts() with a Python function standing in for the ADC."""

    @ffi.callback("uint16_t(void *, uint8_t)")  # type: ignore[untyped-decorator]
    def read_adc(ctx: Any, ch: int) -> int:
        return adc_values[ch]

    hw = ffi.new("sensor_hw_t *", {"read_adc": read_adc, "ctx": ffi.NULL})
    return int(lib.sensor_millivolts(hw, channel, gain_q8))
