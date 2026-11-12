"""pytest-qt tests: drive widgets like a user, without a screen. Run: pytest -q test_gui.py"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from flash_worker import FlashWindow
from PySide6.QtCore import Qt
from PySide6.QtNetwork import QAbstractSocket
from pytestqt.qtbot import QtBot
from rail_check import RailCheck
from results_table import DATA, ResultsWindow, load
from telemetry_viewer import TelemetryViewer


def test_check_button_needs_a_valid_serial(qtbot: QtBot) -> None:
    w = RailCheck()
    qtbot.addWidget(w)  # closed and cleaned up after the test
    qtbot.keyClicks(w.serial, "TLM100-12")
    assert not w.check.isEnabled()
    qtbot.keyClicks(w.serial, "34")
    assert w.check.isEnabled()


def test_out_of_limit_rail_fails_and_emits_signal(qtbot: QtBot) -> None:
    w = RailCheck()
    qtbot.addWidget(w)
    qtbot.keyClicks(w.serial, "TLM100-0042")
    w.rail.setCurrentText("1V8")
    w.volts.setValue(1.70)
    with qtbot.waitSignal(w.checked, timeout=1000) as blocker:
        qtbot.mouseClick(w.check, Qt.MouseButton.LeftButton)
    assert blocker.args == ["TLM100-0042", "1V8", False]
    assert "FAIL" in w.result.text()


def test_failures_only_filter(qtbot: QtBot) -> None:
    w = ResultsWindow(load(DATA))
    qtbot.addWidget(w)
    assert w.proxy.rowCount() == 8
    w.fails.setChecked(True)
    assert w.proxy.rowCount() == 4
    w.search.setText("ST1")
    assert w.proxy.rowCount() == 2


def test_flash_worker_completes_in_background(qtbot: QtBot) -> None:
    w = FlashWindow()
    qtbot.addWidget(w)
    w.start.click()
    assert w.worker is not None
    with qtbot.waitSignal(w.worker.finished, timeout=5000) as blocker:
        pass
    assert blocker.args == [True] and w.bar.value() == 100
    qtbot.waitUntil(lambda: w.worker_thread is None, timeout=2000)  # thread ended, objects deleted
    assert w.start.isEnabled()


def test_cancel_stops_the_worker(qtbot: QtBot) -> None:
    w = FlashWindow()
    qtbot.addWidget(w)
    w.start.click()
    assert w.worker is not None
    with qtbot.waitSignal(w.worker.finished, timeout=5000) as blocker:
        w.stop.click()  # the flag is set before the worker reaches its first block
    assert blocker.args == [False] and w.bar.value() < 100
    qtbot.waitUntil(lambda: w.worker_thread is None, timeout=2000)


def test_close_waits_for_the_worker_instead_of_destroying_it(qtbot: QtBot) -> None:
    w = FlashWindow()
    qtbot.addWidget(w)
    w.start.click()
    assert not w.close()  # refused while the thread runs: closeEvent cancelled and ignored it
    qtbot.waitUntil(lambda: w.worker_thread is None, timeout=5000)
    assert w.close()  # thread_ended() had already closed the window; a second close is accepted


def test_a_second_run_after_the_first(qtbot: QtBot) -> None:
    w = FlashWindow()
    qtbot.addWidget(w)
    for _ in range(2):
        w.start.click()
        qtbot.waitUntil(lambda: w.worker_thread is None, timeout=5000)
    assert w.log.toPlainText().count("SUCCESS") == 2


@pytest.fixture
def device() -> Iterator[int]:
    """Start the simulated device on a free port and wait until it says it is listening."""
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("device_server.py")), "0"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:  # the clean-up must also run when the wait below fails or is cut short by a timeout
        assert proc.stdout is not None
        line = proc.stdout.readline()  # "listening on PORT"; empty if the server died on start-up
        if not line.startswith("listening on "):
            raise RuntimeError(f"device server did not start: {line!r}")
        yield int(line.split()[-1])
    finally:
        proc.kill()
        proc.wait()
        if proc.stdout is not None:
            proc.stdout.close()


def test_viewer_receives_live_telemetry(qtbot: QtBot, device: int) -> None:
    v = TelemetryViewer(port=device)
    qtbot.addWidget(v)
    v.toggle_connection()
    qtbot.waitUntil(lambda: v.splitter.stats.good >= 10, timeout=5000)
    assert v.latest is not None and 15 < v.latest.temperature_c < 35
    qtbot.waitUntil(lambda: v.splitter.stats.bad_crc >= 1, timeout=3000)  # every 7th is corrupted


def test_reconnect_starts_a_clean_stream(qtbot: QtBot, device: int) -> None:
    v = TelemetryViewer(port=device)
    qtbot.addWidget(v)
    v.toggle_connection()
    qtbot.waitUntil(lambda: v.splitter.stats.good >= 5, timeout=5000)
    v.toggle_connection()  # disconnect
    qtbot.waitUntil(
        lambda: v.socket.state() == QAbstractSocket.SocketState.UnconnectedState, timeout=3000
    )
    v.splitter.feed(b"\xa5\x01")  # leave half a frame behind, as a dropped link would
    v.toggle_connection()  # reconnect: nothing from the old stream may survive
    assert len(v.t) == 0 and v.splitter.stats.good == 0 and v.latest is None
    qtbot.waitUntil(lambda: v.splitter.stats.good >= 5, timeout=5000)
    assert v.splitter.stats.malformed == 0 and list(v.t) == sorted(v.t)
