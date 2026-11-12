"""Builds _adc_cffi, a CPython extension made from adc.c and the declarations below.

cffi's API mode compiles the declarations against adc.h. A field whose declared type or offset
differs from the header raises ffi.error the first time the type is used, and names the field.

Usage: python build_cffi.py   (writes _adc_cffi*.so next to this file)
"""

import os
import shutil
from pathlib import Path

from cffi import FFI

here = Path(__file__).resolve().parent
ffibuilder = FFI()
ffibuilder.cdef("""
    #define ADC_ERR_RANGE ...        /* the value is read from adc.h by the compiler */
    #define ADC_ERR_NODEV ...
    #define ADC_ERR_BUSY ...

    typedef struct adc_dev adc_dev;
    typedef struct {
        uint32_t timestamp_ms;
        int16_t value;
        uint8_t channel;
        ...;                         /* padding and anything else: the compiler fills it in */
    } adc_sample;
    typedef struct {
        uint8_t ready : 1;
        uint8_t overrun : 1;
        uint8_t channel : 3;
        uint8_t gain : 3;
    } adc_status;
    typedef union {
        uint32_t word;
        uint8_t bytes[4];
    } adc_reg;
    typedef void (*adc_callback)(const adc_sample *sample, void *user);

    adc_dev *adc_open(const char *name, int *err);
    void adc_close(adc_dev *dev);
    int adc_configure(adc_dev *dev, uint8_t channel, uint8_t gain);
    int adc_read(adc_dev *dev, int16_t *value);
    adc_status adc_get_status(const adc_dev *dev);
    void adc_get_reg(const adc_dev *dev, adc_reg *out);
    int adc_set_callback(adc_dev *dev, adc_callback cb, void *user);
    int adc_poll(adc_dev *dev, int n);

    extern "Python" void on_sample(const adc_sample *sample, void *user);
""")
ffibuilder.set_source(
    "_adc_cffi",
    '#include "adc.h"',
    sources=["../adc.c"],  # the C file is compiled into the module: no libadc.so
    include_dirs=[".."],
)

if __name__ == "__main__":
    work = here / "_build"  # scratch directory for the compiler's files
    work.mkdir(exist_ok=True)
    os.chdir(work)  # the paths above are relative to this directory
    built = Path(ffibuilder.compile(tmpdir=".", verbose=False))
    shutil.move(built, here / built.name)
    os.chdir(here)
    shutil.rmtree(work)
    (here / "adc.o").unlink(missing_ok=True)  # the compiler leaves its object file beside adc.c
