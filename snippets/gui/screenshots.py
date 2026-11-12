"""Render the example windows headlessly to PNG (QT_QPA_PLATFORM=offscreen)."""

import subprocess
import sys

from flash_worker import FlashWindow
from PySide6.QtCore import QEventLoop, QObject, Qt, Slot
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from rail_check import RailCheck
from results_table import DATA, ResultsWindow, load
from telemetry_viewer import TelemetryViewer

app = QApplication(sys.argv)

w = RailCheck()
w.resize(420, 320)
w.show()
for serial, rail, volts in [("TLM100-0007", "3V3", 3.31), ("TLM100-0007", "1V8", 1.712)]:
    w.serial.setText(serial)
    w.rail.setCurrentText(rail)
    w.volts.setValue(volts)
    w.check.click()
QTest.qWait(100)
w.grab().save("shot_rail_check.png")

r = ResultsWindow(load(DATA))
r.resize(620, 330)
r.show()
r.view.sortByColumn(5, Qt.SortOrder.AscendingOrder)
QTest.qWait(100)
r.grab().save("shot_results.png")

f = FlashWindow()
f.resize(380, 240)
f.show()


class CancelAt(QObject):
    """Clicks Cancel at 60 %. A QObject slot, so it runs on the GUI thread (a lambda would not)."""

    @Slot(int)
    def on_progress(self, pct: int) -> None:
        if pct >= 60 and f.stop.isEnabled():
            f.stop.click()


loop = QEventLoop()
helper = CancelAt()
f.start.click()
assert f.worker is not None
f.worker.progress.connect(helper.on_progress)
f.worker.finished.connect(loop.quit)
loop.exec()  # a real event loop: QTest.qWait in a polling loop starved the worker thread here
QTest.qWait(100)
f.grab().save("shot_flash.png")

server = subprocess.Popen(
    [sys.executable, "device_server.py", "0"], stdout=subprocess.PIPE, text=True
)
assert server.stdout is not None
port = int(server.stdout.readline().split()[-1])  # "listening on PORT"
v = TelemetryViewer(port=port)
v.resize(900, 460)
v.show()
v.window_s.setCurrentText("10 s")
v.toggle_connection()
# Wait for the second over-temperature peak so the status lamp is lit in the picture
while not (v.latest and v.latest.uptime_ms > 7000 and v.latest.status):
    QTest.qWait(20)
QTest.qWait(150)
v.grab().save("shot_viewer.png")
print(f"viewer: good={v.splitter.stats.good} bad_crc={v.splitter.stats.bad_crc} latest={v.latest}")
v.socket.disconnectFromHost()
server.terminate()
f.close()
