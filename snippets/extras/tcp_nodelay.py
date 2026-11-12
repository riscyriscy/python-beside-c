"""Write-write-read over loopback, with and without TCP_NODELAY."""
import socket
import statistics
import threading
import time

HEADER = b"H" * 4      # small header, sent first
BODY = b"B" * 20       # small body, sent second
ROUNDS = 20


def server(listener: socket.socket) -> None:
    conn, _ = listener.accept()
    with conn:
        while True:
            data = b""
            while len(data) < len(HEADER) + len(BODY):
                chunk = conn.recv(64)
                if not chunk:
                    return
                data += chunk
            conn.sendall(b"K")


def run(nodelay: bool) -> list[float]:
    listener = socket.create_server(("127.0.0.1", 0))
    threading.Thread(target=server, args=(listener,), daemon=True).start()
    cli = socket.create_connection(listener.getsockname())
    cli.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1 if nodelay else 0)
    times = []
    for _ in range(ROUNDS):
        t0 = time.perf_counter()
        cli.sendall(HEADER)
        cli.sendall(BODY)
        cli.recv(1)
        times.append((time.perf_counter() - t0) * 1000)
    cli.close()
    listener.close()
    return times


for label, flag in (("Nagle on (default)", False), ("TCP_NODELAY set", True)):
    t = run(flag)
    print(f"{label:<20} median {statistics.median(t):6.2f} ms   "
          f"max {max(t):6.2f} ms   min {min(t):6.2f} ms")
