#pragma once
#include <stdint.h>

/* Hardware seam: the firmware reads the ADC only through this table. */
typedef struct {
    uint16_t (*read_adc)(void *ctx, uint8_t channel); /* 12-bit result, 0..4095 */
    void *ctx;
} sensor_hw_t;

/* Millivolts at the pin for a 3300 mV reference. gain_q8 is a gain in Q8 (256 = 1.0). */
int32_t sensor_millivolts(const sensor_hw_t *hw, uint8_t channel, int32_t gain_q8);
