"""Model/view: a sortable, filterable table over CSV results. Run: python3 results_table.py"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

DATA = Path(__file__).parent.parent / "files" / "data" / "results.csv"
LIMITS = {"v3v3": (3.20, 3.40), "v1v8": (1.75, 1.85)}
COLUMNS = ["serial", "station", "v3v3", "v1v8", "temp_c", "result"]
Index = QModelIndex | QPersistentModelIndex
NO_PARENT = QModelIndex()  # the invalid index: "top level" in a flat table


def load(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows: list[dict[str, Any]] = []
        for r in csv.DictReader(f):
            row: dict[str, Any] = {k: r[k] for k in ("serial", "station")}
            for k in ("v3v3", "v1v8", "temp_c"):
                row[k] = float(r[k]) if r[k] else None
            ok = all(row[k] is not None and lo <= row[k] <= hi for k, (lo, hi) in LIMITS.items())
            row["result"] = "PASS" if ok and (row["temp_c"] or 0) <= 45 else "FAIL"
            rows.append(row)
        return rows


class ResultsModel(QAbstractTableModel):
    """Adapts a list of dicts to Qt's table interface. Views ask; the model answers per role."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        super().__init__()
        self.rows = rows

    def rowCount(self, parent: Index = NO_PARENT) -> int:
        return len(self.rows)

    def columnCount(self, parent: Index = NO_PARENT) -> int:
        return len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section].replace("_", " ").upper()
        return None

    def data(self, index: Index, role: int = 0) -> Any:
        value = self.rows[index.row()][COLUMNS[index.column()]]
        match role:
            case Qt.ItemDataRole.DisplayRole:
                return (
                    "n/a"
                    if value is None
                    else f"{value:.2f}"
                    if isinstance(value, float)
                    else value
                )
            case Qt.ItemDataRole.UserRole:  # raw value: lets the proxy sort numbers numerically
                return -1e9 if value is None else value
            case Qt.ItemDataRole.ForegroundRole if value == "FAIL":
                return QColor("#c62828")
            case Qt.ItemDataRole.TextAlignmentRole if isinstance(value, float) or value is None:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None


class FailFilter(QSortFilterProxyModel):
    """Text filter across all columns, plus an optional 'failures only' switch."""

    failures_only = False

    def filterAcceptsRow(self, source_row: int, source_parent: Index) -> bool:
        model = self.sourceModel()
        if self.failures_only and model.index(source_row, COLUMNS.index("result")).data() != "FAIL":
            return False
        return super().filterAcceptsRow(source_row, source_parent)


class ResultsWindow(QWidget):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        super().__init__()
        self.setWindowTitle("Production results")
        self.model = ResultsModel(rows)
        self.proxy = FailFilter()
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.proxy.setFilterKeyColumn(-1)  # search every column
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.search = QLineEdit(placeholderText="filter, e.g. ST2")
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.fails = QCheckBox("Failures only")
        self.fails.toggled.connect(self.set_failures_only)
        top = QHBoxLayout()
        top.addWidget(self.search)
        top.addWidget(self.fails)

        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)  # click a header to sort
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.view)

    def set_failures_only(self, on: bool) -> None:
        # Qt 6.10+: bracket the change so the proxy re-runs filterAcceptsRow
        # (invalidateRowsFilter() still works but is deprecated)
        self.proxy.beginFilterChange()
        self.proxy.failures_only = on
        self.proxy.endFilterChange(QSortFilterProxyModel.Direction.Rows)


def main() -> int:
    app = QApplication(sys.argv)
    w = ResultsWindow(load(DATA))
    w.resize(620, 340)
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
