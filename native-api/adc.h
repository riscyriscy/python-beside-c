/* adc.h: a small ADC driver API of the kind a firmware HAL exposes.
 * It has an opaque handle, a callback, a union, a bit-field register and two error conventions. */
#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ADC_OK 0
#define ADC_ERR_RANGE (-2)   /* argument out of range */
#define ADC_ERR_NODEV (-3)   /* no such device */
#define ADC_ERR_BUSY (-4)    /* operation not allowed while polling */

typedef struct adc_dev adc_dev;   /* opaque: the layout is private to adc.c */

typedef struct {
    uint32_t timestamp_ms;
    int16_t value;
    uint8_t channel;          /* the compiler adds 1 byte of padding after this */
} adc_sample;

typedef struct {              /* a status register: bit fields, LSB first on GCC and Clang */
    uint8_t ready : 1;
    uint8_t overrun : 1;
    uint8_t channel : 3;
    uint8_t gain : 3;
} adc_status;

typedef union {               /* the same 32-bit register seen as a word or as bytes */
    uint32_t word;
    uint8_t bytes[4];
} adc_reg;

typedef void (*adc_callback)(const adc_sample *sample, void *user);

/* Returns NULL and sets *err (ADC_ERR_NODEV) when the name is not known. */
adc_dev *adc_open(const char *name, int *err);
void adc_close(adc_dev *dev);

/* Returns ADC_OK or a negative ADC_ERR_* code. */
int adc_configure(adc_dev *dev, uint8_t channel, uint8_t gain);

/* Returns 0, or -1 with errno set (EAGAIN when no sample is waiting). */
int adc_read(adc_dev *dev, int16_t *value);

adc_status adc_get_status(const adc_dev *dev);
void adc_get_reg(const adc_dev *dev, adc_reg *out);

int adc_set_callback(adc_dev *dev, adc_callback cb, void *user);

/* Produces n samples and calls the callback once for each. Returns n. */
int adc_poll(adc_dev *dev, int n);

/* Sizes as the C compiler sees them, for checking a Python mirror. */
size_t adc_sizeof_sample(void);
size_t adc_sizeof_status(void);

#ifdef __cplusplus
}
#endif
