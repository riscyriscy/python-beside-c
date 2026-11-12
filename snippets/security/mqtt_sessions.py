"""MQTT: what a station misses while it is away, QoS downgrade, retained messages and a broker restart.

Run: python3 mqtt_sessions.py  (needs paho-mqtt 2.x and the mosquitto broker on PATH)
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

TOPIC = "tlm100/TLM100-0007/temp"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def start(port: int, conf: Path) -> subprocess.Popen[bytes]:
    proc = subprocess.Popen(
        [shutil.which("mosquitto") or "mosquitto", "-c", str(conf)], stderr=subprocess.DEVNULL
    )
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            return proc
        except OSError:
            time.sleep(0.1)
    raise TimeoutError("broker did not start")


def client(
    cid: str, port: int, *, clean: bool, got: list[tuple[str, int, bool]] | None = None
) -> mqtt.Client:
    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=cid, clean_session=clean)
    if got is not None:
        c.on_message = lambda cl, ud, m: got.append((m.payload.decode(), m.qos, bool(m.retain)))
    c.connect("127.0.0.1", port, keepalive=30)
    c.loop_start()
    return c


def stop(c: mqtt.Client) -> None:
    c.disconnect()
    c.loop_stop()


def station_away(port: int, clean: bool) -> list[tuple[str, int, bool]]:
    """Subscribe, go away, let a node publish three readings, come back."""
    first: list[tuple[str, int, bool]] = []
    s = client("station-1", port, clean=clean, got=first)
    s.subscribe(TOPIC, qos=1)
    time.sleep(0.3)
    stop(s)
    node = client(f"node-{clean}", port, clean=True)
    for i in range(3):
        node.publish(TOPIC, f"T={20 + i}", qos=1).wait_for_publish(3)
    stop(node)
    back: list[tuple[str, int, bool]] = []
    s = client("station-1", port, clean=clean, got=back)
    time.sleep(0.5)
    stop(s)
    return back


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        Path(d).chmod(0o777)  # mosquitto started as root drops to its own user and must write here
        port = free_port()
        conf = Path(d, "m.conf")
        conf.write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\n")
        proc = start(port, conf)
        print("clean session, 3 readings while away:", len(station_away(port, True)), "received")
        print("persistent session, same:", len(station_away(port, False)), "received")
        # QoS is the lower of publish and subscribe
        got: list[tuple[str, int, bool]] = []
        s = client("q-sub", port, clean=True, got=got)
        s.subscribe("qos/test", qos=0)
        time.sleep(0.3)
        p = client("q-pub", port, clean=True)
        p.publish("qos/test", "x", qos=2).wait_for_publish(3)
        time.sleep(0.3)
        print("published QoS 2, subscribed QoS 0, delivered QoS:", got[0][1])
        stop(s)
        stop(p)
        # retained message and a broker restart, without and with persistence
        for persist in (False, True):
            port = free_port()
            conf.write_text(
                f"listener {port} 127.0.0.1\nallow_anonymous true\n"
                + (
                    f"persistence true\npersistence_location {d}/\npersistence_file m{persist}.db\nautosave_interval 1\n"
                    if persist
                    else ""
                )
            )
            proc.terminate()
            proc.wait(5)
            proc = start(port, conf)
            p = client("r-pub", port, clean=True)
            p.publish("tlm100/state", "ARMED", qos=1, retain=True).wait_for_publish(3)
            stop(p)
            proc.terminate()
            proc.wait(5)  # SIGTERM: mosquitto writes the database on a clean exit
            proc = start(port, conf)
            late: list[tuple[str, int, bool]] = []
            s = client("r-sub", port, clean=True, got=late)
            s.subscribe("tlm100/state", qos=1)
            time.sleep(0.5)
            stop(s)
            print(
                f"retained message after a broker restart, persistence {'on' if persist else 'off'}:",
                late,
            )
        proc.terminate()
        proc.wait(5)


if __name__ == "__main__":
    main()
