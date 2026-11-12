"""A segmentation fault in native code, and the Python stack that faulthandler prints.

Run: python3 -X faulthandler crash_demo.py   (or set PYTHONFAULTHANDLER=1)
"""

import ctypes


def read_register(address: int) -> int:
    return ctypes.c_uint32.from_address(address).value  # a bad pointer, as in C


def poll_status() -> int:
    return read_register(0)  # address 0: a NULL dereference


print("polling")
print(poll_status())
