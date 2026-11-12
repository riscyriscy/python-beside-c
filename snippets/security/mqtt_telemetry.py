"""MQTT telemetry with paho-mqtt 2.x: QoS 1, retained last will, clean stop.

Run: python3 mqtt_telemetry.py  (needs paho-mqtt 2.x and the mosquitto broker on PATH)
"""

from __future__ import annotations

import queue
import shutil
import socket
import subprocess
import textwrap
import threading
import time
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.reasoncodes import ReasonCode

API = CallbackAPIVersion.VERSION2


@contextmanager
def broker() -> Iterator[int]:
    """Run mosquitto on a free port for the duration of the block."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = int(s.getsockname()[1])
    exe = shutil.which("mosquitto") or "mosquitto"
    proc = subprocess.Popen([exe, "-p", str(port)], stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):  # wait until the port accepts connections
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        yield port
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def device(serial: str, port: int) -> mqtt.Client:
    """A telemetry node: its last will says offline if the connection just dies."""
    c = mqtt.Client(API, client_id=serial)
    c.will_set(f"tlm100/{serial}/status", "offline", qos=1, retain=True)
    c.connect("127.0.0.1", port, keepalive=30)
    c.loop_start()  # network thread; callbacks run on it
    return c


def confirmed(info: mqtt.MQTTMessageInfo) -> None:
    """Wait for the QoS 1 ack; wait_for_publish() returns silently on a timeout."""
    info.wait_for_publish(5)
    if not info.is_published():
        raise TimeoutError("the broker did not acknowledge the message in 5 s")


def subscriber(port: int, inbox: queue.Queue[str]) -> mqtt.Client:
    def on_connect(
        c: mqtt.Client, ud: Any, flags: Any, rc: ReasonCode, props: Any
    ) -> None:
        c.subscribe(
            [("tlm100/+/temp", 1), ("tlm100/+/status", 1)]
        )  # on every (re)connect

    def on_message(c: mqtt.Client, ud: Any, m: mqtt.MQTTMessage) -> None:
        kind = "retained" if m.retain else "live"
        inbox.put(f"{m.topic} {m.payload.decode()} (qos {m.qos}, {kind})")

    ready = threading.Event()
    c = mqtt.Client(API, client_id="station")
    c.on_connect, c.on_message = on_connect, on_message
    c.on_subscribe = lambda *args: ready.set()  # SUBACK received
    c.connect("127.0.0.1", port)
    c.loop_start()
    if not ready.wait(5):
        raise TimeoutError("the broker did not confirm the subscriptions in 5 s")
    return c


def drain(inbox: queue.Queue[str], n: int) -> None:
    for _ in range(n):
        print("  ", inbox.get(timeout=5))


def main() -> None:
    try:
        mqtt.Client("TLM100-0007")  # type: ignore[arg-type]  # the 1.x call style
    except (ValueError, TypeError) as e:  # 2.1.0 raises ValueError, 2.2.0 raises TypeError
        print(textwrap.fill(f"1.x style: {e}", 84, subsequent_indent="  "))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        mqtt.Client()  # 2.1 still accepts this and uses callback API version 1
    w = caught[0]
    print(textwrap.fill(f"no version: {w.category.__name__}: {w.message}", 84))
    with broker() as port:
        inbox: queue.Queue[str] = queue.Queue()
        sub = subscriber(port, inbox)
        d7 = device("TLM100-0007", port)
        d7.publish("tlm100/TLM100-0007/status", "online", qos=1, retain=True)
        for t in (21.5, 21.6, 21.8):
            confirmed(d7.publish("tlm100/TLM100-0007/temp", f"{t}", qos=1))
        confirmed(d7.publish("tlm100/TLM100-0007/status", "stopped", 1, retain=True))
        d7.disconnect()  # clean stop: the broker does not send the last will
        d7.loop_stop()
        print("station receives from TLM100-0007:")
        drain(inbox, 5)
        d8 = device("TLM100-0008", port)
        d8.publish("tlm100/TLM100-0008/status", "online", qos=1, retain=True)
        print("station receives from TLM100-0008:")
        drain(inbox, 1)
        sock = d8.socket()
        if sock:
            sock.close()  # a crash: no DISCONNECT; the broker sees the closed socket
        print("station receives after TLM100-0008 dies:")
        drain(inbox, 1)
        d8.loop_stop()
        late: queue.Queue[str] = queue.Queue()
        sub2 = subscriber(port, late)
        print("a late subscriber is given the retained state:")
        drain(late, 2)
        for c in (sub, sub2):
            c.disconnect()
            c.loop_stop()


if __name__ == "__main__":
    main()
