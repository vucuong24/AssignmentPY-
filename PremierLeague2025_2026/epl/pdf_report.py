"""Render the generated Markdown report to a Unicode, paginated PDF."""
from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image, KeepTogether, LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle,
)

from .common import REPORTS


def register_fonts():
    candidates = [
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/Library/Fonts/Arial.ttf"), Path("/Library/Fonts/Arial Bold.ttf")),
    ]
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("ReportFont", str(regular)))
            pdfmetrics.registerFont(TTFont("ReportFontBold", str(bold)))
            pdfmetrics.registerFontFamily("ReportFont", normal="ReportFont", bold="ReportFontBold")
            return
    raise ValueError("Không tìm thấy font Unicode Arial/DejaVuSans để xuất PDF. HTML/Markdown vẫn đã lưu.")


def ascii_dashes(text: str) -> str:
    return text.replace("–", "-").replace("—", "-").replace("‑", "-")


def inline(text: str) -> str:
    text = escape(ascii_dashes(text))
    return re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)",
                  r'<link href="\2" color="#245caa">\1</link>', text)


def build_pdf(report_directory: Path | None = None, source_description: str | None = None,
              appendix_description: str | None = None) -> Path:
    register_fonts()
    report_directory = Path(report_directory) if report_directory is not None else REPORTS
    source = report_directory / "BAO_CAO.md"
    target = report_directory / "BAO_CAO.pdf"
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("VNNormal", fontName="ReportFont", fontSize=10, leading=15,
                            spaceAfter=9, textColor=colors.HexColor("#193044"))
    heading = ParagraphStyle("VNHeading", parent=normal, fontName="ReportFontBold", fontSize=17,
                             leading=23, spaceAfter=15, keepWithNext=True)
    subheading = ParagraphStyle("VNSubheading", parent=normal, fontName="ReportFontBold", fontSize=12,
                                leading=17, spaceBefore=10, spaceAfter=8, keepWithNext=True)
    title = ParagraphStyle("VNTitle", parent=heading, fontSize=25, leading=35, alignment=TA_CENTER)
    caption = ParagraphStyle("VNCaption", parent=normal, fontSize=9, leading=13, alignment=TA_CENTER)
    cell = ParagraphStyle("VNCell", parent=normal, fontSize=7, leading=10, spaceAfter=0, splitLongWords=True)
    width = A4[0] - 80
    doc = SimpleDocTemplate(str(target), pagesize=A4, leftMargin=40, rightMargin=40,
                            topMargin=43, bottomMargin=43, title="Phan tich Premier League 2025-2026",
                            author="Premier League Python Project")
    story = []
    lines = source.read_text(encoding="utf-8").splitlines()
    i = 0
    section_count = 0
    pending_table_heading = None
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("# "):
            story.extend([
                Spacer(1, 120), Paragraph(inline(line[2:]), title), Spacer(1, 35),
                Paragraph("BÁO CÁO BÀI TẬP LỚN - LẬP TRÌNH VỚI PYTHON", caption),
                Spacer(1, 25), Paragraph("Sinh viên: ........................................................", normal),
                Paragraph("Mã sinh viên: ..................................................", normal),
                Paragraph("Lớp / Giảng viên: ..............................................", normal),
                Spacer(1, 25), Paragraph(inline(source_description or "Dữ liệu: HTML FBref và JSON FootballTransfers đã lưu. Phạm vi nguồn được trình bày trong báo cáo."), normal),
                Spacer(1, 20), Paragraph(inline(appendix_description or "Bản HTML đi kèm chứa phụ lục toàn bộ 63 histogram."), normal), PageBreak(),
            ])
        elif line.startswith("### "):
            next_nonempty = next((item.strip() for item in lines[i + 1:] if item.strip()), "")
            if next_nonempty.startswith("|"):
                pending_table_heading = Paragraph(inline(line[4:]), subheading)
            else:
                story.append(Paragraph(inline(line[4:]), subheading))
        elif line.startswith("## "):
            if section_count:
                story.append(PageBreak())
            section_count += 1
            story.append(Paragraph(inline(line[3:]), heading))
        elif line.startswith("| "):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw_cells = [x.strip() for x in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", value) for value in raw_cells):
                    rows.append([Paragraph(inline(value), cell) for value in raw_cells])
                i += 1
            columns = len(rows[0])
            table = LongTable(rows, colWidths=[width / columns] * columns, repeatRows=1, hAlign="LEFT")
            vertical_padding = 4 if len(rows) >= 15 else 6
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e4edf6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), .3, colors.HexColor("#cdd9e3")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), vertical_padding),
                ("BOTTOMPADDING", (0, 0), (-1, -1), vertical_padding),
            ]))
            table_items = ([pending_table_heading] if pending_table_heading is not None else []) + [table]
            if len(rows) <= 8:
                story.extend([KeepTogether(table_items), Spacer(1, 15)])
            else:
                story.extend(table_items + [Spacer(1, 15)])
            pending_table_heading = None
            continue
        elif line.startswith("!["):
            match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", line)
            if match:
                image_path = (report_directory / match.group(2)).resolve()
                iw, ih = ImageReader(str(image_path)).getSize()
                ratio = min(width / iw, 450 / ih)
                figure_block = [
                    Image(str(image_path), width=iw * ratio, height=ih * ratio),
                    Paragraph(inline(match.group(1)), caption),
                    Spacer(1, 14),
                ]
                # Keep a figure with its reading guide, not with the next figure/section.
                cursor = i + 1
                while cursor < len(lines):
                    following = lines[cursor].strip()
                    if following.startswith(("#", "|", "![", "- ")):
                        break
                    if following:
                        figure_block.append(Paragraph(inline(following), normal))
                    cursor += 1
                story.append(KeepTogether(figure_block))
                i = cursor
                continue
        else:
            story.append(Paragraph(inline(line.removeprefix("- ")), normal))
        i += 1

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#cdd9e3"))
        canvas.line(40, 32, A4[0] - 40, 32)
        canvas.setFont("ReportFont", 8)
        canvas.setFillColor(colors.HexColor("#53697a"))
        canvas.drawString(40, 20, "Premier League 2025-2026 | Python")
        canvas.drawRightString(A4[0] - 40, 20, f"Trang {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return target
