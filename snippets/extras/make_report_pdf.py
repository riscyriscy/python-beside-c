"""Create a production-test report PDF with ReportLab. Run: python3 make_report_pdf.py"""

from __future__ import annotations

import csv
import tomllib
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DATA = Path(__file__).parent.parent / "files" / "data"
OUT = Path("out")


def verdict(row: dict[str, str], limits: dict[str, Any]) -> str:
    """PASS only when every value is present and inside the limits of data/limits.toml."""
    for rail, lim in limits["rails"].items():
        if not row[rail].strip() or not lim["min"] <= float(row[rail]) <= lim["max"]:
            return "FAIL"
    if not row["temp_c"].strip():  # not measured: a failure, as in the Book 1, Phase 3 report
        return "FAIL"
    lo, hi = limits["temperature"]["min_c"], limits["temperature"]["max_c"]
    return "PASS" if lo <= float(row["temp_c"]) <= hi else "FAIL"  # NaN fails


def build(path: Path) -> None:
    with (DATA / "limits.toml").open("rb") as toml_file:
        limits = tomllib.load(toml_file)
    with (DATA / "results.csv").open(newline="", encoding="utf-8-sig") as f:  # -sig: Excel BOM
        rows = list(csv.DictReader(f))

    styles = getSampleStyleSheet()
    story = [  # "platypus": a list of flowables that ReportLab lays out onto pages
        Paragraph("TLM-100 production test report", styles["Title"]),
        Paragraph(
            f"{len(rows)} units tested on stations "
            f"{', '.join(sorted({r['station'] for r in rows}))}.",
            styles["Normal"],
        ),
        Spacer(1, 0.2 * inch),
    ]
    table_data = [["Serial", "Station", "3V3 (V)", "1V8 (V)", "Temp (C)", "Result"]]
    table_data += [
        [
            r["serial"],
            r["station"],
            r["v3v3"],
            r["v1v8"] or "n/a",
            r["temp_c"] or "n/a",
            verdict(r, limits),
        ]
        for r in rows
    ]
    table = Table(table_data, repeatRows=1, hAlign="LEFT")
    style: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#001c71")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (2, 1), (4, -1), "RIGHT"),
    ]
    for i, row in enumerate(table_data[1:], start=1):  # colour each verdict cell
        colour = colors.HexColor("#c62828") if row[-1] == "FAIL" else colors.HexColor("#2e7d32")
        style.append(("TEXTCOLOR", (5, i), (5, i), colour))
    table.setStyle(TableStyle(style))
    story.append(table)

    doc = SimpleDocTemplate(  # invariant=1: fixed dates and ids, so equal input gives equal bytes
        str(path),
        pagesize=letter,
        title="TLM-100 test report",
        author="Production test",
        invariant=1,
    )
    doc.build(story)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    build(OUT / "report.pdf")
    print(f"wrote {OUT / 'report.pdf'} ({(OUT / 'report.pdf').stat().st_size} bytes)")
