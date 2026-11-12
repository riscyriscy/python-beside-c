"""A small host tool: CRC-16/CCITT-FALSE of files, to hand to people who have no Python.

Pure Python and standard library only, so it can be run from source, from a zipapp (.pyz)
or from a single-file executable. Run: python3 crc_tool.py FILE [FILE ...]
"""

import argparse
import sys
from pathlib import Path

__version__ = "1.0"
CHECK_VALUE = 0x29B1  # CRC of b"123456789"


def crc16(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def how_am_i_running() -> str:
    # PyInstaller sets sys.frozen. Nuitka does not: it defines __compiled__ in each module.
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return "bundled executable"
    return "Python source or zipapp"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="crc_tool", description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--self-test", action="store_true", help="check the CRC of '123456789'")
    args = parser.parse_args(argv)

    if args.version:
        print(f"crc_tool {__version__} ({how_am_i_running()})")
        return 0
    if args.self_test:
        ok = crc16(b"123456789") == CHECK_VALUE
        print("self-test:", "ok" if ok else "FAILED")
        return 0 if ok else 1
    status = 0
    for path in args.files:
        try:
            print(f"{crc16(path.read_bytes()):04X}  {path}", flush=True)
        except OSError as exc:
            print(f"crc_tool: {exc.strerror}: {path}", file=sys.stderr)
            status = 2
    return status


def cli() -> None:  # entry point for zipapp, which ignores the return value of main()
    sys.exit(main())


if __name__ == "__main__":
    cli()
