"""ctypes: call a C shared library and mirror a packed C struct, with no build step."""

import ctypes
import sys
from pathlib import Path

# libcrc16.so: the firmware's crc16.c built as a shared library (crc16.dll on Windows)
lib = ctypes.CDLL(str(Path(sys.argv[1]).resolve()))
lib.crc16_ccitt.argtypes = [ctypes.c_char_p, ctypes.c_size_t]  # always declare the signature
lib.crc16_ccitt.restype = ctypes.c_uint16  # default would be C int


class TelemetryWire(ctypes.LittleEndianStructure):
    """Byte-for-byte mirror of telemetry_t in native/telemetry.h."""

    _pack_ = 1  # like __attribute__((packed))
    _layout_ = "ms"  # Python 3.14: say explicitly that _pack_ follows MSVC/GCC packed rules
    _fields_ = [
        ("timestamp_ms", ctypes.c_uint32),
        ("temperature_cdeg", ctypes.c_int16),
        ("supply_mv", ctypes.c_uint16),
        ("status", ctypes.c_uint8),
    ]


data = b"123456789"
print(f"crc16_ccitt -> {lib.crc16_ccitt(data, len(data)):#06x}")
assert ctypes.sizeof(TelemetryWire) == 9, "wire format changed"
t = TelemetryWire.from_buffer_copy(bytes.fromhex("40e201002efbe50c02"))
print(f"{t.timestamp_ms} ms, {t.temperature_cdeg / 100} C, {t.supply_mv} mV, status {t.status:#x}")
