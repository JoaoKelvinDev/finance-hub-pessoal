"""Renderização PDF (reportlab): A4 paisagem, cabeçalho de tabela repetido a cada página.

Valores no formato brasileiro (R$ 1.234,56), linha de total em destaque e rodapé
"Página X de Y". Fontes padrão (Helvetica) cobrem os acentos do português.
"""

import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.domains.reporting.exports import Column, cell_text, period_label
from app.domains.reporting.exports import Table as DataTable
from app.domains.support import now_local

VIOLET = colors.HexColor("#4C1D95")
VIOLET_SOFT = colors.HexColor("#EDE9FE")
ZEBRA = colors.HexColor("#F7F7FA")
MUTED = colors.HexColor("#6B7280")
NEGATIVE = colors.HexColor("#B91C1C")

PAGE = landscape(A4)
MARGIN = 1.2 * cm
NUMERIC = ("money", "int", "pct")

TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=15, leading=19, spaceAfter=2)
SUBTITLE = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=9, leading=12, textColor=MUTED)
CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=7.5, leading=9.5)
CELL_R = ParagraphStyle("cell_r", parent=CELL, alignment=TA_RIGHT)
CELL_NEG = ParagraphStyle("cell_neg", parent=CELL_R, textColor=NEGATIVE)
HEAD = ParagraphStyle("head", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
HEAD_R = ParagraphStyle("head_r", parent=HEAD, alignment=TA_RIGHT)
BOLD = ParagraphStyle("bold", parent=CELL, fontName="Helvetica-Bold")
BOLD_R = ParagraphStyle("bold_r", parent=BOLD, alignment=TA_RIGHT)
EMPTY = ParagraphStyle("empty", parent=SUBTITLE, fontName="Helvetica-Oblique")


def brl(cents: int) -> str:
    """Centavos -> 'R$ 1.234,56' / '-R$ 1.234,56'."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    reais = f"{cents // 100:,}".replace(",", ".")
    return f"{sign}R$ {reais},{cents % 100:02d}"


def _text(v, col: Column) -> str:
    if col.type == "money" and v is not None and v != "":
        return brl(int(v))
    if col.type == "pct" and v is not None and v != "":
        return f"{cell_text(v, 'pct')}%"
    if col.type == "period":
        return period_label(v)
    return cell_text(v, col.type)


def _widths(table: DataTable, available: float) -> list[float]:
    """Largura proporcional ao conteúdo; nunca menor que o rótulo (com folga do negrito), teto p/ textos longos."""
    weights = []
    for j, col in enumerate(table.columns):
        sample = [len(_text(r[j], col)) for r in table.rows[:300]]
        # Rótulos longos podem quebrar em 2 linhas; curtos ("Pessoa") cabem inteiros.
        label = len(col.label) + 2 if len(col.label) <= 14 else (len(col.label) + 1) / 2 + 2
        weights.append(min(max(label, *sample, 9 if col.type in NUMERIC else 6), 45))
    total = sum(weights)
    return [available * w / total for w in weights]


def _flowables(table: DataTable) -> list:
    out = [Paragraph(escape(table.title), TITLE), Paragraph(escape(table.subtitle), SUBTITLE), Spacer(1, 8)]
    if not table.rows:
        out.append(Paragraph("Nenhum registro no período.", EMPTY))
        return out

    header = [Paragraph(escape(c.label), HEAD_R if c.type in NUMERIC else HEAD) for c in table.columns]
    data = [header]
    for row in table.rows:
        line = []
        for v, col in zip(row, table.columns, strict=True):
            if col.type == "money" and isinstance(v, int) and v < 0:
                style = CELL_NEG
            else:
                style = CELL_R if col.type in NUMERIC else CELL
            line.append(Paragraph(escape(_text(v, col)), style))
        data.append(line)
    if table.total:
        data.append([
            Paragraph(escape(_text(v, col)), BOLD_R if col.type in NUMERIC else BOLD)
            for v, col in zip(table.total, table.columns, strict=True)
        ])

    t = Table(data, colWidths=_widths(table, PAGE[0] - 2 * MARGIN), repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), VIOLET),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
    ]
    style += [("BACKGROUND", (0, i), (-1, i), ZEBRA) for i in range(2, len(table.rows) + 1, 2)]
    if table.total:
        style += [("BACKGROUND", (0, -1), (-1, -1), VIOLET_SOFT), ("LINEABOVE", (0, -1), (-1, -1), 0.8, VIOLET)]
    t.setStyle(TableStyle(style))
    out.append(t)
    return out


def _canvas_factory(generated: datetime):
    class NumberedCanvas(Canvas):
        """Guarda as páginas para escrever 'Página X de Y' no fim."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._pages: list[dict] = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self.setFont("Helvetica", 7.5)
                self.setFillColor(MUTED)
                self.drawString(MARGIN, 0.7 * cm, f"Finance Hub Pessoal · gerado em {generated:%d/%m/%Y %H:%M}")
                self.drawRightString(PAGE[0] - MARGIN, 0.7 * cm, f"Página {self._pageNumber} de {total}")
                super().showPage()
            super().save()

    return NumberedCanvas


def render_pdf(tables: list[DataTable]) -> bytes:
    buf = io.BytesIO()
    title = tables[0].title if len(tables) == 1 else "Finance Hub — pacote completo"
    doc = SimpleDocTemplate(
        buf, pagesize=PAGE, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=1.4 * cm,
        title=title, author="Finance Hub Pessoal",
    )
    story: list = []
    for k, table in enumerate(tables):
        if k:
            story.append(PageBreak())
        story += _flowables(table)
    doc.build(story, canvasmaker=_canvas_factory(now_local()))
    return buf.getvalue()
