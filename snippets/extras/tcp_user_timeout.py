"""TCP_USER_TIMEOUT: how long a send may stay unacknowledged before the socket fails."""
import errno
import socket
import subprocess
import threading
import time

TCP_USER_TIMEOUT = socket.TCP_USER_TIMEOUT      # Linux only


def nft(rule: str) -> None:
    subprocess.run(["nft", *rule.split()], check=True)


def run(user_timeout_ms: int) -> None:
    listener = socket.create_server(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    peers = []
    threading.Thread(target=lambda: peers.append(listener.accept()), daemon=True).start()
    cli = socket.create_connection(("127.0.0.1", port))
    cli.setsockopt(socket.IPPROTO_TCP, TCP_USER_TIMEOUT, user_timeout_ms)
    cli.sendall(b"hello")                       # acknowledged normally
    time.sleep(0.2)
    nft("add table ip cut")
    nft("add chain ip cut c { type filter hook output priority 0 ; }")
    nft(f"add rule ip cut c tcp dport {port} drop")
    t0 = time.monotonic()
    cli.sendall(b"lost")                        # the link is cut: no ACK will arrive
    cli.settimeout(300)
    try:
        cli.recv(1)                             # blocks until the kernel gives up
    except OSError as e:
        print(f"   user timeout {user_timeout_ms:>5} ms: "
              f"{errno.errorcode[e.errno]} after {time.monotonic() - t0:5.1f} s")
    nft("delete table ip cut")


if __name__ == "__main__":
    run(3000)
    run(10000)
