"""A firmware download over the frametool link: blocks, retries, an image hash and a fake bootloader."""

from __future__ import annotations

import hashlib
import socket
import struct
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from frametool import cobs
from frametool.link import FrameSplitter, LinkStats
from frametool.protocol import Frame

HELLO, ERASE, WRITE, VERIFY, BOOT = 0x30, 0x31, 0x32, 0x33, 0x34
ACK, NAK = 0x40, 0x41
NAK_RANGE, NAK_NO_IMAGE = 2, 3
RETRIES, ACK_TIMEOUT_S = 3, 0.15  # resends per request, and how long to wait for each ACK
BLOCK = 128  # data bytes per frame: 128 + 4 + 4 + 2 bytes stay under the splitter's 300-byte limit


class FlashError(Exception):
    pass


class FlashAborted(FlashError):
    def __init__(self, offset: int) -> None:
        super().__init__(f"aborted at offset {offset:#x}")
        self.offset = offset


class Wire:
    """One end of a byte link. fault(n, data) may damage or drop (return None) the nth frame sent."""

    def __init__(self, sock: socket.socket, fault: Callable[[int, bytes], bytes | None] | None = None) -> None:
        self.sock, self.fault, self.sent = sock, fault, 0
        self.splitter = FrameSplitter(LinkStats())
        self.queue: deque[Frame] = deque()

    def send(self, frame: Frame) -> None:
        data = cobs.encode(frame.to_bytes()) + b"\x00"
        self.sent += 1
        if self.fault is not None:
            damaged = self.fault(self.sent, data)
            if damaged is None:
                return
            data = damaged
        self.sock.sendall(data)

    def receive(self, timeout_s: float) -> Frame | None:
        self.sock.settimeout(timeout_s)
        while not self.queue:  # a chunk can hold several frames: keep them all
            try:
                chunk = self.sock.recv(4096)
            except TimeoutError:
                return None
            if not chunk:
                return None
            self.queue.extend(self.splitter.feed(chunk))
        return self.queue.popleft()


@dataclass
class FlashReport:
    blocks: int
    retries: int
    digest: str


def exchange(wire: Wire, seq: int, ftype: int, payload: bytes = b"") -> tuple[Frame, int]:
    """Send one request and wait for the reply with the same seq. Returns the reply and the retries used."""
    for attempt in range(RETRIES + 1):
        wire.send(Frame(ftype, seq, payload))
        deadline = time.monotonic() + ACK_TIMEOUT_S
        while (left := deadline - time.monotonic()) > 0:
            reply = wire.receive(left)
            if reply is None or reply.seq != seq:
                continue  # silence, or a late reply to an earlier request: keep waiting until the deadline
            if reply.type == ACK:
                return reply, attempt
            break  # a NAK for this request: send it again now
    raise FlashError(f"no ACK for type {ftype:#x} seq {seq} after {RETRIES + 1} tries")


def flash(
    wire: Wire,
    image: bytes,
    cancel: threading.Event | None = None,
    on_block: Callable[[int, int], None] | None = None,
) -> FlashReport:
    seq = 0
    exchange(wire, seq, HELLO)
    seq += 1
    exchange(wire, seq, ERASE, struct.pack("<I", len(image)))
    retries = blocks = 0
    for offset in range(0, len(image), BLOCK):
        if cancel is not None and cancel.is_set():
            raise FlashAborted(offset)
        seq = (seq + 1) & 0xFF
        _, used = exchange(wire, seq, WRITE, struct.pack("<I", offset) + image[offset : offset + BLOCK])
        retries += used
        blocks += 1
        if on_block is not None:
            on_block(blocks, -(-len(image) // BLOCK))  # a GUI turns this into a progress signal
    seq = (seq + 1) & 0xFF
    reply, _ = exchange(wire, seq, VERIFY)
    digest = hashlib.sha256(image).digest()
    if reply.payload != digest:
        raise FlashError(f"image hash differs: device {reply.payload.hex()[:16]}, expected {digest.hex()[:16]}")
    seq = (seq + 1) & 0xFF
    exchange(wire, seq, BOOT, digest)  # the bootloader boots only if its own hash of the flash matches
    return FlashReport(blocks, retries, digest.hex())


class FakeBootloader(threading.Thread):
    """Answers HELLO, ERASE, WRITE, VERIFY and BOOT. BOOT carries the expected SHA-256 and is refused on a mismatch."""

    def __init__(self, sock: socket.socket, size: int = 4096, drop_ack: int | None = None, flip_bit_at: int | None = None) -> None:
        super().__init__(daemon=True)
        self.wire = Wire(sock)
        self.memory = bytearray(b"\xff" * size)
        self.written = 0
        self.booted = False
        self.drop_ack, self.flip_bit_at, self.writes = drop_ack, flip_bit_at, 0

    def reply(self, seq: int, ftype: int, payload: bytes = b"") -> None:
        self.wire.send(Frame(ftype, seq, payload))

    def run(self) -> None:
        while True:
            try:
                frame = self.wire.receive(0.5)  # a frame with a bad CRC is dropped without a reply
            except OSError:
                return  # the host closed the link
            if frame is None:
                if self.booted:
                    return
                continue
            self.handle(frame)

    def handle(self, frame: Frame) -> None:
        if frame.type == WRITE:
            self.write(frame)
        elif frame.type == VERIFY:
            self.reply(frame.seq, ACK, hashlib.sha256(self.memory[: self.written]).digest())
        elif frame.type == BOOT:
            if hashlib.sha256(self.memory[: self.written]).digest() == frame.payload:
                self.booted = True
                self.reply(frame.seq, ACK)
            else:
                self.reply(frame.seq, NAK, bytes([NAK_NO_IMAGE]))
        else:
            self.reply(frame.seq, ACK)  # HELLO, ERASE

    def write(self, frame: Frame) -> None:
        self.writes += 1
        (offset,) = struct.unpack_from("<I", frame.payload)
        data = frame.payload[4:]
        if offset + len(data) > len(self.memory):
            self.reply(frame.seq, NAK, bytes([NAK_RANGE]))
            return
        self.memory[offset : offset + len(data)] = data
        self.written = max(self.written, offset + len(data))
        if self.flip_bit_at is not None and self.written > self.flip_bit_at >= offset:
            self.memory[self.flip_bit_at] ^= 0x01
        if self.writes != self.drop_ack:  # a lost ACK: the block was stored, the reply never leaves
            self.reply(frame.seq, ACK)
