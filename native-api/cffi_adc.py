"""cffi (API mode) on the same C API as ctypes_adc.py. Build first: python build_cffi.py"""

import errno
import os
from collections.abc import Callable
from typing import Any, Self

from _adc_cffi import ffi, lib  # type: ignore[import-not-found]


class AdcError(Exception):
    def __init__(self, what: str, code: int) -> None:
        super().__init__(f"{what}: error {code}")
        self.code = code


class Context:
    """What the C callback needs, passed through its void *user as a cffi handle."""

    def __init__(self, fn: Callable[[Any], None]) -> None:
        self.fn = fn
        self.failure: Exception | None = None


@ffi.def_extern()  # type: ignore[untyped-decorator]
def on_sample(sample: Any, user: Any) -> None:
    ctx: Context = ffi.from_handle(user)
    try:
        ctx.fn(sample)  # a pointer to C memory, valid only during the call
    except Exception as exc:  # an exception cannot cross the C frames
        ctx.failure = ctx.failure or exc


class Adc:
    def __init__(self, name: str) -> None:
        err = ffi.new("int *")
        dev = lib.adc_open(name.encode(), err)
        if dev == ffi.NULL:
            raise AdcError(f"open {name!r}", err[0])
        self._dev = ffi.gc(dev, lib.adc_close)  # adc_close runs when this object is collected
        self._ctx: Context | None = None
        self._handle: Any = None  # keeps the handle alive while C holds the pointer

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        ffi.release(self._dev)  # runs adc_close now and disarms the collector's call

    @property
    def dev(self) -> Any:
        return self._dev

    def configure(self, channel: int, gain: int) -> None:
        code = lib.adc_configure(self._dev, channel, gain)
        if code < 0:
            raise AdcError("configure", code)

    def read(self) -> int:
        value = ffi.new("int16_t *")
        if lib.adc_read(self._dev, value) == -1:
            raise OSError(ffi.errno, os.strerror(ffi.errno))  # ffi.errno: errno after the call
        return int(value[0])

    def on_sample(self, fn: Callable[[Any], None]) -> None:
        self._ctx = Context(fn)
        self._handle = ffi.new_handle(self._ctx)
        lib.adc_set_callback(self._dev, lib.on_sample, self._handle)

    def poll(self, n: int) -> int:
        if self._ctx is not None:
            self._ctx.failure = None
        done = int(lib.adc_poll(self._dev, n))
        if self._ctx is not None and self._ctx.failure is not None:
            raise self._ctx.failure
        return done


def main() -> None:
    # 1. The compiler fixed the layout, so there is nothing to compare by hand
    print(
        "sizes:",
        "sample",
        ffi.sizeof("adc_sample"),
        "status",
        ffi.sizeof("adc_status"),
        "reg",
        ffi.sizeof("adc_reg"),
    )

    # 2. Error constants come from adc.h, not from a copy typed into Python
    print("constants:", lib.ADC_ERR_RANGE, lib.ADC_ERR_NODEV, lib.ADC_ERR_BUSY)

    # 3. Error conventions, as in the ctypes version
    try:
        Adc("adc9")
    except AdcError as exc:
        print("open failed:", exc)

    with Adc("adc0") as adc:
        adc.configure(channel=3, gain=5)
        try:
            adc.configure(channel=9, gain=1)
        except AdcError as exc:
            print("configure failed:", exc)
        try:
            adc.read()
        except BlockingIOError as exc:
            print("read failed:", errno.errorcode[exc.errno or 0])

        # 4. A callback with a handle for its user pointer
        seen: list[tuple[int, int, int]] = []
        adc.on_sample(lambda s: seen.append((s.timestamp_ms, s.value, s.channel)))
        print("poll delivered", adc.poll(4), "samples:", seen)

        # 5. A struct with bit fields returned by value, and a union
        st = lib.adc_get_status(adc.dev)
        print(f"status: ready={st.ready} channel={st.channel} gain={st.gain}")
        reg = ffi.new("adc_reg *")
        lib.adc_get_reg(adc.dev, reg)
        print(f"reg: word={reg.word:#010x} bytes={bytes(reg.bytes).hex()}")
        print("read:", adc.read())

        # 6. An exception in a callback
        def bad(s: Any) -> None:
            if s.timestamp_ms > 60:
                raise ValueError("value out of limits")

        adc.on_sample(bad)
        try:
            adc.poll(3)
        except ValueError as exc:
            print("raised after poll returned:", exc)


if __name__ == "__main__":
    main()
