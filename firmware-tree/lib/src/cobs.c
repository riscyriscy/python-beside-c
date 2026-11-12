#include "fw/cobs.h"

#include <string.h>

size_t cobs_encode(const uint8_t *in, size_t len, uint8_t *out)
{
    size_t code_index = 0;   /* where the current block's code byte goes */
    size_t o = 1;            /* next free output byte */
    uint8_t code = 1;

    for (size_t i = 0; i < len; i++) {
        if (in[i] == 0) {
            out[code_index] = code;
            code_index = o++;
            code = 1;
        } else {
            out[o++] = in[i];
            if (++code == 0xFF) {
                out[code_index] = code;
                code_index = o++;
                code = 1;
            }
        }
    }
    out[code_index] = code;
    return o;
}

size_t cobs_decode(const uint8_t *in, size_t len, uint8_t *out)
{
    size_t i = 0;
    size_t o = 0;

    while (i < len) {
        uint8_t code = in[i++];
        if (code == 0 || (size_t)(code - 1) > len - i) {
            return COBS_ERROR;
        }
        memcpy(out + o, in + i, (size_t)(code - 1));
        o += (size_t)(code - 1);
        i += (size_t)(code - 1);
        if (code < 0xFF && i < len) {
            out[o++] = 0;
        }
    }
    return o;
}
