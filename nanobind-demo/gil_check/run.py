import threading
import time

import gilmod

count = 0
stop = False


def counter() -> None:
    global count
    while not stop:
        count += 1


t = threading.Thread(target=counter)
t.start()
time.sleep(0.1)
for name in ("hold", "release"):
    fn = getattr(gilmod, name)
    start = count
    t0 = time.perf_counter()
    fn(300)
    elapsed = time.perf_counter() - t0
    print(
        f"{name:8s} 300 ms call took {elapsed * 1000:.0f} ms; the counter thread advanced {count - start:,} steps"
    )
stop = True
t.join()
