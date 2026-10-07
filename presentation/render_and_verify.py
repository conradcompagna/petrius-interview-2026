"""Export with installed PowerPoint, render slides, write a readable speaker PDF and QA record."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

import fitz
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

HERE = Path(__file__).resolve().parent
PPTX = HERE / "PetrIUS_Interview_15min.pptx"
PDF = PPTX.with_suffix(".pdf")


def export_powerpoint():
    ps = r"""
$ErrorActionPreference = 'Stop'
$deckPath = Join-Path $PSScriptRoot 'PetrIUS_Interview_15min.pptx'
$powerpoint = New-Object -ComObject PowerPoint.Application
$wasEmpty = $powerpoint.Presentations.Count -eq 0
try {
  $deck = $powerpoint.Presentations.Open($deckPath, -1, 0, 0)
  $deck.SaveAs([System.IO.Path]::ChangeExtension($deckPath, '.pdf'), 32)
  $deck.Close()
} finally { if ($wasEmpty) { $powerpoint.Quit() } }
"""
    script = HERE / "export_powerpoint.ps1"
    script.write_text(ps.strip() + "\n", encoding="utf-8-sig")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], check=True)


def render_slides():
    folder = HERE / "rendered"
    folder.mkdir(exist_ok=True)
    doc = fitz.open(PDF)
    assert len(doc) == 18
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
    for i, page in enumerate(doc):
        page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6)).save(folder / f"slide_{i + 1:02d}.png")
    for start in range(0, len(doc), 6):
        sheet = Image.new("RGB", (1600, 1455), "#e0e0e0")
        draw = ImageDraw.Draw(sheet)
        for n in range(start, min(start + 6, len(doc))):
            im = Image.open(folder / f"slide_{n + 1:02d}.png")
            im.thumbnail((780, 439))
            x, y = 10 + (n - start) % 2 * 800, 10 + (n - start) // 2 * 480
            sheet.paste(im, (x, y))
            draw.text((x, y + 442), f"Slide {n + 1}", font=font, fill="#222222")
        sheet.save(folder / f"contact_{start + 1:02d}-{min(start + 6, len(doc)):02d}.jpg", quality=91)
    return doc


def speaker_pdf(slides):
    pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/arial.ttf"))
    pdfmetrics.registerFont(TTFont("ArialBold", "C:/Windows/Fonts/arialbd.ttf"))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Speech", fontName="Arial", fontSize=11, leading=15.5, spaceAfter=14))
    styles.add(ParagraphStyle("Section", fontName="ArialBold", fontSize=20, leading=25, textColor=colors.HexColor("#162B38"), spaceAfter=14))
    styles.add(ParagraphStyle("Cue", fontName="ArialBold", fontSize=12, leading=16, textColor=colors.HexColor("#087F8C"), spaceBefore=8, spaceAfter=7, keepWithNext=True))
    story = []
    for i, row in enumerate(slides):
        if i % 5 == 0:
            if i:
                story.append(PageBreak())
            story.append(Paragraph(f"{row['task']} — five-minute presentation", styles["Section"]))
            story.append(Paragraph("Conrad Compagna · PetrIUS interview · 20 October 2026", styles["Speech"]))
        story.append(Paragraph(f"{i:02d}:00–{i + 1:02d}:00 · Slide {i + 1}: {row['title']}", styles["Cue"]))
        story.append(Paragraph(row["body"], styles["Speech"]))
    def footer(canvas, doc):
        canvas.setFont("Arial", 9)
        canvas.setFillColor(colors.HexColor("#566570"))
        canvas.drawString(42, 24, "60 seconds per slide, including visual pointing pauses")
        canvas.drawRightString(A4[0] - 42, 24, str(doc.page))
    SimpleDocTemplate(str(HERE / "SPEAKER_SCRIPT.pdf"), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=36, bottomMargin=42).build(story, onFirstPage=footer, onLaterPages=footer)


def verify(doc, slides):
    content = "\n".join(p.get_text() for p in doc)
    assert all(s in content for s in ["131", "0.862", "0.945", "360", "Jacobus", "Bartolus", "5,065"])
    assert all(s not in content for s in ["Â", "â€", "â†", "silver", "AI-reviewed", "LLM-checked"])
    xml_count = 0
    with zipfile.ZipFile(PPTX) as z:
        assert z.testzip() is None
        notes = [n for n in z.namelist() if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n)]
        assert len(notes) == 18
        for n in z.namelist():
            if n.endswith(".xml"):
                data = z.read(n)
                ET.fromstring(data)
                xml_count += 1
                assert not re.search(rb'<a:ext[^>]*(?:cx|cy)="-\d+"', data)
    result = {
        "date": "2026-10-07",
        "main_slides": 15,
        "appendix_slides": 3,
        "powerpoint_open_and_pdf_export": "passed",
        "pdf_pages": len(doc),
        "embedded_note_pages": len(notes),
        "xml_files_parsed": xml_count,
        "zip_crc": "passed",
        "negative_shape_extents": 0,
        "encoding_check": "passed",
        "timing_seconds": sum(s["seconds"] for s in slides),
        "speaker_words_by_task": {t: sum(len(s["body"].split()) for s in slides if s["task"] == t) for t in ["Task I", "Task III", "Task IV"]},
        "assets": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((HERE / "assets").glob("*"))},
        "outputs": {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in [PPTX, PDF, HERE / "SPEAKER_SCRIPT.md", HERE / "SPEAKER_SCRIPT.pdf"]},
    }
    assert result["timing_seconds"] == 900
    (HERE / "QA.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    print(json.dumps({k: v for k, v in result.items() if k not in ["assets", "outputs"]}, indent=2))


if __name__ == "__main__":
    export_powerpoint()
    slides = json.loads((HERE / "slide_manifest.json").read_text(encoding="utf8"))
    doc = render_slides()
    speaker_pdf(slides)
    verify(doc, slides)
