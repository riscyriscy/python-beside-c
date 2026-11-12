#include "fw/sensor.h"

int32_t sensor_millivolts(const sensor_hw_t *hw, uint8_t channel, int32_t gain_q8)
{
    int64_t scaled = (int64_t)hw->read_adc(hw->ctx, channel) * gain_q8; /* 4095 * gain_q8 needs 64 bits */
    return (int32_t)((scaled * 3300) / (4095 * 256));
}
