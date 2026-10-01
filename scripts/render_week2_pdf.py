from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
from xml.sax.saxutils import escape

ROOT = Path('/Users/woojin/Documents/막시무스')
SRC = ROOT / 'output' / 'reports' / '[2주차]_막시무스_선행연구조사보고서.docx'
OUT = ROOT / 'output' / 'reports' / '[2주차]_막시무스_선행연구조사보고서.pdf'
FONT_PATH = '/Library/Fonts/Arial Unicode.ttf'
pdfmetrics.registerFont(TTFont('Korean', FONT_PATH))

navy = HexColor('#1F4D78')
gray = HexColor('#666666')

styles = {
    'title': ParagraphStyle('title', fontName='Korean', fontSize=20, leading=25, textColor=navy,
                            alignment=TA_CENTER, spaceAfter=2),
    'meta': ParagraphStyle('meta', fontName='Korean', fontSize=9.5, leading=12, textColor=gray,
                           alignment=TA_CENTER, spaceAfter=2),
    'team': ParagraphStyle('team', fontName='Korean', fontSize=9.8, leading=12, textColor=HexColor('#000000'),
                           alignment=TA_CENTER, spaceAfter=7),
    'h1': ParagraphStyle('h1', fontName='Korean', fontSize=14, leading=18, textColor=navy,
                         spaceBefore=8, spaceAfter=5, keepWithNext=True),
    'h2': ParagraphStyle('h2', fontName='Korean', fontSize=11, leading=14, textColor=navy,
                         spaceBefore=5, spaceAfter=3, keepWithNext=True),
    'body': ParagraphStyle('body', fontName='Korean', fontSize=9.2, leading=13.0,
                           alignment=TA_JUSTIFY, spaceAfter=5, splitLongWords=False),
    'ref': ParagraphStyle('ref', fontName='Korean', fontSize=7.3, leading=9.1,
                          textColor=HexColor('#444444'), leftIndent=4*mm, firstLineIndent=-4*mm,
                          spaceAfter=1.2),
}

docx = Document(SRC)
story = []
nonempty_index = 0
in_refs = False

for p in docx.paragraphs:
    has_page_break = any(
        br.get(qn('w:type')) == 'page'
        for br in p._p.xpath('.//w:br')
    )
    if has_page_break:
        story.append(PageBreak())
        continue
    text = p.text.strip()
    if not text:
        continue
    nonempty_index += 1
    if nonempty_index == 1:
        style = styles['title']
    elif nonempty_index == 2:
        style = styles['meta']
    elif nonempty_index == 3:
        style = styles['team']
    elif p.style.name == 'Heading 1':
        style = styles['h1']
    elif p.style.name == 'Heading 2':
        style = styles['h2']
        if text == '참고문헌':
            in_refs = True
    elif in_refs:
        style = styles['ref']
    else:
        style = styles['body']
    story.append(Paragraph(escape(text), style))

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Korean', 8)
    canvas.setFillColor(gray)
    canvas.drawCentredString(A4[0] / 2, 8 * mm, str(doc.page))
    canvas.restoreState()

pdf = SimpleDocTemplate(
    str(OUT), pagesize=A4,
    leftMargin=20*mm, rightMargin=20*mm, topMargin=16*mm, bottomMargin=15*mm,
    title='[2주차] 막시무스 선행 연구 조사 보고서',
    author='팀 막시무스 (장한별, 지우진, 최시현)',
)
pdf.build(story, onFirstPage=footer, onLaterPages=footer)
print(OUT)
