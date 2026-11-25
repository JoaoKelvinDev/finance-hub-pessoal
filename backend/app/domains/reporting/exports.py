"""Exportação CSV pensada para o Excel em português.

- Separador ";" e vírgula decimal (o Excel pt-BR reconhece os valores como número).
- UTF-8 com BOM: acentos abrem corretamente no Excel.
- Datas em dd/mm/aaaa. Valores sem separador de milhar.
- Cada exportação é registrada em audit_events (dados sensíveis).
"""

import csv
import io
import uuid
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


def money(cents: int) -> str:
    """Centavos -> '1234,56' (sem ponto flutuante)."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100},{cents % 100:02d}"


def d(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def _csv(header: list[str], rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(header)
    w.writerows(rows)
    return ("﻿" + buf.getvalue()).encode("utf-8")


def _transactions(db: Session, start: date, end: date):
    txs = db.scalars(
        select(Transaction)
        .where(Transaction.effective_date.between(start, end))
        .order_by(Transaction.effective_date, Transaction.created_at)
    ).unique()
    header = ["Data", "Descrição", "Tipo", "Situação", "Conta", "Categoria", "Pessoa", "Valor (R$)"]
    rows = [
        [
            d(t.effective_date),
            t.description,
            KIND_LABEL.get(t.kind, t.kind),
            STATUS_LABEL.get(t.status, t.status),
            t.account.name,
            t.category.name if t.category else "",
            t.counterparty.display_name if t.counterparty else "",
            money(t.amount_cents),
        ]
        for t in txs
    ]
    return header, rows


def _card_purchases(db: Session, start: date, end: date):
    items = db.scalars(
        select(CardPurchase)
        .where(CardPurchase.purchased_on.between(start, end))
        .order_by(CardPurchase.purchased_on, CardPurchase.created_at)
    ).unique()
    header = ["Data", "Cartão", "Estabelecimento", "Descrição", "Categoria", "Parcelas", "Situação", "Valor (R$)"]
    rows = [
        [
            d(p.purchased_on),
            p.card.nickname or p.card.name,
            p.merchant or "",
            p.description,
            p.category.name if p.category else "",
            str(p.installments_count),
            {"ACTIVE": "Ativa", "REVERSED": "Estornada", "CANCELLED": "Cancelada"}.get(p.status, p.status),
            money(p.total_cents),
        ]
        for p in items
    ]
    return header, rows


def _party_balances(db: Session):
    header = [
        "Pessoa", "Tipo", "Direção", "Descrição", "Data", "Vencimento", "Principal (R$)", "Encargos (R$)",
        "Descontos (R$)", "Acertado (R$)", "Em aberto (R$)", "Situação",
    ]
    rows = [
        [
            b.person_name,
            PARTY_ORIGIN.get(b.origin_type, b.origin_type),
            "A receber" if b.direction == "RECEIVABLE" else "A pagar",
            b.description,
            d(b.operation_date),
            d(b.due_date),
            money(b.principal_cents),
            money(b.charges_cents),
            money(b.discounts_cents),
            money(b.settled_cents),
            money(b.open_cents),
            PARTY_STATUS.get(b.status, b.status),
        ]
        for b in parties.list_balances(db, include_cancelled=True)
    ]
    return header, rows


def _categories(db: Session, start: date, end: date, basis: str):
    r = reports.category_report(db, start, end, basis)
    header = ["Categoria", "Subcategoria", "Valor (R$)", "Período anterior (R$)", "Participação (%)"]
    rows: list[list[str]] = []
    for row in r.rows:
        rows.append([row.name, "", money(row.amount_cents), money(row.previous_cents), f"{row.share_pct}".replace(".", ",")])
        for child in row.children:
            rows.append(
                [row.name, child.name, money(child.amount_cents), money(child.previous_cents),
                 f"{child.share_pct}".replace(".", ",")]
            )
    rows.append(["Total", "", money(r.total_cents), money(r.previous_total_cents), "100"])
    return header, rows


def _cash_flow(db: Session, start: date, end: date):
    r = reports.cash_flow_report(db, start, end)
    header = ["Período", "Receitas (R$)", "Despesas (R$)", "Resultado (R$)"]
    rows = [[p.period, money(p.income_cents), money(p.expense_cents), money(p.net_cents)] for p in r.points]
    rows.append(["Total", money(r.income_cents), money(r.expense_cents), money(r.net_cents)])
    return header, rows


def _cards(db: Session, start: date, end: date):
    r = reports.card_report(db, start, end)
    header = ["Cartão", "Banco", "Compras no período (R$)", "Qtd. compras", "Pago no período (R$)",
              "Em aberto (R$)", "Parcelas futuras (R$)"]
    rows = [
        [c.name, c.bank or "", money(c.purchases_cents), str(c.purchases_count), money(c.paid_cents),
         money(c.open_cents), money(c.future_cents)]
        for c in r.cards
    ]
    return header, rows


def _counterparties(db: Session, start: date, end: date):
    r = reports.counterparty_report(db, start, end)
    header = ["Pessoa", "Me deve (R$)", "Eu devo (R$)", "A vencer (R$)", "Atraso 1–30 (R$)", "Atraso 31–60 (R$)",
              "Atraso 61–90 (R$)", "Atraso 90+ (R$)", "Sem vencimento (R$)", "Recebido no período (R$)"]
    rows = [
        [
            p.name, money(p.receivable_cents), money(p.payable_cents),
            money(p.receivable_aging.current_cents), money(p.receivable_aging.d0_30_cents),
            money(p.receivable_aging.d31_60_cents), money(p.receivable_aging.d61_90_cents),
            money(p.receivable_aging.d90_plus_cents), money(p.receivable_aging.no_due_cents),
            money(p.settled_in_period_cents),
        ]
        for p in r.people
    ]
    return header, rows


def export_csv(
    db: Session, kind: str, start: date, end: date, basis: str, request_id: str | None
) -> tuple[str, bytes, int]:
    """Gera o CSV e registra a exportação. Retorna (nome do arquivo, bytes, linhas)."""
    reports.validate_range(start, end)
    builders = {
        "transactions": lambda: _transactions(db, start, end),
        "card-purchases": lambda: _card_purchases(db, start, end),
        "party-balances": lambda: _party_balances(db),
        "categories": lambda: _categories(db, start, end, basis),
        "cash-flow": lambda: _cash_flow(db, start, end),
        "cards": lambda: _cards(db, start, end),
        "counterparties": lambda: _counterparties(db, start, end),
    }
    header, rows = builders[kind]()
    audit(
        db, "export", uuid.uuid4(), "csv", None,
        {"kind": kind, "from": start, "to": end, "basis": basis, "rows": len(rows)},
        request_id,
    )
    name = f"finance-hub-{kind}-{start:%Y%m%d}-{end:%Y%m%d}.csv"
    return name, _csv(header, rows), len(rows)
