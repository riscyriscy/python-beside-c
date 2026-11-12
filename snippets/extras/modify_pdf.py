"""Modify PDFs with pypdf and read them back with pdfplumber. Run after make_report_pdf.py."""

from __future__ import annotations

import io
from pathlib import Path

import pdfplumber
from pypdf import PdfReader, PdfWriter
from pypdf.errors import FileNotDecryptedError
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = Path("out")


def make_stamp(text: str) -> PdfReader:
    """Draw a one-page watermark in memory with ReportLab's low-level canvas."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 60)
    c.setFillColorRGB(0.8, 0.1, 0.1, alpha=0.18)  # translucent red
    c.translate(letter[0] / 2, letter[1] / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, text)
    c.save()
    buf.seek(0)
    return PdfReader(buf)


def make_cover() -> PdfReader:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 28)
    c.drawString(72, 650, "TLM-100 Device History Record")
    c.setFont("Helvetica", 14)
    c.drawString(72, 615, "Lot 2026-10-12, production test results attached")
    c.save()
    buf.seek(0)
    return PdfReader(buf)


report = PdfReader(OUT / "report.pdf")
print(
    f"input: {len(report.pages)} page(s), title {report.metadata.title!r}"
    if report.metadata
    else "input has no metadata"
)

# 1. Stamp every page and put a cover in front
stamp = make_stamp("CONTROLLED COPY").pages[0]
writer = PdfWriter()
writer.append(make_cover())
for page in report.pages:
    added = writer.add_page(page)  # pypdf 7 merges only into a page that a writer owns
    added.merge_page(stamp)  # draws the stamp over the existing content
writer.add_metadata(
    {
        "/Title": "TLM-100 DHR, lot 2026-10-12",
        "/Author": "Production test",
        "/Subject": "Test results",
    }
)
writer.add_outline_item("Cover", 0)  # bookmarks for the PDF viewer's sidebar
writer.add_outline_item("Test results", 1)
with (OUT / "dhr.pdf").open("wb") as f:
    writer.write(f)

# 2. An encrypted copy: AES-256 needs the 'cryptography' package (pypdf[crypto])
enc = PdfWriter(clone_from=OUT / "dhr.pdf")
enc.encrypt(user_password="lot1012", owner_password="qa-only", algorithm="AES-256")
with (OUT / "dhr-encrypted.pdf").open("wb") as f:
    enc.write(f)

# 3. Split: extract the results page on its own, rotated to landscape for a wall display
single = PdfWriter()
single.add_page(PdfReader(OUT / "dhr.pdf").pages[1])
single.pages[0].rotate(90)
with (OUT / "results-only.pdf").open("wb") as f:
    single.write(f)

# 4. Read everything back
for name in ("dhr.pdf", "dhr-encrypted.pdf", "results-only.pdf"):
    r = PdfReader(OUT / name)
    if r.is_encrypted:
        r.decrypt("lot1012")
    title = r.metadata.title if r.metadata else None
    print(f"{name:<20} pages={len(r.pages)} encrypted={r.is_encrypted!s:<5} title={title!r}")

try:
    PdfReader(OUT / "dhr-encrypted.pdf").pages[0].extract_text()
except FileNotDecryptedError as e:  # reading an encrypted file without the password
    print(f"no password: {type(e).__name__}")

# 5. pdfplumber: pull the results table back out as rows
with pdfplumber.open(OUT / "dhr.pdf") as pdf:
    rows = pdf.pages[1].extract_table() or []
fails = [r[0] for r in rows[1:] if r[-1] == "FAIL"]
print(f"table read back: {len(rows) - 1} rows, header {rows[0]}")
print(f"failed serials from the PDF itself: {fails}")
