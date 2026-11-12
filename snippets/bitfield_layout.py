"""Packed bit fields: one C struct, GCC's layout and the two ctypes layouts.

Run:   python bitfield_layout.py
"""

import ctypes
import subprocess
import tempfile
import warnings
from pathlib import Path

C_SOURCE = r"""
#include <stdio.h>
#include <stdint.h>
struct __attribute__((packed)) reg { uint8_t mode : 3; uint16_t gain : 7; uint8_t flags; };
int main(void)
{
    struct reg r = {0};
    r.mode = 5; r.gain = 100; r.flags = 0xAA;
    printf("%zu", sizeof r);
    for (unsigned i = 0; i < sizeof r; i++) printf(" %02x", ((unsigned char *)&r)[i]);
    printf("\n");
    return 0;
}
"""

warnings.simplefilter("ignore", DeprecationWarning)  # 3.14 warns about _pack_ without _layout_


class RegPlain(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("mode", ctypes.c_uint8, 3),
        ("gain", ctypes.c_uint16, 7),
        ("flags", ctypes.c_uint8),
    ]


class RegMs(ctypes.LittleEndianStructure):
    _pack_ = 1
    _layout_ = "ms"
    _fields_ = [
        ("mode", ctypes.c_uint8, 3),
        ("gain", ctypes.c_uint16, 7),
        ("flags", ctypes.c_uint8),
    ]


def describe(reg: RegPlain | RegMs) -> str:
    reg.mode, reg.gain, reg.flags = 5, 100, 0xAA
    return f"{ctypes.sizeof(reg)} {bytes(reg).hex(' ')}"


with tempfile.TemporaryDirectory() as tmp:
    source = Path(tmp, "reg.c")
    source.write_text(C_SOURCE)
    subprocess.run(["cc", "-o", str(Path(tmp, "reg")), str(source)], check=True)
    c_result = subprocess.run([str(Path(tmp, "reg"))], capture_output=True, text=True, check=True)

print(f"C, gcc packed       size and bytes: {c_result.stdout.strip()}")
print(f"ctypes, _pack_ = 1  size and bytes: {describe(RegPlain())}")
print(f"ctypes, + 'ms'      size and bytes: {describe(RegMs())}")
