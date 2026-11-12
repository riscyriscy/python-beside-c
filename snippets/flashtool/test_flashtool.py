import hashlib
import random
import socket
import threading
from collections.abc import Callable

import pytest
from frametool.protocol import Frame

from flashtool import (
    BLOCK,
    BOOT,
    NAK,
    FakeBootloader,
    FlashAborted,
    FlashError,
    Wire,
    flash,
)

IMAGE = random.Random(1).randbytes(1000)


def start(fault: Callable[[int, bytes], bytes | None] | None = None, **options: int) -> tuple[Wire, FakeBootloader]:
    host, device = socket.socketpair()
    boot = FakeBootloader(device, **options)
    boot.start()
    return Wire(host, fault), boot


def test_clean_download_boots() -> None:
    wire, boot = start()
    report = flash(wire, IMAGE)
    assert (report.blocks, report.retries, boot.booted) == (8, 0, True)
    assert report.digest == hashlib.sha256(IMAGE).hexdigest()


def test_damaged_frame_is_sent_again() -> None:
    def flip(n: int, data: bytes) -> bytes | None:
        return data[:5] + bytes([data[5] ^ 0x40]) + data[6:] if n == 4 else data

    wire, boot = start(flip)
    assert flash(wire, IMAGE).retries == 1
    assert boot.wire.splitter.stats.bad_crc == 1


def test_lost_ack_is_harmless_because_a_write_is_addressed() -> None:
    wire, boot = start(drop_ack=6)
    assert flash(wire, IMAGE).retries == 1
    assert bytes(boot.memory[: len(IMAGE)]) == IMAGE


def test_flipped_flash_bit_fails_the_hash() -> None:
    wire, boot = start(flip_bit_at=300)
    with pytest.raises(FlashError, match="hash differs"):
        flash(wire, IMAGE)
    assert not boot.booted


def test_abort_leaves_an_image_that_will_not_boot() -> None:
    cancel = threading.Event()
    wire, boot = start()
    with pytest.raises(FlashAborted) as info:
        flash(wire, IMAGE, cancel, lambda done, total: cancel.set() if done == 3 else None)
    assert info.value.offset == 3 * BLOCK
    wire.send(Frame(BOOT, 0x77, hashlib.sha256(IMAGE).digest()))
    reply = wire.receive(0.5)
    assert reply is not None and reply.type == NAK and not boot.booted
