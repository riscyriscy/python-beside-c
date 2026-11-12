"""Serve simulated frametool telemetry on TCP for the GUI examples. Run: python3 device_server.py 5555 (port 0 picks a free one)"""

import asyncio
import contextlib
import sys

from frametool import device


async def main(port: int) -> None:
    async def client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        with contextlib.suppress(ConnectionError):
            await device.run(writer)

    server = await asyncio.start_server(client, "127.0.0.1", port)  # port 0: the system picks one
    print(f"listening on {server.sockets[0].getsockname()[1]}", flush=True)  # tests wait for this
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 5555))
