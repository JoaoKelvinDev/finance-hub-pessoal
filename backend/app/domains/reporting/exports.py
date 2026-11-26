"""Exportação em CSV, XLSX e PDF a partir de uma única montagem de tabelas.

Cada tipo de exportação monta uma `Table` com valores brutos (centavos inteiros, datas,
percentuais). Os três formatos são renderizados a partir dessas mesmas linhas, então os
totais são idênticos em qualquer formato.

CSV (Excel pt-BR):
- Separador ";" e vírgula decimal (o Excel pt-BR reconhece os valores como número).
- UTF-8 com BOM: acentos abrem corretamente no Excel.
- Datas em dd/mm/aaaa. Valores sem separador de milhar.

Toda exportação é registrada em audit_events (dados sensíveis), com o formato.
"""

import csv
import io
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.parties import service as parties
from app.domains.reporting import reports
from app.domains.support import audit
from app.models import CardPurchase, Transaction

ExportKind = Literal[
    "transactions", "card-purchases", "party-balances", "categories", "cash-flow", "cards", "counterparties"
]
ExportFormat = Literal["csv", "xlsx", "pdf"]
# "period": "AAAA-MM" ou "AAAA-MM-DD" — o CSV mantém o texto bruto; XLSX/PDF mostram "nov/2026" ou "25/11".
ColType = Literal["text", "money", "date", "int", "pct", "period"]
Cell = str | int | float | date | None

KINDS: tuple[str, ...] = (
    "transactions", "card-purchases", "categories", "cash-flow", "cards", "counterparties", "party-balances"
)
MEDIA_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}

KIND_LABEL = {
    "INCOME": "Receita",
    "EXPENSE": "Despesa",
    "TRANSFER_IN": "Transferência recebida",
    "TRANSFER_OUT": "Transferência enviada",
    "ADJUSTMENT": "Ajuste",
    "LOAN_OUT": "Empréstimo/adiantamento concedido",
    "LOAN_IN": "Empréstimo recebido",
    "SETTLEMENT_IN": "Acerto recebido",
    "SETTLEMENT_OUT": "Acerto pago",
}
STATUS_LABEL = {"POSTED": "Efetivado", "PLANNED": "Previsto", "CANCELLED": "Cancelado"}
PARTY_ORIGIN = {
    "LOAN_GIVEN": "Emprestei",
    "LOAN_TAKEN": "Peguei emprestado",
    "ADVANCE": "Paguei por alguém",
    "OWED_TO_ME": "Alguém me deve",
    "I_OWE": "Eu devo",
}
PARTY_STATUS = {
    "OPEN": "Em aberto",
    "PARTIALLY_SETTLED": "Parcial",
    "SETTLED": "Quitado",
    "OVERDUE": "Vencido",
    "CANCELLED": "Cancelado",
}
BASIS_LABEL = {"CASH": "regime de caixa", "COMPETENCE": "regime de competência"}


@dataclass
class Column:
    label: str
    type: ColType = "text"


@dataclass
class Table:
    kind: str
    title: str
    subtitle: str
    columns: list[Column]
    rows: list[list[Cell]] = field(default_factory=list)
    total: list[Cell] | None = None

    @property
    def row_count(self) -> int:
        return len(self.rows) + (1 if self.total else 0)


def money(cents: int) -> str:
    """Centavos -> '1234,56' (sem ponto flutuante)."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100},{cents % 100:02d}"


def d(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def cell_text(value: Cell, col_type: ColType) -> str:
    """Texto da célula no padrão do CSV (pt-BR, sem separador de milhar)."""
    if value is None:
        return ""
    if col_type == "money":
        return money(int(value))
    if col_type == "date":
        return d(value)  # type: ignore[arg-type]
    if col_type == "pct":
        return f"{value}".replace(".", ",")
    return str(value)


MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def period_label(value: Cell) -> str:
    """'2026-11' -> 'nov/2026'; '2026-11-25' -> '25/11/2026'; outros textos (ex.: 'Total') ficam iguais."""
    s = str(value or "")
    parts = s.split("-")
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        return f"{MONTHS[int(parts[1]) - 1]}/{parts[0]}"
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return s


def _period(start: date, end: date) -> str:
    return f"{d(start)} a {d(end)}"


def _cols(*spec: str | tuple[str, ColType]) -> list[Column]:
    return [Column(s) if isinstance(s, str) else Column(*s) for s in spec]


# ---------- montagem das tabelas ----------

def _transactions(db: Session, start: date, end: date) -> Table:
    txs = db.scalars(
        select(Transaction)
        .where(Transaction.effective_date.between(start, end))
        .order_by(Transaction.effective_date, Transaction.created_at)
    ).unique()
    return Table(
        "transactions", "Lançamentos", _period(start, end),
        _cols(("Data", "date"), "Descrição", "Tipo", "Situação", "Conta", "Categoria", "Pessoa",
              ("Valor (R$)", "money")),
        [
            [
                t.effective_date,
                t.description,
                KIND_LABEL.get(t.kind, t.kind),
                STATUS_LABEL.get(t.status, t.status),
                t.account.name,
                t.category.name if t.category else "",
                t.counterparty.display_name if t.counterparty else "",
                t.amount_cents,
            ]
            for t in txs
        ],
    )


def _card_purchases(db: Session, start: date, end: date) -> Table:
    items = db.scalars(
        select(CardPurchase)
        .where(CardPurchase.purchased_on.between(start, end))
        .order_by(CardPurchase.purchased_on, CardPurchase.created_at)
    ).unique()
    return Table(
        "card-purchases", "Compras no cartão", _period(start, end),
        _cols(("Data", "date"), "Cartão", "Estabelecimento", "Descrição", "Categoria", ("Parcelas", "int"),
              "Situação", ("Valor (R$)", "money")),
        [
            [
                p.purchased_on,
                p.card.nickname or p.card.name,
                p.merchant or "",
                p.description,
                p.category.name if p.category else "",
                p.installments_count,
                {"ACTIVE": "Ativa", "REVERSED": "Estornada", "CANCELLED": "Cancelada"}.get(p.status, p.status),
                p.total_cents,
            ]
            for p in items
        ],
    )


def _party_balances(db: Session) -> Table:
    return Table(
        "party-balances", "Valores com terceiros", "Posição atual (inclui quitados e cancelados)",
        _cols("Pessoa", "Tipo", "Direção", "Descrição", ("Data", "date"), ("Vencimento", "date"),
              ("Principal (R$)", "money"), ("Encargos (R$)", "money"), ("Descontos (R$)", "money"),
              ("Acertado (R$)", "money"), ("Em aberto (R$)", "money"), "Situação"),
        [
            [
                b.person_name,
                PARTY_ORIGIN.get(b.origin_type, b.origin_type),
                "A receber" if b.direction == "RECEIVABLE" else "A pagar",
                b.description,
                b.operation_date,
                b.due_date,
                b.principal_cents,
                b.charges_cents,
                b.discounts_cents,
                b.settled_cents,
                b.open_cents,
                PARTY_STATUS.get(b.status, b.status),
            ]
            for b in parties.list_balances(db, include_cancelled=True)
        ],
    )


def _categories(db: Session, start: date, end: date, basis: str) -> Table:
    r = reports.category_report(db, start, end, basis)
    rows: list[list[Cell]] = []
    for row in r.rows:
        rows.append([row.name, "", row.amount_cents, row.previous_cents, row.share_pct])
        for child in row.children:
            rows.append([row.name, child.name, child.amount_cents, child.previous_cents, child.share_pct])
    return Table(
        "categories", "Gastos por categoria", f"{_period(start, end)} · {BASIS_LABEL.get(basis, basis)}",
        _cols("Categoria", "Subcategoria", ("Valor (R$)", "money"), ("Período anterior (R$)", "money"),
              ("Participação (%)", "pct")),
        rows,
        ["Total", "", r.total_cents, r.previous_total_cents, 100],
    )


def _cash_flow(db: Session, start: date, end: date) -> Table:
    r = reports.cash_flow_report(db, start, end)
    return Table(
        "cash-flow", "Fluxo de caixa",
        f"{_period(start, end)} · {'por dia' if r.granularity == 'day' else 'por mês'}",
        _cols(("Período", "period"), ("Receitas (R$)", "money"), ("Despesas (R$)", "money"), ("Resultado (R$)", "money")),
        [[p.period, p.income_cents, p.expense_cents, p.net_cents] for p in r.points],
        ["Total", r.income_cents, r.expense_cents, r.net_cents],
    )


def _cards(db: Session, start: date, end: date) -> Table:
    r = reports.card_report(db, start, end)
    return Table(
        "cards", "Cartões", _period(start, end),
        _cols("Cartão", "Banco", ("Compras no período (R$)", "money"), ("Qtd. compras", "int"),
              ("Pago no período (R$)", "money"), ("Em aberto (R$)", "money"), ("Parcelas futuras (R$)", "money")),
        [
            [c.name, c.bank or "", c.purchases_cents, c.purchases_count, c.paid_cents, c.open_cents, c.future_cents]
            for c in r.cards
        ],
    )


def _counterparties(db: Session, start: date, end: date) -> Table:
    r = reports.counterparty_report(db, start, end)
    return Table(
        "counterparties", "Terceiros — posição e atrasos",
        f"Posição em {d(r.today)} · recebido no período {_period(start, end)}",
        _cols("Pessoa", ("Me deve (R$)", "money"), ("Eu devo (R$)", "money"), ("A vencer (R$)", "money"),
              ("Atraso 1–30 (R$)", "money"), ("Atraso 31–60 (R$)", "money"), ("Atraso 61–90 (R$)", "money"),
              ("Atraso 90+ (R$)", "money"), ("Sem vencimento (R$)", "money"), ("Recebido no período (R$)", "money")),
        [
            [
                p.name, p.receivable_cents, p.payable_cents,
                p.receivable_aging.current_cents, p.receivable_aging.d0_30_cents,
                p.receivable_aging.d31_60_cents, p.receivable_aging.d61_90_cents,
                p.receivable_aging.d90_plus_cents, p.receivable_aging.no_due_cents,
                p.settled_in_period_cents,
            ]
            for p in r.people
        ],
    )


def build_table(db: Session, kind: str, start: date, end: date, basis: str) -> Table:
    builders = {
        "transactions": lambda: _transactions(db, start, end),
        "card-purchases": lambda: _card_purchases(db, start, end),
        "party-balances": lambda: _party_balances(db),
        "categories": lambda: _categories(db, start, end, basis),
        "cash-flow": lambda: _cash_flow(db, start, end),
        "cards": lambda: _cards(db, start, end),
        "counterparties": lambda: _counterparties(db, start, end),
    }
    return builders[kind]()


# ---------- renderização ----------

def render_csv(table: Table) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow([c.label for c in table.columns])
    for row in [*table.rows, *([table.total] if table.total else [])]:
        w.writerow([cell_text(v, c.type) for v, c in zip(row, table.columns, strict=True)])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def _render(tables: list[Table], fmt: str) -> bytes:
    if fmt == "csv":
        return render_csv(tables[0])
    if fmt == "xlsx":
        from app.domains.reporting.xlsx import render_xlsx

        return render_xlsx(tables)
    from app.domains.reporting.pdf import render_pdf

    return render_pdf(tables)


def export_file(
    db: Session, kind: str, fmt: str, start: date, end: date, basis: str, request_id: str | None
) -> tuple[str, bytes, int]:
    """Gera o arquivo e registra a exportação. Retorna (nome do arquivo, bytes, linhas)."""
    reports.validate_range(start, end)
    table = build_table(db, kind, start, end, basis)
    audit(
        db, "export", uuid.uuid4(), fmt, None,
        {"kind": kind, "format": fmt, "from": start, "to": end, "basis": basis, "rows": table.row_count},
        request_id,
    )
    name = f"finance-hub-{kind}-{start:%Y%m%d}-{end:%Y%m%d}.{fmt}"
    return name, _render([table], fmt), table.row_count


def export_bundle(
    db: Session, start: date, end: date, basis: str, request_id: str | None
) -> tuple[str, bytes, int]:
    """Pacote completo em XLSX: uma aba por tipo de exportação, mesmo período."""
    reports.validate_range(start, end)
    tables = [build_table(db, kind, start, end, basis) for kind in KINDS]
    total_rows = sum(t.row_count for t in tables)
    audit(
        db, "export", uuid.uuid4(), "xlsx", None,
        {"kind": "bundle", "format": "xlsx", "from": start, "to": end, "basis": basis, "rows": total_rows,
         "sheets": [t.kind for t in tables]},
        request_id,
    )
    name = f"finance-hub-completo-{start:%Y%m%d}-{end:%Y%m%d}.xlsx"
    return name, _render(tables, "xlsx"), total_rows


def export_csv(
    db: Session, kind: str, start: date, end: date, basis: str, request_id: str | None
) -> tuple[str, bytes, int]:
    """Compatibilidade: CSV como antes."""
    return export_file(db, kind, "csv", start, end, basis, request_id)
