"""QThread + worker object + signals: long work off the GUI thread. Run: python3 flash_worker.py"""

from __future__ import annotations

import sys
import threading
import time
import zlib

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class FlashWorker(QObject):
    """Stands in for a blocking bootloader download (pyserial, a vendor DLL, ...)."""

    progress = Signal(int)  # percent
    message = Signal(str)
    finished = Signal(bool)  # True on success

    def __init__(self, image: bytes, block: int = 4096) -> None:
        super().__init__()
        self.image, self.block = image, block
        self._cancel = threading.Event()  # set from the GUI thread, read from the worker

    def cancel(self) -> None:
        self._cancel.set()

    @Slot()
    def run(self) -> None:  # runs in the worker thread: never touch widgets here
        blocks = range(0, len(self.image), self.block)
        crc = 0
        for n, offset in enumerate(blocks, start=1):
            if self._cancel.is_set():
                self.message.emit(f"cancelled at {offset:#x}")
                self.finished.emit(False)
                return
            chunk = self.image[offset : offset + self.block]
            time.sleep(0.004)  # the blocking "write block and wait for ACK"
            crc = zlib.crc32(chunk, crc)
            self.progress.emit(n * 100 // len(blocks))  # signals cross threads safely
        self.message.emit(f"wrote {len(self.image)} bytes, crc32 {crc:#010x}")
        self.finished.emit(True)


class FlashWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Firmware update")
        self.bar = QProgressBar()
        self.log = QPlainTextEdit(readOnly=True)
        self.start = QPushButton("Start")
        self.stop = QPushButton("Cancel")
        self.stop.setEnabled(False)
        buttons = QHBoxLayout()
        buttons.addWidget(self.start)
        buttons.addWidget(self.stop)
        layout = QVBoxLayout(self)
        layout.addWidget(self.bar)
        layout.addLayout(buttons)
        layout.addWidget(self.log)
        self.start.clicked.connect(self.begin)
        # A slot of this window runs at once on the GUI thread and may call worker.cancel(): it only
        # sets a threading.Event. Queuing cancel() on the worker would wait for its blocked loop.
        self.stop.clicked.connect(self.cancel)
        # Named worker_thread, not thread: self.thread would hide QObject.thread()
        self.worker_thread: QThread | None = None  # None whenever no download is running
        self.worker: FlashWorker | None = None
        self._closing = False

    @Slot()
    def begin(self) -> None:
        thread = QThread(self)
        worker = FlashWorker(bytes(range(256)) * 1024)  # 256 KiB image
        worker.moveToThread(thread)  # its slots now run in that thread
        thread.started.connect(worker.run)
        worker.progress.connect(self.bar.setValue)  # delivered on the GUI thread
        worker.message.connect(self.log.appendPlainText)
        worker.finished.connect(self.done)
        worker.finished.connect(thread.quit)
        # One worker and one thread per click. Qt deletes the thread, whose parent is the window.
        # The worker has no parent: Python deletes it in thread_ended(), on the GUI thread, after
        # the thread has left its event loop. worker.deleteLater() ran in the worker thread and
        # raced with that: it crashed about 1 run in 600.
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.thread_ended)
        self.worker_thread, self.worker = thread, worker
        self.start.setEnabled(False)
        self.stop.setEnabled(True)
        self.log.appendPlainText("flashing ...")
        thread.start()

    @Slot()
    def cancel(self) -> None:
        if self.worker is not None:
            self.worker.cancel()

    @Slot(bool)
    def done(self, ok: bool) -> None:
        self.log.appendPlainText("SUCCESS" if ok else "FAILED")
        self.stop.setEnabled(False)

    @Slot()
    def thread_ended(self) -> None:
        """The thread has finished: dropping the last reference deletes the worker here."""
        self.worker_thread = self.worker = None
        self.start.setEnabled(True)  # only now: a new click would replace the running pair
        if self._closing:
            self.close()  # the close that closeEvent put off

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker_thread is None:
            event.accept()
            return
        # Destroying a running QThread aborts the process, and a wait() with a time limit can
        # still expire first. Cancel, refuse to close, and close from thread_ended() instead.
        self._closing = True
        self.setEnabled(False)
        self.cancel()
        event.ignore()


def main() -> int:
    app = QApplication(sys.argv)
    w = FlashWindow()
    w.resize(380, 260)
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
