"""Five downloads of the same 1000-byte image against the fake bootloader. Run: python flash_demo.py"""

import hashlib
import random
import socket
import threading
from collections.abc import Callable

from frametool.protocol import Frame

from flashtool import BLOCK, BOOT, FakeBootloader, FlashAborted, FlashError, Wire, flash

IMAGE = random.Random(1).randbytes(1000)


def session(fault: Callable[[int, bytes], bytes | None] | None = None, **boot_options: int) -> tuple[Wire, FakeBootloader]:
    host, device = socket.socketpair()
    boot = FakeBootloader(device, **boot_options)
    boot.start()
    return Wire(host, fault), boot


def flip_frame_4(n: int, data: bytes) -> bytes | None:
    return data[:5] + bytes([data[5] ^ 0x40]) + data[6:] if n == 4 else data  # n counts frames sent, HELLO is 1


def main() -> None:
    blocks = -(-len(IMAGE) // BLOCK)
    print(f"image {len(IMAGE)} bytes, {BLOCK} data bytes per frame, {blocks} blocks, sha256 {hashlib.sha256(IMAGE).hexdigest()[:16]}")

    wire, boot = session()
    report = flash(wire, IMAGE)
    print(f"1 clean line: {report.blocks} blocks, {report.retries} retries, booted {boot.booted}")

    wire, boot = session(flip_frame_4)
    report = flash(wire, IMAGE)
    print(f"2 one frame damaged on the wire: {report.blocks} blocks, {report.retries} retry, "
          f"bootloader counted {boot.wire.splitter.stats.bad_crc} bad CRC, booted {boot.booted}")

    wire, boot = session(drop_ack=6)
    report = flash(wire, IMAGE)
    print(f"3 ACK of write 6 lost: {report.retries} retry, bootloader got {boot.writes} write frames for {blocks} blocks, "
          f"image intact {bytes(boot.memory[:len(IMAGE)]) == IMAGE}")

    wire, boot = session(flip_bit_at=300)
    try:
        flash(wire, IMAGE)
    except FlashError as exc:
        print(f"4 one flash bit flipped: FlashError: {exc}; booted {boot.booted}")

    cancel = threading.Event()
    wire, boot = session()
    try:
        flash(wire, IMAGE, cancel=cancel, on_block=lambda done, total: cancel.set() if done == 3 else None)
    except FlashAborted as exc:
        print(f"5 cancelled after 3 blocks: {exc}")
    wire.send(Frame(BOOT, 0x77, hashlib.sha256(IMAGE).digest()))
    reply = wire.receive(0.5)
    print(f"  boot request after the abort: type {reply.type:#x} reason {reply.payload[0]}, booted {boot.booted}" if reply else "  no reply")


if __name__ == "__main__":
    main()
