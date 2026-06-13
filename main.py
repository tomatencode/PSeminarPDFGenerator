import json
import os
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    HRFlowable, Table, TableStyle, PageBreak,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY

# ── Colour palette (matching the Planspiele Rollenkarte style) ─────────────────
BLUE       = HexColor('#5B8EC4')   # title colour
ORANGE     = HexColor('#E87800')   # section-header colour
GRAY       = HexColor('#888888')   # page-header / rule colour
TABLE_DARK = HexColor("#35619B")   # info-table header background

# ── Page geometry ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN_H = 1.5 * cm
MARGIN_V = 1.5 * cm
CONTENT_W    = PAGE_W - 2 * MARGIN_H   # ≈ 18 cm
FLAG_COL_W   = 5.0 * cm
INFO_TABLE_W = 10.0 * cm
LABEL_COL_W  = 3.2 * cm
VALUE_COL_W  = INFO_TABLE_W - LABEL_COL_W


def _styles():
    page_header = ParagraphStyle(
        'PageHeader',
        fontSize=9,
        textColor=GRAY,
        fontName='Helvetica',
        spaceAfter=2,
    )
    title = ParagraphStyle(
        'CountryTitle',
        fontSize=26,
        textColor=BLUE,
        fontName='Helvetica',
        spaceBefore=4,
        spaceAfter=14,
        leading=32,
    )
    section = ParagraphStyle(
        'SectionTitle',
        fontSize=10,
        textColor=ORANGE,
        fontName='Helvetica-Bold',
        spaceBefore=10,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        'Body',
        fontSize=9,
        fontName='Helvetica',
        leading=13,
        spaceAfter=6,
        alignment=TA_JUSTIFY,
    )
    return page_header, title, section, body


def _flag_image(path):
    """Return an Image flowable that fits within FLAG_COL_W × 4 cm."""
    img = Image(path)
    nat_w, nat_h = img.imageWidth, img.imageHeight
    max_w, max_h = FLAG_COL_W - 0.2 * cm, 4.0 * cm
    ratio = min(max_w / nat_w, max_h / nat_h)
    img.drawWidth  = nat_w * ratio
    img.drawHeight = nat_h * ratio
    return img


def _build_info_table(info: dict, styles) -> Table | None:
    """Build the country fact table (dark header + label/value rows)."""
    _, _, _, body_style = styles

    header_style = ParagraphStyle(
        'InfoHeader',
        fontSize=9,
        textColor=white,
        fontName='Helvetica-Bold',
        leading=12,
    )
    label_style = ParagraphStyle(
        'InfoLabel',
        fontSize=8,
        fontName='Helvetica',
        leading=11,
    )
    value_style = ParagraphStyle(
        'InfoValue',
        fontSize=8,
        fontName='Helvetica',
        leading=11,
    )

    header_text = info.get('header', '')
    rows_data   = info.get('rows', {})

    table_rows = []

    # Header row spans both columns
    if header_text:
        table_rows.append([Paragraph(header_text, header_style), ''])

    # Label / value rows
    for label, value in rows_data.items():
        table_rows.append([
            Paragraph(label, label_style),
            Paragraph(str(value), value_style),
        ])

    if not table_rows:
        return None

    tbl = Table(
        table_rows,
        colWidths=[LABEL_COL_W, VALUE_COL_W],
    )

    style_cmds = [
        # all cells
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        # outer border
        ('BOX',           (0, 0), (-1, -1), 0.5, GRAY),
        # horizontal lines between rows
        ('INNERGRID',     (0, 0), (-1, -1), 0.3, GRAY),
    ]

    if header_text:
        style_cmds += [
            # header spans both columns
            ('SPAN',            (0, 0), (1, 0)),
            ('BACKGROUND',      (0, 0), (1, 0), TABLE_DARK),
            # no divider inside the header cell
            ('INNERGRID',       (0, 0), (1, 0), 0, TABLE_DARK),
        ]

    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def build_story(data: dict, flags_dir: str) -> list:
    all_styles = _styles()
    page_header_style, title_style, section_style, body_style = all_styles
    story = []

    for idx, (country_name, country_data) in enumerate(data.items()):
        if idx > 0:
            story.append(PageBreak())

        flag_file  = country_data.get('flag', '')
        info       = country_data.get('info', {})
        paragraphs = country_data.get('paragraphs', [])

        # ── page header + rule ────────────────────────────────────────────────
        story.append(Paragraph(f'M3: Rollenkarte {country_name}', page_header_style))
        story.append(HRFlowable(width='100%', thickness=0.75, color=GRAY, spaceAfter=10))

        # ── full-width country title ──────────────────────────────────────────
        story.append(Paragraph(country_name, title_style))

        # ── info table (left) + flag (right) ─────────────────────────────────
        flag_path   = os.path.join(flags_dir, flag_file)
        has_flag    = bool(flag_file and os.path.exists(flag_path))
        info_table  = _build_info_table(info, all_styles) if info else None

        if info_table and has_flag:
            flag_img    = _flag_image(flag_path)
            gap         = CONTENT_W - INFO_TABLE_W - FLAG_COL_W
            outer = Table(
                [[info_table, '', flag_img]],
                colWidths=[INFO_TABLE_W, gap, FLAG_COL_W],
            )
            outer.setStyle(TableStyle([
                ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
                ('ALIGN',         (2, 0), (2,  0),  'RIGHT'),
                ('TOPPADDING',    (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ('LEFTPADDING',   (0, 2), (-1, -1), 0),
                ('RIGHTPADDING',  (0, 2), (-1, -1), 0),
            ]))
            story.append(outer)
        elif info_table:
            story.append(info_table)
        elif has_flag:
            flag_img = _flag_image(flag_path)
            story.append(flag_img)

        story.append(Spacer(1, 10))

        # ── content paragraphs ────────────────────────────────────────────────
        for para in paragraphs:
            title = para.get('title', '').strip()
            text  = para.get('text',  '').strip()
            if title:
                story.append(Paragraph(title, section_style))
            if text:
                story.append(Paragraph(text, body_style))

    return story


def generate_pdf(json_path: str, output_path: str, flags_dir: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with open(json_path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN_H,
        rightMargin=MARGIN_H,
        topMargin=MARGIN_V,
        bottomMargin=MARGIN_V,
    )
    doc.build(build_story(data, flags_dir))
    print(f'PDF written to {output_path}')


if __name__ == '__main__':
    json_path   = sys.argv[1] if len(sys.argv) > 1 else 'pharagraphs.json'
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'out/output.pdf'
    flags_dir   = sys.argv[3] if len(sys.argv) > 3 else 'flags'
    generate_pdf(json_path, output_path, flags_dir)
