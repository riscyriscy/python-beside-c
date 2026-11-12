"""Live telemetry viewer: QTcpSocket + frametool + pyqtgraph. Run: python3 telemetry_viewer.py"""

from __future__ import annotations

import sys
import time
from collections import deque

import pyqtgraph as pg
from frametool.link import FrameSplitter
from frametool.protocol import MessageType, Telemetry, TelemetryStatus
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

OVER_TEMP_C = 34.0


class StatusLamp(QLabel):
    """A round 'LED' made from a styled label."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.set_on(False)

    def set_on(self, on: bool, colour: str = "#c62828") -> None:
        bg = colour if on else "#cfd8dc"
        self.setStyleSheet(f"background: {bg}; color: white; border-radius: 9px; padding: 2px 8px;")


class TelemetryViewer(QMainWindow):
    def __init__(self, host: str = "127.0.0.1", port: int = 5555) -> None:
        super().__init__()
        self.setWindowTitle("TLM-100 telemetry")
        self.splitter = FrameSplitter()
        self.t: deque[float] = deque(maxlen=600)  # last 60 s at 10 Hz
        self.temp: deque[float] = deque(maxlen=600)
        self.latest: Telemetry | None = None

        # Qt's own socket: asynchronous and driven by the event loop, so no threads or locks
        self.socket = QTcpSocket(self)
        self.socket.readyRead.connect(self.on_ready_read)
        self.socket.connected.connect(lambda: self.set_link_state("connected"))
        self.socket.disconnected.connect(lambda: self.set_link_state("disconnected"))
        self.socket.errorOccurred.connect(self.on_socket_error)

        # --- connection bar ---
        self.host = QLineEdit(host)
        self.port = QSpinBox(minimum=1, maximum=65535, value=port)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        bar = QHBoxLayout()
        for w in (QLabel("Host"), self.host, QLabel("Port"), self.port, self.connect_btn):
            bar.addWidget(w)
        bar.addStretch()

        # --- plot (pyqtgraph: fast, interactive, made for live data) ---
        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget(background="w")
        self.plot.setLabel("left", "Temperature", units="°C")
        self.plot.setLabel("bottom", "Device uptime", units="s")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.curve = self.plot.plot(pen=pg.mkPen("#001c71", width=2))
        limit_pen = pg.mkPen("#ee7623", width=2, style=Qt.PenStyle.DashLine)
        self.plot.addItem(pg.InfiniteLine(OVER_TEMP_C, angle=0, pen=limit_pen))  # alarm threshold
        self.window_s = QComboBox()
        self.window_s.addItems(["10 s", "30 s", "60 s"])
        self.window_s.setCurrentText("30 s")

        # --- side panel ---
        self.temp_label = QLabel("--.- °C")
        self.temp_label.setStyleSheet("font-size: 28pt; font-weight: bold;")
        self.supply_label = QLabel("supply --")
        self.lamps = {
            flag: StatusLamp(str(flag.name).replace("_", " ").lower())
            for flag in (
                TelemetryStatus.OVER_TEMP,
                TelemetryStatus.UNDER_VOLTAGE,
                TelemetryStatus.SENSOR_FAULT,
            )
        }
        stats_box = QGroupBox("Link")
        stats = QFormLayout(stats_box)
        self.good, self.bad_crc, self.malformed, self.rate = (QLabel("0") for _ in range(4))
        stats.addRow("Good frames", self.good)
        stats.addRow("Bad CRC", self.bad_crc)
        stats.addRow("Malformed", self.malformed)
        stats.addRow("Rate", self.rate)
        side = QVBoxLayout()
        side.addWidget(self.temp_label)
        side.addWidget(self.supply_label)
        for lamp in self.lamps.values():
            side.addWidget(lamp)
        side.addWidget(stats_box)
        side.addWidget(QLabel("Plot window"))
        side.addWidget(self.window_s)
        side.addStretch()

        body = QHBoxLayout()
        body.addWidget(self.plot, stretch=1)
        body.addLayout(side)
        root = QVBoxLayout()
        root.addLayout(bar)
        root.addLayout(body)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)
        self.set_link_state("disconnected")

        # Redraw at a fixed 10 Hz, independent of how fast data arrives
        self._rate_mark = (time.monotonic(), 0)
        self.redraw = QTimer(self, interval=100)
        self.redraw.timeout.connect(self.refresh)
        self.redraw.start()

    @Slot()
    def toggle_connection(self) -> None:
        if self.socket.state() == QAbstractSocket.SocketState.UnconnectedState:
            self.reset_stream()
            self.set_link_state("connecting")
            self.socket.connectToHost(self.host.text(), self.port.value())
        else:
            self.socket.disconnectFromHost()

    def reset_stream(self) -> None:
        """A new connection starts a new stream: no half frame, no old points, no old counts."""
        self.splitter = FrameSplitter()  # drops a partial frame and zeroes the statistics
        self.t.clear()  # device uptime starts again at 0, so old points would run backwards
        self.temp.clear()
        self.latest = None
        self._rate_mark = (time.monotonic(), 0)

    def set_link_state(self, state: str) -> None:
        self.statusBar().showMessage(f"{state}  {self.host.text()}:{self.port.value()}")
        self.connect_btn.setText(
            "Disconnect" if state in ("connected", "connecting") else "Connect"
        )

    @Slot(QAbstractSocket.SocketError)
    def on_socket_error(self, _err: QAbstractSocket.SocketError) -> None:
        self.statusBar().showMessage(f"error: {self.socket.errorString()}")
        self.connect_btn.setText("Connect")

    @Slot()
    def on_ready_read(self) -> None:
        for frame in self.splitter.feed(self.socket.readAll().data()):  # QByteArray -> bytes
            if frame.type == MessageType.TELEMETRY:
                t = Telemetry.from_bytes(frame.payload)
                self.latest = t
                self.t.append(t.uptime_ms / 1000)
                self.temp.append(t.temperature_c)

    @Slot()
    def refresh(self) -> None:
        if self.t:
            self.curve.setData(list(self.t), list(self.temp))
            span = int(self.window_s.currentText().split()[0])
            self.plot.setXRange(max(0.0, self.t[-1] - span), max(span, self.t[-1]), padding=0)
        if self.latest is not None:
            self.temp_label.setText(f"{self.latest.temperature_c:5.1f} °C")
            self.supply_label.setText(f"supply {self.latest.supply_v:.3f} V")
            for flag, lamp in self.lamps.items():
                lamp.set_on(flag in self.latest.status)
        s = self.splitter.stats
        self.good.setText(str(s.good))
        self.bad_crc.setText(str(s.bad_crc))
        self.malformed.setText(str(s.malformed))
        now, count = time.monotonic(), s.good + s.bad_crc
        t0, c0 = self._rate_mark
        if now - t0 >= 1.0:
            self.rate.setText(f"{(count - c0) / (now - t0):.1f} frames/s")
            self._rate_mark = (now, count)


def main() -> int:
    app = QApplication(sys.argv)
    viewer = TelemetryViewer()
    viewer.resize(900, 480)
    viewer.show()
    viewer.toggle_connection()  # connect straight away; the button toggles afterwards
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
