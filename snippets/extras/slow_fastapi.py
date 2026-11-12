"""The same blocking call in two FastAPI handlers. Run: uvicorn slow_fastapi:app --port 8002"""

import ctypes

from fastapi import FastAPI

libc = ctypes.CDLL(None)
app = FastAPI()


@app.get("/slow_async")
async def slow_async() -> dict[str, bool]:
    # runs on the event loop: the C call stops every other request
    libc.usleep(200_000)
    return {"ok": True}


@app.get("/slow_def")
def slow_def() -> dict[str, bool]:  # runs on a thread of a pool: other requests continue
    libc.usleep(200_000)
    return {"ok": True}
