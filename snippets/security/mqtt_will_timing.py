"""Time the last will of a node that freezes, as a power loss would, instead of closing its socket.

Run: python3 mqtt_will_timing.py  (needs paho-mqtt 2.x and the mosquitto broker on PATH)

The node runs as a child process. SIGSTOP freezes it: no DISCONNECT, no PINGREQ, and the TCP
connection stays open. The broker publishes the will after about 1.5 times the keepalive.
"""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import time

import paho.mqtt.client as mqtt
from mqtt_telemetry import broker
from paho.mqtt.enums import CallbackAPIVersion

API = CallbackAPIVersion.VERSION2
TOPIC = "tlm100/TLM100-0009/status"
KEEPALIVE_S = 4


def node(port: int) -> None:
    """Child process: connect with a will, then idle until frozen or killed."""
    c = mqtt.Client(API, client_id="TLM100-0009")
    c.will_set(TOPIC, "offline", qos=1)
    c.connect("127.0.0.1", port, keepalive=KEEPALIVE_S)
    c.loop_start()
    time.sleep(60)


def main() -> None:
    with broker() as port:
        inbox: queue.Queue[tuple[str, float]] = queue.Queue()

        def on_message(c: mqtt.Client, ud: object, m: mqtt.MQTTMessage) -> None:
            inbox.put((m.payload.decode(), time.monotonic()))

        sub = mqtt.Client(API, client_id="station")
        sub.on_message = on_message
        sub.connect("127.0.0.1", port)
        sub.subscribe(TOPIC, qos=1)
        sub.loop_start()
        child = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "node", str(port)]
        )
        time.sleep(1.0)  # let the node connect
        os.kill(child.pid, signal.SIGSTOP)
        frozen_at = time.monotonic()
        payload, seen_at = inbox.get(timeout=30)
        print(
            f"keepalive {KEEPALIVE_S} s: will '{payload}' arrived {seen_at - frozen_at:.1f} s after SIGSTOP"
        )
        os.kill(child.pid, signal.SIGKILL)
        child.wait()
        sub.disconnect()
        sub.loop_stop()


if __name__ == "__main__":
    if sys.argv[1:2] == ["node"]:
        node(int(sys.argv[2]))
    else:
        main()
