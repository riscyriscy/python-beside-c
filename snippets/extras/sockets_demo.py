"""Sockets: UDP discovery and a line-based TCP command protocol. Run: python3 sockets_demo.py"""

from __future__ import annotations

import json
import socket
import socketserver
import threading
import time
from typing import Any

# ---------------- UDP: "who is out there?" discovery ----------------


def discovery_responder(sock: socket.socket) -> None:
    """Device side: answer DISCOVER datagrams with an identity record."""
    while True:
        data, addr = sock.recvfrom(1024)
        if data == b"DISCOVER":
            reply = {
                "product": "TLM-100",
                "serial": "TLM100-0007",
                "fw": "1.10.0",
                "tcp_port": TCP_PORT,
            }
            sock.sendto(json.dumps(reply).encode(), addr)


def discover(target: tuple[str, int], timeout: float = 0.5) -> list[dict[str, Any]]:
    """Host side: send one request, collect replies until the timeout expires."""
    found: list[dict[str, Any]] = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)  # every blocking socket call needs a timeout
        # On a real LAN: setsockopt(SOL_SOCKET, SO_BROADCAST, 1), send to ("255.255.255.255", port)
        s.sendto(b"DISCOVER", target)
        try:
            while True:
                data, addr = s.recvfrom(1024)
                try:
                    reply = json.loads(data)
                except ValueError:  # anyone can send here; skip non-JSON
                    continue
                port = reply.get("tcp_port") if isinstance(reply, dict) else None
                if isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535:
                    found.append({**reply, "addr": addr[0]})  # the real source address wins
        except TimeoutError:  # socket.timeout is an alias of TimeoutError since 3.10
            pass
    return found


# ---------------- TCP: a line-based command interface, as many instruments have ----------------


class CommandHandler(socketserver.StreamRequestHandler):
    """One instance per client connection; rfile/wfile are file-like wrappers of the socket."""

    def handle(self) -> None:
        for raw in self.rfile:  # one command per line until the client disconnects
            cmd = raw.strip().decode("ascii", errors="replace")
            if cmd == "SLOW?":
                time.sleep(0.3)  # an instrument that is busy measuring
            reply = {"ID?": "TLM-100,TLM100-0007,1.10.0", "TEMP?": "T=2534", "SLOW?": "T=2534"}.get(
                cmd, f"ERR {cmd}"
            )
            self.wfile.write(reply.encode() + b"\n")


class SocketTransport:
    """Satisfies the Transport protocol from Book 1, Phase 3, so TempSensor can talk over TCP."""

    def __init__(self, host: str, port: int, timeout: float = 2.0) -> None:
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._buffer = b""  # bytes received but not yet returned as a line

    def write(self, data: bytes) -> None:
        self._sock.sendall(data)  # send() may send only part of the buffer; sendall() loops

    def read_line(self) -> bytes:
        """Return one line with its newline, b"" at end of stream, or raise TimeoutError.

        The buffer is ours, so a timeout loses nothing and the next call can continue. The
        file object from makefile() cannot: after one timeout it raises OSError for good.
        """
        while b"\n" not in self._buffer:
            chunk = self._sock.recv(4096)  # raises TimeoutError after the socket timeout
            if not chunk:  # the peer closed the connection
                line, self._buffer = self._buffer, b""
                return line
            self._buffer += chunk
        line, _, self._buffer = self._buffer.partition(b"\n")
        return line + b"\n"

    def close(self) -> None:
        self._sock.close()


udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp.bind(("127.0.0.1", 0))  # port 0: the OS picks a free port
tcp = socketserver.ThreadingTCPServer(("127.0.0.1", 0), CommandHandler)
TCP_PORT = tcp.server_address[1]

threading.Thread(target=discovery_responder, args=(udp,), daemon=True).start()
threading.Thread(target=tcp.serve_forever, daemon=True).start()

devices = discover(udp.getsockname())
print(f"discovered: {devices}")

link = SocketTransport(devices[0]["addr"], devices[0]["tcp_port"])
for command in (b"ID?", b"TEMP?", b"RESET"):
    link.write(command + b"\n")
    print(f"{command.decode():<6} -> {link.read_line().decode().strip()}")
link.close()

# A reply that arrives after the timeout is not lost: the next read_line() collects it
slow = SocketTransport(devices[0]["addr"], devices[0]["tcp_port"], timeout=0.2)
slow.write(b"SLOW?\n")
try:
    slow.read_line()
except TimeoutError:
    print("SLOW?  -> timed out after 0.2 s")
print(f"SLOW?  -> {slow.read_line().decode().strip()} (second read)")
slow.close()
tcp.shutdown()
tcp.server_close()
