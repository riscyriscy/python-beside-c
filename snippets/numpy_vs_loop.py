"""When does NumPy / SciPy beat a pure-Python loop on an ADC capture?

Run: python3 numpy_vs_loop.py   (needs: uv sync)
"""

import math
import random
import timeit
from collections.abc import Callable
from typing import Any

import numpy as np
from scipy import signal

FS = 100_000.0  # sample rate, Hz
N = 1_000_000  # 10 s of capture at 100 kS/s
TONE_HZ = 1_234.0

# A synthetic 12-bit capture: mid-scale offset, a tone and noise, clipped to 0..4095.
rng = random.Random(7)
codes = [
    min(4095, max(0, round(2048 + 1000 * math.sin(2 * math.pi * TONE_HZ * i / FS)
                           + rng.gauss(0, 40))))
    for i in range(N)
]
arr = np.array(codes, dtype=np.int16)


def best_ms(fn: Callable[[], object], repeat: int = 5, number: int = 1) -> float:
    return min(timeit.repeat(fn, repeat=repeat, number=number)) / number * 1000.0


# 1. Convert codes to volts and take the RMS of the AC part ---------------------------
def rms_loop() -> float:
    volts = [c * 3.3 / 4095 for c in codes]
    mean = sum(volts) / len(volts)
    return math.sqrt(sum((v - mean) ** 2 for v in volts) / len(volts))


def rms_numpy() -> float:
    volts = arr * (3.3 / 4095)
    return float(np.sqrt(np.mean((volts - volts.mean()) ** 2)))


# 2. A 4th-order Butterworth low-pass at 5 kHz ------------------------------------------
sos = signal.butter(4, 5_000.0, btype="low", fs=FS, output="sos")


def biquad_loop() -> list[float]:
    out = [float(c) for c in codes]
    for b0, b1, b2, _a0, a1, a2 in sos:  # each row is one second-order section
        x1 = x2 = y1 = y2 = 0.0
        for i, x in enumerate(out):
            y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            out[i] = y
            x2, x1, y2, y1 = x1, x, y1, y
    return out


def biquad_scipy() -> Any:
    return signal.sosfilt(sos, arr.astype(np.float64))


# 3. Windowed spectrum and the strongest bin --------------------------------------------
def spectrum_peak() -> float:
    x = arr[:65_536].astype(np.float64)
    x -= x.mean()
    spec = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    return float(np.argmax(spec) * FS / x.size)


# 4. The other side: a 15-sample frame, where NumPy only adds overhead -------------------
frame = codes[:15]
frame_arr = arr[:15]

if __name__ == "__main__":
    print(f"numpy {np.__version__}, scipy {__import__('scipy').__version__}, {N} samples")
    t_loop, t_np = best_ms(rms_loop), best_ms(rms_numpy)
    print(f"RMS of 1M codes     loop {t_loop:8.1f} ms   NumPy {t_np:7.2f} ms   "
          f"{t_loop / t_np:5.0f}x   ({rms_loop():.6f} vs {rms_numpy():.6f} V)")

    t_loop, t_sp = best_ms(biquad_loop, repeat=3), best_ms(biquad_scipy)
    err = float(np.max(np.abs(np.array(biquad_loop()) - biquad_scipy())))
    print(f"Butterworth, 1M     loop {t_loop:8.1f} ms   SciPy {t_sp:7.2f} ms   "
          f"{t_loop / t_sp:5.0f}x   (max difference {err:.1e} codes)")

    t_fft = best_ms(spectrum_peak, number=10)
    print(f"Peak of 64 Ki FFT   NumPy {t_fft:6.2f} ms, strongest bin at "
          f"{spectrum_peak():.1f} Hz (tone is {TONE_HZ:.1f} Hz)")

    t_py = best_ms(lambda: sum(frame) / len(frame), number=10_000)
    t_na = best_ms(lambda: frame_arr.mean(), number=10_000)
    print(f"Mean of 15 samples  Python {t_py * 1000:6.2f} us  NumPy {t_na * 1000:6.2f} us  "
          f"(NumPy is {t_na / t_py:.1f}x slower)")
