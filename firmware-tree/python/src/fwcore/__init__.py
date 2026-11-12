"""The firmware's fw_core library (CRC-16 and COBS) for host tools and tests."""

from ._fwcore import MAX_FRAME, cobs_decode, cobs_encode, crc16

__all__ = ["MAX_FRAME", "cobs_decode", "cobs_encode", "crc16"]
