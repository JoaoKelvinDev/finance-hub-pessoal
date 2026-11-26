"""Relatórios: categorias, fluxo de caixa, cartões e terceiros.

Regras (docs/FINANCIAL_RULES.md):
- Consumo por categoria usa a mesma fonte dos orçamentos (`consumption_by_category`).
- Fluxo de caixa: só INCOME/EXPENSE efetivados. Pagamento de fatura e de conta da casa
  são saídas de caixa reais; transferências, empréstimos e acertos não entram.
- Totais são calculados sobre exatamente as linhas devolvidas.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.domains.ledger.rules import EXPENSE_KINDS, INCOME_KINDS
from app.domains.money import pct_change
from app.domains.parties import service as parties
from app.domains.planning.service import consumption_by_category
from app.domains.support import today_local
from app.models import (
    CardInstallment,
    CardPurchase,
    CardStatement,
    Category,
    CreditCard,
    PartySettlement,
    StatementPayment,
    Transaction,
)
from app.schemas.reports import (
    AgingBuckets,
    CardReport,
    CardReportRow,
    CashFlowPoint,
    CashFlowReport,
    CategoryReport,
    CategoryRow,
    CounterpartyReport,
    CounterpartyRow,
    MerchantRow,
)

MAX_RANGE_DAYS = 731
UNCATEGORIZED_COLOR = "#71717A"


def validate_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise DomainError("invalid_range", "A data final deve ser igual ou posterior à inicial.")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise DomainError("range_too_large", "O período máximo é de 2 anos.")


def _share(part: int, total: int) -> float:
    return round(part * 100 / total, 1) if total else 0.0


# ---------- categorias ----------

def category_report(db: Session, date_from: date, date_to: date, basis: str) -> CategoryReport:
    validate_range(date_from, date_to)
    span = date_to - date_from
    prev_to = date_from - timedelta(days=1)
    prev_from = prev_to - span

    current = consumption_by_category(db, date_from, date_to, basis)
    previous = consumption_by_category(db, prev_from, prev_to, basis)

    cats = {c.id: c for c in db.scalars(select(Category).where(Category.kind == "EXPENSE"))}

    def root_of(cid: uuid.UUID | None) -> uuid.UUID | None:
        c = cats.get(cid) if cid else None
        while c is not None and c.parent_id is not None and c.parent_id in cats:
            c = cats[c.parent_id]
        return c.id if c else None

    # Agrupa por raiz; guarda o detalhe por subcategoria.
    by_root: dict[uuid.UUID | None, dict[uuid.UUID | None, list[int]]] = defaultdict(dict)
    for source, idx in ((current, 0), (previous, 1)):
        for cid, cents in source.items():
            leaf = cid if cid in cats else None
            pair = by_root[root_of(leaf)].setdefault(leaf, [0, 0])
            pair[idx] += cents

    total = sum(current.values())
    prev_total = sum(previous.values())

    def row(cid: uuid.UUID | None, amount: int, prev: int, children: list[CategoryRow]) -> CategoryRow:
        cat = cats.get(cid) if cid else None
        return CategoryRow(
            category_id=cid,
            name=cat.name if cat else "Sem categoria",
            color=cat.color if cat else UNCATEGORIZED_COLOR,
            amount_cents=amount,
            previous_cents=prev,
            share_pct=_share(amount, total),
            change_pct=pct_change(amount, prev),
            children=children,
        )

    rows: list[CategoryRow] = []
    for root_id, leaves in by_root.items():
        amount = sum(v[0] for v in leaves.values())
        prev = sum(v[1] for v in leaves.values())
        children = [
            row(leaf, v[0], v[1], [])
            for leaf, v in sorted(leaves.items(), key=lambda kv: -kv[1][0])
            if leaf != root_id and (v[0] or v[1])
        ]
        if amount or prev:
            rows.append(row(root_id, amount, prev, children))
    rows.sort(key=lambda r: (-r.amount_cents, r.name))

    return CategoryReport(
        date_from=date_from,
        date_to=date_to,
        previous_from=prev_from,
        previous_to=prev_to,
        basis=basis,
        total_cents=total,
        previous_total_cents=prev_total,
        rows=rows,
    )


# ---------- fluxo de caixa ----------

def cash_flow_report(db: Session, date_from: date, date_to: date) -> CashFlowReport:
    validate_range(date_from, date_to)
    # Até 62 dias: diário; acima: mensal.
    daily = (date_to - date_from).days <= 62
    bucket = (
        func.to_char(Transaction.effective_date, "YYYY-MM-DD")
        if daily
        else func.to_char(Transaction.effective_date, "YYYY-MM")
    )
    rows = db.execute(
        select(bucket, Transaction.kind, func.sum(Transaction.amount_cents))
        .where(
            Transaction.status == "POSTED",
            Transaction.kind.in_(INCOME_KINDS + EXPENSE_KINDS),
            Transaction.effective_date.between(date_from, date_to),
        )
        .group_by(bucket, Transaction.kind)
    ).all()
    agg: dict[str, dict[str, int]] = defaultdict(dict)
    for key, kind, total in rows:
        agg[key][kind] = abs(int(total))

    keys: list[str] = []
    if daily:
        d = date_from
        while d <= date_to:
            keys.append(d.isoformat())
            d += timedelta(days=1)
    else:
        y, m = date_from.year, date_from.month
        while (y, m) <= (date_to.year, date_to.month):
            keys.append(f"{y:04d}-{m:02d}")
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)

    points = []
    for k in keys:
        inc = agg.get(k, {}).get("INCOME", 0)
        exp = agg.get(k, {}).get("EXPENSE", 0)
        points.append(CashFlowPoint(period=k, income_cents=inc, expense_cents=exp, net_cents=inc - exp))
    income = sum(p.income_cents for p in points)
    expense = sum(p.expense_cents for p in points)
    return CashFlowReport(
        date_from=date_from,
        date_to=date_to,
        granularity="day" if daily else "month",
        income_cents=income,
        expense_cents=expense,
        net_cents=income - expense,
        points=points,
    )


# ---------- cartões ----------

def card_report(db: Session, date_from: date, date_to: date) -> CardReport:
    validate_range(date_from, date_to)
    today = today_local()
    live = CardInstallment.status.notin_(("REVERSED", "CANCELLED"))

    purchases = {
        cid: (int(total or 0), int(count or 0))
        for cid, total, count in db.execute(
            select(CardPurchase.card_id, func.sum(CardInstallment.amount_cents), func.count(func.distinct(CardPurchase.id)))
            .join(CardInstallment, CardInstallment.purchase_id == CardPurchase.id)
            .where(CardPurchase.status == "ACTIVE", CardPurchase.purchased_on.between(date_from, date_to), live)
            .group_by(CardPurchase.card_id)
        ).all()
    }
    paid = {
        cid: int(total or 0)
        for cid, total in db.execute(
            select(CardStatement.card_id, func.sum(StatementPayment.amount_cents))
            .join(CardStatement, CardStatement.id == StatementPayment.statement_id)
            .join(Transaction, Transaction.id == StatementPayment.transaction_id)
            .where(StatementPayment.paid_on.between(date_from, date_to), Transaction.status == "POSTED")
            .group_by(CardStatement.card_id)
        ).all()
    }
    # Dívida atual por fatura (total − pago) e parcelas de faturas que ainda vão vencer.
    stmt_totals = dict(
        db.execute(
            select(CardInstallment.statement_id, func.sum(CardInstallment.amount_cents))
            .where(live)
            .group_by(CardInstallment.statement_id)
        ).all()
    )
    open_by_card: dict[uuid.UUID, int] = defaultdict(int)
    future_by_card: dict[uuid.UUID, int] = defaultdict(int)
    for stmt in db.scalars(select(CardStatement).where(CardStatement.status != "CANCELLED")):
        remaining = max(int(stmt_totals.get(stmt.id, 0) or 0) - stmt.paid_cents, 0)
        open_by_card[stmt.card_id] += remaining
        if stmt.due_date > today:
            future_by_card[stmt.card_id] += remaining

    merchant_label = func.coalesce(func.nullif(func.trim(CardPurchase.merchant), ""), CardPurchase.description)
    merchants: dict[uuid.UUID, list[MerchantRow]] = defaultdict(list)
    for cid, name, total, count in db.execute(
        select(CardPurchase.card_id, merchant_label, func.sum(CardPurchase.total_cents), func.count())
        .where(CardPurchase.status == "ACTIVE", CardPurchase.purchased_on.between(date_from, date_to))
        .group_by(CardPurchase.card_id, merchant_label)
        .order_by(func.sum(CardPurchase.total_cents).desc())
    ).all():
        if len(merchants[cid]) < 5:
            merchants[cid].append(MerchantRow(name=name, amount_cents=int(total), count=int(count)))

    rows = []
    for card in db.scalars(select(CreditCard).order_by(CreditCard.name)):
        p_total, p_count = purchases.get(card.id, (0, 0))
        row = CardReportRow(
            card_id=card.id,
            name=card.nickname or card.name,
            bank=card.bank,
            color=card.color,
            limit_cents=card.limit_cents,
            purchases_cents=p_total,
            purchases_count=p_count,
            paid_cents=paid.get(card.id, 0),
            open_cents=open_by_card.get(card.id, 0),
            future_cents=future_by_card.get(card.id, 0),
            top_merchants=merchants.get(card.id, []),
        )
        # Cartão arquivado sem movimento nem dívida não polui o relatório.
        if card.archived_at is None or row.purchases_cents or row.open_cents or row.paid_cents:
            rows.append(row)

    return CardReport(
        date_from=date_from,
        date_to=date_to,
        purchases_cents=sum(r.purchases_cents for r in rows),
        paid_cents=sum(r.paid_cents for r in rows),
        open_cents=sum(r.open_cents for r in rows),
        future_cents=sum(r.future_cents for r in rows),
        cards=rows,
    )


# ---------- terceiros (aging) ----------

def _empty_aging() -> dict[str, int]:
    return {"current": 0, "d0_30": 0, "d31_60": 0, "d61_90": 0, "d90_plus": 0, "no_due": 0}


def _bucket(due: date | None, today: date) -> str:
    if due is None:
        return "no_due"
    late = (today - due).days
    if late <= 0:
        return "current"
    if late <= 30:
        return "d0_30"
    if late <= 60:
        return "d31_60"
    if late <= 90:
        return "d61_90"
    return "d90_plus"


def _aging(a: dict[str, int]) -> AgingBuckets:
    return AgingBuckets(
        current_cents=a["current"],
        d0_30_cents=a["d0_30"],
        d31_60_cents=a["d31_60"],
        d61_90_cents=a["d61_90"],
        d90_plus_cents=a["d90_plus"],
        no_due_cents=a["no_due"],
    )


def counterparty_report(db: Session, date_from: date, date_to: date) -> CounterpartyReport:
    validate_range(date_from, date_to)
    today = today_local()
    balances = parties.list_balances(db)

    settled = {
        pid: int(total or 0)
        for pid, total in db.execute(
            select(Transaction.counterparty_id, func.sum(PartySettlement.amount_cents))
            .join(Transaction, Transaction.id == PartySettlement.transaction_id)
            .where(
                PartySettlement.reversed_at.is_(None),
                PartySettlement.settled_on.between(date_from, date_to),
            )
            .group_by(Transaction.counterparty_id)
        ).all()
    }

    people: dict[uuid.UUID, dict] = {}
    total_aging = _empty_aging()
    for b in balances:
        if b.status in ("SETTLED", "CANCELLED") or b.open_cents <= 0:
            continue
        p = people.setdefault(
            b.person_id, {"name": b.person_name, "rec": 0, "pay": 0, "aging": _empty_aging()}
        )
        if b.direction == "RECEIVABLE":
            p["rec"] += b.open_cents
            key = _bucket(b.due_date, today)
            p["aging"][key] += b.open_cents
            total_aging[key] += b.open_cents
        else:
            p["pay"] += b.open_cents

    rows = [
        CounterpartyRow(
            person_id=pid,
            name=v["name"],
            receivable_cents=v["rec"],
            payable_cents=v["pay"],
            receivable_aging=_aging(v["aging"]),
            settled_in_period_cents=settled.get(pid, 0),
        )
        for pid, v in people.items()
    ]
    rows.sort(key=lambda r: (-(r.receivable_cents + r.payable_cents), r.name))
    return CounterpartyReport(
        today=today,
        receivable_cents=sum(r.receivable_cents for r in rows),
        payable_cents=sum(r.payable_cents for r in rows),
        receivable_aging=_aging(total_aging),
        people=rows,
    )
