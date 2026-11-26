"""Renderização XLSX (openpyxl): valores como número/data de verdade, prontos para somar e filtrar.

- Dinheiro: Decimal(centavos)/100, formato contábil em R$ (o Excel aplica o separador do idioma).
- Datas: tipo data, exibidas como dd/mm/aaaa.
- Cabeçalho congelado e com autofiltro; linha de total em negrito.
"""

import io
from datetime import datetime
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.domains.reporting.exports import Table, cell_text, period_label
from app.domains.support import now_local

MONEY_FMT = '"R$" #,##0.00;[Red]-"R$" #,##0.00'
DATE_FMT = "DD/MM/YYYY"
PCT_FMT = "0.0"
SHEET_NAME = {
    "transactions": "Lançamentos",
    "card-purchases": "Compras no cartão",
    "party-balances": "Terceiros - valores",
    "categories": "Categorias",
    "cash-flow": "Fluxo de caixa",
    "cards": "Cartões",
    "counterparties": "Terceiros - atrasos",
}

HEADER_FILL = PatternFill("solid", fgColor="4C1D95")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TOTAL_FILL = PatternFill("solid", fgColor="EDE9FE")
TOP_BORDER = Border(top=Side(style="thin", color="4C1D95"))

FIRST_HEADER_ROW = 4


def _value(v, col_type: str):
    if v is None or v == "":
        return None
    if col_type == "money":
        return Decimal(int(v)) / Decimal(100)
    if col_type == "period":
        return period_label(v)
    return v


def _write_sheet(ws, table: Table, generated: datetime) -> None:
    ws["A1"] = table.title
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"{table.subtitle} · gerado em {generated:%d/%m/%Y %H:%M}"
    ws["A2"].font = Font(italic=True, color="6B7280")

    widths = [len(c.label) for c in table.columns]
    for j, col in enumerate(table.columns, start=1):
        c = ws.cell(row=FIRST_HEADER_ROW, column=j, value=col.label)
        c.font, c.fill = HEADER_FONT, HEADER_FILL
        c.alignment = Alignment(horizontal="right" if col.type in ("money", "int", "pct") else "left",
                                vertical="center", wrap_text=True)

    r = FIRST_HEADER_ROW
    for row in table.rows:
        r += 1
        for j, (v, col) in enumerate(zip(row, table.columns, strict=True), start=1):
            c = ws.cell(row=r, column=j, value=_value(v, col.type))
            if col.type == "money":
                c.number_format = MONEY_FMT
            elif col.type == "date":
                c.number_format = DATE_FMT
            elif col.type == "pct":
                c.number_format = PCT_FMT
            widths[j - 1] = max(widths[j - 1], len(cell_text(v, col.type)) + (4 if col.type == "money" else 0))

    last_data = r
    if table.total:
        r += 1
        for j, (v, col) in enumerate(zip(table.total, table.columns, strict=True), start=1):
            c = ws.cell(row=r, column=j, value=_value(v, col.type))
            c.font, c.fill, c.border = Font(bold=True), TOTAL_FILL, TOP_BORDER
            if col.type == "money":
                c.number_format = MONEY_FMT
            elif col.type == "pct":
                c.number_format = PCT_FMT

    if not table.rows:
        ws.cell(row=FIRST_HEADER_ROW + 1, column=1, value="Nenhum registro no período.").font = Font(
            italic=True, color="6B7280"
        )

    ws.freeze_panes = ws.cell(row=FIRST_HEADER_ROW + 1, column=1)
    if table.rows:
        ws.auto_filter.ref = f"A{FIRST_HEADER_ROW}:{get_column_letter(len(table.columns))}{last_data}"
    for j, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(j)].width = min(max(w + 2, 10), 50)
    ws.row_dimensions[FIRST_HEADER_ROW].height = 30


def render_xlsx(tables: list[Table]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    generated = now_local()
    for table in tables:
        ws = wb.create_sheet(SHEET_NAME.get(table.kind, table.kind)[:31])
        _write_sheet(ws, table, generated)
    wb.properties.title = tables[0].title if len(tables) == 1 else "Finance Hub — pacote completo"
    wb.properties.creator = "Finance Hub Pessoal"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
