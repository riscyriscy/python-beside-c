"""The same API with FastAPI: validation, docs and async for free.

Run: uvicorn fastapi_app:app --host 127.0.0.1 --port 8000   (then open /docs)
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


class Sample(BaseModel):
    t: float
    temp_c: float


class Rate(BaseModel):
    # Validated before your code runs; 422 if not. strict=True: pydantic's default also accepts
    # "50" and 25.0 and converts them to 50 and 25, which the stdlib server rejects with 400
    period_ms: int = Field(strict=True, ge=10, le=10_000)


class Status(BaseModel):
    uptime_s: float
    period_ms: int
    latest: Sample


started = time.monotonic()
period_ms = 100
samples: deque[Sample] = deque(maxlen=600)


async def acquire() -> None:  # a task on the server's event loop: no locks needed
    while True:
        t = time.monotonic() - started
        samples.append(Sample(t=round(t, 3), temp_c=round(25 + 10 * math.sin(t), 2)))
        await asyncio.sleep(period_ms / 1000)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # start-up and shut-down hooks
    task = asyncio.create_task(acquire())
    yield
    task.cancel()


app = FastAPI(title="TLM-100 status", version="1.10.0", lifespan=lifespan)


@app.get("/api/status")
async def status() -> Status:
    if not samples:
        raise HTTPException(503, "no data yet")
    return Status(
        uptime_s=round(time.monotonic() - started, 1), period_ms=period_ms, latest=samples[-1]
    )


@app.get("/api/telemetry")
async def telemetry(last: int = Query(5, ge=1, le=600)) -> list[Sample]:
    return list(samples)[-last:]


@app.post("/api/rate")
async def set_rate(rate: Rate) -> Rate:
    global period_ms
    period_ms = rate.period_ms
    return rate
