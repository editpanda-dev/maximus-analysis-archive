from pathlib import Path

from docx import Document
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph as RLParagraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path("/Users/woojin/Documents/막시무스")
DOCX = ROOT / "output" / "reports" / "[3주차]_막시무스_방학스터디_최종보고서.docx"
PDF = ROOT / "output" / "reports" / "[3주차]_막시무스_방학스터디_최종보고서.pdf"
CHART = ROOT / "reports" / "eda" / "dongdaemun_50min_pilot" / "figures" / "b078_time_bands.png"
FONT_PATH = Path("/Library/Fonts/Arial Unicode.ttf")

pdfmetrics.registerFont(TTFont("Korean", str(FONT_PATH)))

NAVY = colors.HexColor("#1F4D78")
MID = colors.HexColor("#5C6975")
PALE = colors.HexColor("#EAF1F8")
LIGHT = colors.HexColor("#F3F5F7")
BLACK = colors.HexColor("#14181C")


def esc(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


styles = getSampleStyleSheet()
BODY = ParagraphStyle("BodyK", parent=styles["BodyText"], fontName="Korean", fontSize=7.5,
                      leading=10.1, textColor=BLACK, alignment=TA_JUSTIFY, spaceAfter=3.2)
H1 = ParagraphStyle("H1K", parent=BODY, fontSize=14, leading=17, textColor=NAVY,
                    spaceBefore=4, spaceAfter=5)
H2 = ParagraphStyle("H2K", parent=BODY, fontSize=10.3, leading=12.5, textColor=NAVY,
                    spaceBefore=5, spaceAfter=3)
TITLE = ParagraphStyle("TitleK", parent=BODY, fontSize=19, leading=23, textColor=NAVY,
                       alignment=TA_CENTER, spaceBefore=8, spaceAfter=4)
CENTER = ParagraphStyle("CenterK", parent=BODY, alignment=TA_CENTER, textColor=MID)
LABEL = ParagraphStyle("LabelK", parent=BODY, fontSize=7.3, leading=9.6)
CELL = ParagraphStyle("CellK", parent=BODY, fontSize=6.8, leading=8.3, spaceAfter=0)
CELL_HEAD = ParagraphStyle("CellHeadK", parent=CELL, textColor=NAVY, alignment=TA_CENTER)
CALLOUT = ParagraphStyle("CalloutK", parent=BODY, fontSize=7.4, leading=9.8, spaceAfter=0)


def iter_blocks(document):
    parent = document.element.body
    for child in parent.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, document)
        elif child.tag.endswith("}tbl"):
            yield DocxTable(child, document)


def has_page_break(paragraph):
    return bool(paragraph._p.xpath('.//w:br[@w:type="page"]'))


def page_furniture(canvas, doc):
    canvas.saveState()
    canvas.setFont("Korean", 7.2)
    canvas.setFillColor(MID)
    canvas.drawRightString(A4[0] - 19 * mm, A4[1] - 10 * mm, "MAXIMUS · DAT 방학 스터디")
    canvas.drawCentredString(A4[0] / 2, 8 * mm, str(doc.page))
    canvas.restoreState()


def make_table(block):
    data = []
    for r_idx, row in enumerate(block.rows):
        rendered = []
        for cell in row.cells:
            text = "\n".join(p.text.strip() for p in cell.paragraphs if p.text.strip())
            style = CELL_HEAD if r_idx == 0 else CELL
            rendered.append(RLParagraph(esc(text), style))
        data.append(rendered)
    cols = len(data[0]) if data else 1
    if cols == 1:
        widths = [172 * mm]
    elif cols == 2:
        widths = [32 * mm, 140 * mm]
    elif cols == 3:
        widths = [37 * mm, 72 * mm, 63 * mm]
    elif cols == 4:
        widths = [24 * mm, 38 * mm, 62 * mm, 48 * mm]
    else:
        widths = [172 * mm / cols] * cols
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="CENTER")
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), "Korean"),
        ("GRID", (0, 0), (-1, -1), .45, colors.HexColor("#30363B")),
        ("BACKGROUND", (0, 0), (-1, 0), PALE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]
    if cols == 1:
        commands = [
            ("FONTNAME", (0, 0), (-1, -1), "Korean"),
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
            ("BOX", (0, 0), (-1, -1), 0, LIGHT),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
    table.setStyle(TableStyle(commands))
    return KeepTogether([table, Spacer(1, 3)])


def build():
    source = Document(DOCX)
    story = []
    image_inserted = False
    for block in iter_blocks(source):
        if isinstance(block, DocxTable):
            story.append(make_table(block))
            continue
        if has_page_break(block):
            story.append(PageBreak())
            continue
        text = block.text.strip()
        has_drawing = bool(block._p.xpath('.//w:drawing'))
        if has_drawing and not image_inserted:
            img = Image(str(CHART), width=166 * mm, height=69 * mm)
            img.hAlign = "CENTER"
            story.append(img)
            image_inserted = True
            continue
        if not text:
            continue
        style_name = block.style.name if block.style else ""
        if style_name == "Heading 1":
            story.append(RLParagraph(esc(text), H1))
        elif style_name == "Heading 2":
            story.append(RLParagraph(esc(text), H2))
        elif text == "[3주차] 방학 스터디 최종 보고서":
            story.append(RLParagraph(esc(text), TITLE))
        elif text.startswith("2026년") or text.startswith("팀 막시무스") or text.startswith("그림 1."):
            story.append(RLParagraph(esc(text), CENTER))
        elif text.startswith("※") or text.startswith("자료 출처 및 재현성"):
            story.append(RLParagraph(esc(text), LABEL))
        else:
            # Preserve the visual label hierarchy used in the DOCX paragraphs.
            first = next((run.text.strip() for run in block.runs if run.bold and run.text.strip()), "")
            if first and text.startswith(first):
                rest = text[len(first):].strip()
                html = f'<font color="#1F4D78">{esc(first)}</font>  {esc(rest)}'
                story.append(RLParagraph(html, LABEL))
            else:
                story.append(RLParagraph(esc(text), BODY))

    doc = SimpleDocTemplate(
        str(PDF), pagesize=A4,
        leftMargin=19 * mm, rightMargin=19 * mm,
        topMargin=15 * mm, bottomMargin=14 * mm,
        title="[3주차] 막시무스 방학 스터디 최종 보고서",
        author="팀 막시무스",
    )
    doc.build(story, onFirstPage=page_furniture, onLaterPages=page_furniture)
    print(PDF)


if __name__ == "__main__":
    build()
