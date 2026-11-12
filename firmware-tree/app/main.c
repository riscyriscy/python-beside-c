/* A stand-in for the firmware image: it links the same fw_core library as the Python module. */
#include <stdio.h>
#include <string.h>

#include "fw/cobs.h"
#include "fw/crc16.h"

int main(void)
{
    const uint8_t check[] = "123456789";
    uint16_t crc = crc16_ccitt(check, 9);
    printf("crc16 of 123456789: %#06x\n", crc);

    const uint8_t frame[] = {0x10, 0x00, 0x20, 0x00, 0x00, 0x30};
    uint8_t enc[COBS_MAX_ENCODED(sizeof frame)];
    uint8_t dec[sizeof frame];
    size_t n = cobs_encode(frame, sizeof frame, enc);
    size_t m = cobs_decode(enc, n, dec);
    printf("cobs: %zu bytes in, %zu encoded, %zu decoded, round trip %s\n", sizeof frame, n, m,
           (m == sizeof frame && memcmp(frame, dec, m) == 0) ? "ok" : "FAILED");
    return (crc == 0x29B1u && m == sizeof frame && memcmp(frame, dec, m) == 0) ? 0 : 1;
}
