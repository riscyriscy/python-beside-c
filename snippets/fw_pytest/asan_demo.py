"""The caller sizes the output buffer by the input length, not by COBS_MAX_ENCODED(len)."""

import fw

data = bytes(range(1, 255))  # 254 non-zero bytes: the encoding needs 256
out = fw.ffi.new("uint8_t[]", len(data))  # the mistake: 254 bytes
fw.lib.cobs_encode(data, len(data), out)
print("returned without a report")
