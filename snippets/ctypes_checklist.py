"""ctypes checklist: buffers, pointers, ownership, the GIL, errno and bitness.

Run: python3.14 ctypes_checklist.py   (Linux, gcc and glibc 2.33 or later)
"""

import ctypes
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

C_SOURCE = r"""
#define _GNU_SOURCE
#include <errno.h>
#include <malloc.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* Fills a caller-owned buffer; snprintf never writes past n bytes. */
int fill_name(char *buf, size_t n, int unit)
{
    return snprintf(buf, n, "sensor-%d", unit);
}

/* 256 KiB is above glibc's mmap threshold, so the block sits near 0x7f...,
 * far above 4 GiB on x86-64 Linux. */
void *big_pointer(void)
{
    static void *block;  /* the same block on every call, so results compare */
    if (block == NULL) {
        block = malloc(256 * 1024);
    }
    return block;
}
void *null_pointer(void) { return NULL; }

/* Returns what C receives: shows whether a 64-bit value survived the call. */
uint64_t echo_pointer(void *p) { return (uint64_t)(uintptr_t)p; }

/* The caller owns the returned block and must free() it. */
char *dup_name(void)
{
    char *s = malloc(1001);
    memset(s, 'x', 1000);
    s[1000] = '\0';
    return s;
}

size_t heap_in_use(void) { return mallinfo2().uordblks; }

void nap_ms(int ms) { usleep((useconds_t)ms * 1000); }

int fail_with(int e)
{
    errno = e;
    return -1;
}
"""

libc = ctypes.CDLL(None)  # the C library of the process, on Linux
libc.free.argtypes = [ctypes.c_void_p]
libc.free.restype = None


def build(tmp: Path) -> Path:
    src, so = tmp / "helper.c", tmp / "libhelper.so"
    src.write_text(C_SOURCE)
    cmd = ["gcc", "-shared", "-fPIC", "-O1", "-o", str(so), str(src)]
    subprocess.run(cmd, check=True)
    return so


def strings_and_buffers(lib: ctypes.CDLL) -> None:
    print("--- strings and buffers")
    lib.fill_name.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int]
    lib.fill_name.restype = ctypes.c_int
    buf = ctypes.create_string_buffer(8)  # a writable char[8], zero filled
    needed = lib.fill_name(buf, len(buf), 12)  # pass the real size, not a guess
    print(f"snprintf wanted {needed} chars; the 8-byte buffer holds {buf.value!r}")
    print("raw bytes:", buf.raw)
    big = ctypes.create_string_buffer(b"abc", 8)  # initial bytes, total size 8
    print(
        f"create_string_buffer(b'abc', 8): sizeof {ctypes.sizeof(big)}, "
        f"value {big.value!r}"
    )
    print(
        f"create_string_buffer(b'abc'): sizeof "
        f"{ctypes.sizeof(ctypes.create_string_buffer(b'abc'))} (adds the NUL)"
    )

    array = (ctypes.c_char * 6)()  # the same thing, spelled as a C array type
    ctypes.memmove(array, b"AB\x00CD\x00", 6)  # unchecked, like memcpy
    print(f"c_char * 6: value {array.value!r} stops at the NUL, raw {array.raw!r}")

    addr = ctypes.addressof(buf)  # the address as an int; no copy, no reference
    ctypes.memmove(addr + 4, b"XY", 2)  # overwrites buf[4:6]
    print("string_at(addr, 8):", ctypes.string_at(addr, 8))
    print("string_at(addr) up to the NUL:", ctypes.string_at(addr))
    print("buffer after memmove:", buf.raw)


def pointers(path: Path) -> None:
    print("--- c_void_p results")
    plain = ctypes.CDLL(str(path))  # restype left at the default, c_int
    raw = plain.big_pointer()  # ctypes reads a 32-bit int
    lib = ctypes.CDLL(str(path))  # a second handle keeps its own prototypes
    lib.big_pointer.restype = ctypes.c_void_p
    ptr = lib.big_pointer()
    assert ptr is not None
    print(f"restype c_void_p gives {type(ptr).__name__} {ptr:#x}")
    print(f"pointer is above 4 GiB: {ptr > 2**32}")
    print(f"default restype gives int {raw}, in hex {raw & 0xFFFFFFFF:#x}")
    print(f"same as the low 32 bits of the pointer: {raw & 0xFFFFFFFF == ptr % 2**32}")
    print(f"the upper bits, {ptr >> 32:#x}, are gone")
    lib.null_pointer.restype = ctypes.c_void_p
    print("NULL with restype c_void_p:", lib.null_pointer())

    plain.echo_pointer.restype = ctypes.c_uint64  # restype only, no argtypes
    print(f"without argtypes C received {plain.echo_pointer(ptr):#x} for {ptr:#x}")
    lib.echo_pointer.argtypes = [ctypes.c_void_p]
    lib.echo_pointer.restype = ctypes.c_uint64
    print(f"with argtypes C received    {lib.echo_pointer(ptr):#x}")
    libc.free(ptr)


def ownership(lib: ctypes.CDLL) -> None:
    print("--- who frees a returned char *")
    calls = 20_000

    lib.heap_in_use.restype = ctypes.c_size_t
    lib.dup_name.restype = ctypes.c_void_p  # keep the pointer so it can be freed
    before = lib.heap_in_use()
    for _ in range(calls):
        p = lib.dup_name()
        assert p is not None
        text = ctypes.string_at(p)  # copies the bytes into a Python bytes object
        libc.free(p)  # the block came from malloc, so it goes back with free
    grown = lib.heap_in_use() - before
    print(
        f"restype c_void_p, string_at, free: {len(text)} chars, heap grew "
        f"{grown // 1024} KiB over {calls} calls"
    )

    lib.dup_name.restype = ctypes.c_char_p  # ctypes copies the text, drops the pointer
    before = lib.heap_in_use()
    for _ in range(calls):
        value = lib.dup_name()
    grown = lib.heap_in_use() - before
    assert value is not None
    print(
        f"restype c_char_p: {len(value)} chars, heap grew "
        f"{grown // 1024} KiB over {calls} calls ({grown // calls} bytes each)"
    )


def gil(path: Path) -> None:
    print("--- CDLL and PyDLL with two threads, each calling a 400 ms sleep")
    for cls in (ctypes.CDLL, ctypes.PyDLL):
        lib = cls(str(path))
        lib.nap_ms.argtypes = [ctypes.c_int]
        lib.nap_ms.restype = None
        threads = [threading.Thread(target=lib.nap_ms, args=(400,)) for _ in range(2)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        print(f"{cls.__name__}: {time.perf_counter() - start:.1f} s")


def errno_copy(path: Path) -> None:
    print("--- use_errno")
    for flag in (False, True):
        lib = ctypes.CDLL(str(path), use_errno=flag)
        lib.fail_with.argtypes = [ctypes.c_int]
        lib.fail_with.restype = ctypes.c_int
        ctypes.set_errno(0)
        result = lib.fail_with(2)
        err = ctypes.get_errno()
        print(
            f"use_errno={flag}: returned {result}, get_errno() = {err} "
            f"{os.strerror(err) if err else ''}".rstrip()
        )


def bitness(tmp: Path) -> None:
    print("--- bitness")
    src, so = tmp / "tiny.c", tmp / "libtiny32.so"
    src.write_text("int tiny(void) { return 1; }\n")
    cmd = ["gcc", "-m32", "-shared", "-fPIC", "-nostdlib", "-o", str(so), str(src)]
    done = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        print("gcc -m32 failed:", done.stderr.strip().splitlines()[-1])
        return
    try:
        ctypes.CDLL(str(so))
    except OSError as exc:
        print(f"{type(exc).__name__}: {str(exc).replace(str(tmp), '<tmp>')}")


def main() -> None:
    print(f"Python {sys.version.split()[0]}, {ctypes.sizeof(ctypes.c_void_p) * 8}-bit")
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        so = build(tmp)
        lib = ctypes.CDLL(str(so))
        strings_and_buffers(lib)
        pointers(so)
        ownership(lib)
        gil(so)
        errno_copy(so)
        bitness(tmp)


if __name__ == "__main__":
    main()
