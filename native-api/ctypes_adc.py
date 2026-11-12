"""ctypes on a realistic C API: opaque handle, callback, union, bit fields, two error conventions.

Usage: python ctypes_adc.py path/to/libadc.so
"""

import ctypes
import errno
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Self

ADC_ERR_RANGE, ADC_ERR_NODEV = -2, -3


class _AdcDev(ctypes.Structure):
    """Opaque handle: C never shows the fields, so Python declares none."""


class Sample(ctypes.Structure):  # natural alignment, so the compiler's 1 byte of padding is implied
    _fields_ = [
        ("timestamp_ms", ctypes.c_uint32),
        ("value", ctypes.c_int16),
        ("channel", ctypes.c_uint8),
    ]


class Status(ctypes.Structure):  # bit fields: ctypes takes the width as the third item
    _fields_ = [
        ("ready", ctypes.c_uint8, 1),
        ("overrun", ctypes.c_uint8, 1),
        ("channel", ctypes.c_uint8, 3),
        ("gain", ctypes.c_uint8, 3),
    ]


class Reg(ctypes.Union):
    _fields_ = [("word", ctypes.c_uint32), ("bytes", ctypes.c_uint8 * 4)]


# void (*)(const adc_sample *, void *): the first argument is the return type
CALLBACK = ctypes.CFUNCTYPE(None, ctypes.POINTER(Sample), ctypes.c_void_p)


class AdcError(Exception):
    def __init__(self, what: str, code: int) -> None:
        super().__init__(f"{what}: error {code}")
        self.code = code


def load(path: str) -> ctypes.CDLL:
    lib = ctypes.CDLL(path, use_errno=True)  # use_errno keeps a private copy of C's errno
    handle = ctypes.POINTER(_AdcDev)
    lib.adc_open.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
    lib.adc_open.restype = handle
    lib.adc_close.argtypes = [handle]
    lib.adc_close.restype = None
    lib.adc_configure.argtypes = [handle, ctypes.c_uint8, ctypes.c_uint8]
    lib.adc_configure.restype = ctypes.c_int
    lib.adc_read.argtypes = [handle, ctypes.POINTER(ctypes.c_int16)]
    lib.adc_read.restype = ctypes.c_int
    lib.adc_get_status.argtypes = [handle]
    lib.adc_get_status.restype = Status  # a struct returned by value
    lib.adc_get_reg.argtypes = [handle, ctypes.POINTER(Reg)]
    lib.adc_get_reg.restype = None
    lib.adc_set_callback.argtypes = [handle, CALLBACK, ctypes.c_void_p]
    lib.adc_set_callback.restype = ctypes.c_int
    lib.adc_poll.argtypes = [handle, ctypes.c_int]
    lib.adc_poll.restype = ctypes.c_int
    lib.adc_sizeof_sample.restype = ctypes.c_size_t
    lib.adc_sizeof_status.restype = ctypes.c_size_t
    return lib


class Adc:
    """Owns one adc_dev. The with statement is the close() that C code would call in cleanup."""

    def __init__(self, lib: ctypes.CDLL, name: str) -> None:
        self._lib = lib
        err = ctypes.c_int(0)  # out-parameter convention: a pointer to an int
        handle = lib.adc_open(name.encode(), ctypes.byref(err))
        if not handle:  # a NULL pointer is falsy
            raise AdcError(f"open {name!r}", err.value)
        self._h: ctypes._Pointer[_AdcDev] | None = handle
        self._cb: object = None  # keeps the callback object alive for the C side
        self._failure: Exception | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def handle(self) -> "ctypes._Pointer[_AdcDev]":
        if self._h is None:  # a closed wrapper must never pass NULL to the C side
            raise ValueError("adc is closed")
        return self._h

    def close(self) -> None:
        if self._h:
            self._lib.adc_close(self._h)
            self._h = None  # a second close() does nothing instead of a double free

    def configure(self, channel: int, gain: int) -> None:
        code = self._lib.adc_configure(self.handle, channel, gain)  # negative-code convention
        if code < 0:
            raise AdcError("configure", code)

    def read(self) -> int:
        value = ctypes.c_int16()
        if self._lib.adc_read(self.handle, ctypes.byref(value)) == -1:  # errno convention
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err))  # EAGAIN becomes BlockingIOError
        return value.value

    def status(self) -> Status:
        return self._lib.adc_get_status(self.handle)  # type: ignore[no-any-return]

    def reg(self) -> Reg:
        out = Reg()
        self._lib.adc_get_reg(self.handle, ctypes.byref(out))
        return out

    def on_sample(self, fn: Callable[[Sample], None]) -> None:
        def trampoline(sample: "ctypes._Pointer[Sample]", _user: int | None) -> None:
            try:
                fn(sample.contents)  # valid only during the call: copy what you keep
            except Exception as exc:  # an exception cannot cross the C frames
                self._failure = self._failure or exc

        self._cb = CALLBACK(trampoline)
        self._lib.adc_set_callback(self.handle, self._cb, None)

    def poll(self, n: int) -> int:
        self._failure = None
        done: int = self._lib.adc_poll(self.handle, n)
        if self._failure is not None:
            raise self._failure  # re-raised here, after C has returned
        return done


def main() -> None:
    lib = load(str(Path(sys.argv[1]).resolve()))

    # 1. The mirror must match the compiler's layout. ctypes cannot check it at build time.
    sizes = (ctypes.sizeof(Sample), ctypes.sizeof(Status), ctypes.sizeof(Reg))
    print(f"sizes: Sample {sizes[0]}, Status {sizes[1]}, Reg {sizes[2]}")
    assert sizes[0] == lib.adc_sizeof_sample() and sizes[1] == lib.adc_sizeof_status()

    # 2. A typed opaque pointer rejects the wrong kind of argument
    try:
        lib.adc_close(ctypes.c_int(0))
    except ctypes.ArgumentError as exc:
        print("wrong handle type:", type(exc).__name__)

    # 3. Error convention 1: NULL return plus an out-parameter
    try:
        Adc(lib, "adc9")
    except AdcError as exc:
        print("open failed:", exc, "(NODEV)" if exc.code == ADC_ERR_NODEV else "")

    with Adc(lib, "adc0") as adc:
        # 4. Error convention 2: a negative code
        adc.configure(channel=3, gain=5)
        try:
            adc.configure(channel=9, gain=1)
        except AdcError as exc:
            print("configure failed:", exc, "(RANGE)" if exc.code == ADC_ERR_RANGE else "")

        # 5. Error convention 3: -1 and errno
        try:
            adc.read()
        except BlockingIOError as exc:
            print("read failed:", errno.errorcode[exc.errno or 0])

        # 6. A callback, called from C while poll() runs
        seen: list[tuple[int, int, int]] = []
        adc.on_sample(lambda s: seen.append((s.timestamp_ms, s.value, s.channel)))
        print("poll delivered", adc.poll(4), "samples:", seen)

        # 7. Bit fields, a struct returned by value
        st = adc.status()
        print(f"status: ready={st.ready} channel={st.channel} gain={st.gain} raw={bytes(st).hex()}")

        # 8. A union: the same 4 bytes as a word and as an array
        reg = adc.reg()
        print(f"reg: word={reg.word:#010x} bytes={bytes(reg.bytes).hex()}")
        print("read:", adc.read(), "then ready =", adc.status().ready)

        # 9. An exception inside a callback does not cross C. The wrapper carries it out.
        def bad(s: Sample) -> None:
            if s.timestamp_ms > 60:
                raise ValueError("value out of limits")

        adc.on_sample(bad)
        try:
            adc.poll(3)
        except ValueError as exc:
            print("raised after poll returned:", exc)

        # Without the trampoline, ctypes reports the exception to sys.unraisablehook and goes on
        lost: list[str] = []
        sys.unraisablehook = lambda u: lost.append(type(u.exc_value).__name__)

        def naive(sample: "ctypes._Pointer[Sample]", _user: int | None) -> None:
            raise RuntimeError("lost")

        raw = CALLBACK(naive)
        lib.adc_set_callback(adc.handle, raw, None)
        print("naive callback: poll returned", lib.adc_poll(adc.handle, 2), "lost", lost)
        lib.adc_set_callback(adc.handle, CALLBACK(), None)  # NULL callback before `raw` goes away

    # 10. After close() every method refuses. Passing the NULL handle to C would crash the process.
    try:
        adc.configure(channel=1, gain=1)
    except ValueError as exc:
        print("use after close:", exc)


if __name__ == "__main__":
    main()
