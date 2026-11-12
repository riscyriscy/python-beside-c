/* adc.c: a simulated ADC. Samples are a triangle wave, so the output is the same on every run. */
#include "adc.h"

#include <errno.h>
#include <stdlib.h>
#include <string.h>

struct adc_dev {
    uint8_t channel;
    uint8_t gain;
    uint32_t clock_ms;
    int16_t phase;
    int have_sample;
    int16_t last;
    int polling;
    adc_callback cb;
    void *user;
};

adc_dev *adc_open(const char *name, int *err)
{
    if (strcmp(name, "adc0") != 0) {
        if (err) *err = ADC_ERR_NODEV;
        return NULL;
    }
    adc_dev *dev = calloc(1, sizeof *dev);
    if (!dev) {
        if (err) *err = ADC_ERR_NODEV;
        return NULL;
    }
    if (err) *err = ADC_OK;
    return dev;
}

void adc_close(adc_dev *dev) { free(dev); }

int adc_configure(adc_dev *dev, uint8_t channel, uint8_t gain)
{
    if (dev->polling) return ADC_ERR_BUSY;
    if (channel > 7 || gain > 7) return ADC_ERR_RANGE;
    dev->channel = channel;
    dev->gain = gain;
    return ADC_OK;
}

int adc_read(adc_dev *dev, int16_t *value)
{
    if (!dev->have_sample) {
        errno = EAGAIN;
        return -1;
    }
    *value = dev->last;
    dev->have_sample = 0;
    return 0;
}

adc_status adc_get_status(const adc_dev *dev)
{
    adc_status s = {0};
    s.ready = dev->have_sample;
    s.overrun = 0;
    s.channel = dev->channel;
    s.gain = dev->gain;
    return s;
}

void adc_get_reg(const adc_dev *dev, adc_reg *out)
{
    out->word = 0;
    out->bytes[0] = (uint8_t)(dev->have_sample | (dev->channel << 2));
    out->bytes[1] = dev->gain;
    out->bytes[3] = 0xA5;
}

int adc_set_callback(adc_dev *dev, adc_callback cb, void *user)
{
    if (dev->polling) return ADC_ERR_BUSY;
    dev->cb = cb;
    dev->user = user;
    return ADC_OK;
}

int adc_poll(adc_dev *dev, int n)
{
    dev->polling = 1;
    for (int i = 0; i < n; i++) {
        dev->phase = (int16_t)((dev->phase + 250) % 1000);
        dev->clock_ms += 10;
        dev->last = (int16_t)(dev->phase < 500 ? dev->phase : 1000 - dev->phase);
        dev->have_sample = 1;
        if (dev->cb) {
            adc_sample s = {dev->clock_ms, dev->last, dev->channel};
            dev->cb(&s, dev->user);
        }
    }
    dev->polling = 0;
    return n;
}

size_t adc_sizeof_sample(void) { return sizeof(adc_sample); }
size_t adc_sizeof_status(void) { return sizeof(adc_status); }
