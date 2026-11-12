"""Rules that the C test sequencer calls. The host is C; the limits live here, so a change to
them needs no rebuild of the sequencer."""

import fw  # the module that sequencer.c registers before it starts the interpreter

LIMITS = {
    "supply_mv": (3135, 3465),  # 3.3 V +/- 5 %
    "temperature_cdeg": (-4000, 8500),
    "rate_hz": (9, 11),
}


def check(name: str, value: float) -> tuple[bool, str]:
    low, high = LIMITS[name]  # KeyError for a name that is not in the table
    ok = low <= value <= high
    return ok, f"{name} {value:g} is {'within' if ok else 'outside'} [{low}, {high}]"


def frame_ok(frame: bytes) -> bool:
    """A frame is a payload followed by its CRC-16 as 2 bytes, big endian."""
    return fw.crc16(frame[:-2]) == int.from_bytes(frame[-2:], "big")
