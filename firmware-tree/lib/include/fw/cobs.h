#pragma once
#include <stddef.h>
#include <stdint.h>

#define COBS_ERROR ((size_t)-1)

/* Largest output of cobs_encode() for len input bytes. */
#define COBS_MAX_ENCODED(len) ((len) + (len) / 254u + 1u)

/* Consistent Overhead Byte Stuffing. The output has no 0x00 byte and no trailing delimiter.
 * out must hold COBS_MAX_ENCODED(len) bytes. Returns the number of bytes written. */
size_t cobs_encode(const uint8_t *in, size_t len, uint8_t *out);

/* out must hold len bytes. Returns the number of bytes written, or COBS_ERROR. */
size_t cobs_decode(const uint8_t *in, size_t len, uint8_t *out);
