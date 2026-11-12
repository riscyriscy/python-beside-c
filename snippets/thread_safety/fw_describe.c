/* Two ways to return a text for a log line: a static buffer, and a buffer from the caller. */
#include <stddef.h>
#include <stdio.h>
#include <string.h>

const char *fw_describe_static(unsigned id, unsigned mv)
{
    static char buf[48];                       /* one buffer, shared by every caller */
    snprintf(buf, sizeof buf, "unit %u", id);
    size_t n = strlen(buf);
    snprintf(buf + n, sizeof buf - n, " reads %u mV", mv);
    return buf;
}

int fw_describe(char *out, size_t cap, unsigned id, unsigned mv)
{
    return snprintf(out, cap, "unit %u reads %u mV", id, mv);   /* no state kept between calls */
}
