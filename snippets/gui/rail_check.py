"""Qt basics: widgets, layouts, signals and slots, validation. Run: python3 rail_check.py"""

from __future__ import annotations

import sys

from PySide6.QtCore import QRegularExpression, Signal, Slot
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

LIMITS = {"3V3": (3.20, 3.40), "1V8": (1.75, 1.85), "0V9": (0.87, 0.93)}


class RailCheck(QWidget):
    """A small form: enter a serial number and a measured rail voltage, get PASS/FAIL."""

    checked = Signal(str, str, bool)  # custom signal: serial, rail, passed

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Rail check")

        self.serial = QLineEdit(placeholderText="TLM100-0001")
        self.serial.setValidator(QRegularExpressionValidator(QRegularExpression(r"TLM100-\d{4}")))
        self.rail = QComboBox()
        self.rail.addItems(list(LIMITS))  # the dict keys, as a list
        self.volts = QDoubleSpinBox(
            decimals=3, minimum=0.0, maximum=5.0, singleStep=0.01, suffix=" V"
        )
        self.check = QPushButton("Check")
        self.check.setEnabled(False)  # until the serial number is valid
        self.result = QLabel("enter a serial number")
        self.history = QListWidget()

        form = QFormLayout()  # label/field pairs, aligned for you
        form.addRow("Serial", self.serial)
        form.addRow("Rail", self.rail)
        form.addRow("Measured", self.volts)
        layout = QVBoxLayout(self)  # passing self installs the layout on this widget
        layout.addLayout(form)
        layout.addWidget(self.check)
        layout.addWidget(self.result)
        layout.addWidget(self.history)

        # Signals and slots: Qt's callbacks. Connect an event to any callable.
        self.serial.textChanged.connect(self.update_enabled)
        self.check.clicked.connect(self.on_check)
        self.serial.returnPressed.connect(self.check.click)

    @Slot()
    def update_enabled(self) -> None:
        self.check.setEnabled(self.serial.hasAcceptableInput())  # validator decides

    @Slot()
    def on_check(self) -> None:
        rail, v = self.rail.currentText(), self.volts.value()
        lo, hi = LIMITS[rail]
        passed = lo <= v <= hi
        verdict = "PASS" if passed else f"FAIL (limits {lo:.2f}-{hi:.2f} V)"
        self.result.setText(f"{self.serial.text()} {rail} = {v:.3f} V: {verdict}")
        self.result.setStyleSheet(f"font-weight: bold; color: {'#2e7d32' if passed else '#c62828'}")
        self.history.insertItem(0, self.result.text())  # newest first
        self.checked.emit(self.serial.text(), rail, passed)


def main() -> int:
    app = QApplication(sys.argv)
    window = RailCheck()
    window.resize(420, 320)
    window.show()
    return app.exec()  # the event loop: runs until the last window closes


if __name__ == "__main__":
    sys.exit(main())
