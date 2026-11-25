"""Calendário financeiro: visão unificada de compromissos, sem dupla contagem.

Fontes consolidadas (cada evento tem chave única `origem:id`):
- Faturas de cartão (vencimento; valor = total - pago).
- Parcelas de contas da casa materializadas.
- Ocorrências futuras de recorrências ativas ainda NÃO materializadas (previsão
  virtual, nada é gravado). Descartadas quando já existe parcela com o mesmo
  (recurrence_id, due_date), em qualquer status.
- Lançamentos PLANNED de receita/despesa.

Pagamentos (transações POSTED vinculadas) não viram eventos próprios: o pagamento
aparece como situação "PAID" do próprio compromisso.
"""

from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.domains.bills.rules import generate_installment_dates
from app.domains.cards.rules import derive_statement_status
from app.domains.parties.service import aggregates as party_aggregates
from app.domains.parties.service import to_out as party_to_out
from app.domains.support import today_local
from app.models.entities import (
    Bill,
    BillInstallment,
    BillRecurrence,
    CardInstallment,
    CardStatement,
    CreditCard,
    PartyBalance,
    Transaction,
)
from app.schemas.calendar import CalendarDay, CalendarEvent, CalendarResponse, CalendarSummary

MAX_RANGE_DAYS = 92
# Teto de ocorrências geradas por recorrência (50 anos de mensais) — proteção contra laço.
_MAX_OCCURRENCES = 600

_OPEN_STATUSES = ("PENDING", "OVERDUE", "PARTIAL", "FORECAST")


def _validate_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise DomainError("invalid_range", "A data final deve ser igual ou posterior à inicial.")
    if (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
        raise DomainError("range_too_large", f"O intervalo máximo é de {MAX_RANGE_DAYS} dias.")


def _statement_events(db: Session, date_from: date, date_to: date, today: date) -> list[CalendarEvent]:
    totals = (
        select(
            CardInstallment.statement_id.label("sid"),
            func.coalesce(func.sum(CardInstallment.amount_cents), 0).label("total"),
        )
        .where(CardInstallment.status.notin_(("REVERSED", "CANCELLED")))
        .group_by(CardInstallment.statement_id)
        .subquery()
    )
    rows = db.execute(
        select(CardStatement, CreditCard, func.coalesce(totals.c.total, 0))
        .join(CreditCard, CreditCard.id == CardStatement.card_id)
        .outerjoin(totals, totals.c.sid == CardStatement.id)
        .where(
            CardStatement.due_date.between(date_from, date_to),
            CardStatement.status != "CANCELLED",
        )
    ).all()

    events = []
    for stmt, card, total in rows:
        total = int(total)
        if total == 0 and stmt.paid_cents == 0:
            continue
        derived = derive_statement_status(stmt.paid_cents, total, stmt.due_date, today)
        status = {"PAID": "PAID", "PARTIALLY_PAID": "PARTIAL", "OVERDUE": "OVERDUE"}.get(derived, "PENDING")
        if status == "PARTIAL" and stmt.due_date < today:
            status = "OVERDUE"
        events.append(
            CalendarEvent(
                key=f"statement:{stmt.id}",
                source="CARD_STATEMENT",
                source_id=stmt.id,
                ref_id=card.id,
                date=stmt.due_date,
                title=f"Fatura {card.nickname or card.name}",
                subtitle=card.bank,
                direction="OUT",
                amount_cents=total,
                open_cents=max(total - stmt.paid_cents, 0),
                status=status,
                color=card.color,
            )
        )
    return events


def _bill_events(db: Session, date_from: date, date_to: date, today: date) -> list[CalendarEvent]:
    rows = db.execute(
        select(BillInstallment, Bill)
        .join(Bill, Bill.id == BillInstallment.bill_id)
        .where(
            BillInstallment.due_date.between(date_from, date_to),
            BillInstallment.status != "CANCELLED",
        )
    ).all()

    events = []
    for inst, bill in rows:
        if inst.status == "PAID":
            status, open_cents = "PAID", 0
        elif inst.status in ("SKIPPED", "REVERSED"):
            status, open_cents = inst.status, 0
        else:  # PENDING / POSTED
            status = "OVERDUE" if inst.due_date < today else "PENDING"
            open_cents = inst.amount_cents
        events.append(
            CalendarEvent(
                key=f"bill_installment:{inst.id}",
                source="BILL_INSTALLMENT",
                source_id=inst.id,
                ref_id=bill.id,
                date=inst.due_date,
                title=bill.name,
                subtitle=bill.category,
                direction="OUT",
                amount_cents=inst.amount_cents,
                open_cents=open_cents,
                status=status,
                color=bill.color,
            )
        )
    return events


def _forecast_events(db: Session, date_from: date, date_to: date) -> list[CalendarEvent]:
    rows = db.execute(
        select(BillRecurrence, Bill)
        .join(Bill, Bill.id == BillRecurrence.bill_id)
        .where(
            BillRecurrence.status == "ACTIVE",
            Bill.archived_at.is_(None),
            BillRecurrence.start_date <= date_to,
            (BillRecurrence.end_date.is_(None)) | (BillRecurrence.end_date >= date_from),
        )
    ).all()
    if not rows:
        return []

    rec_ids = [rec.id for rec, _ in rows]
    materialized = {
        (rid, due)
        for rid, due in db.execute(
            select(BillInstallment.recurrence_id, BillInstallment.due_date).where(
                BillInstallment.recurrence_id.in_(rec_ids)
            )
        ).all()
    }

    events = []
    for rec, bill in rows:
        limit = min(rec.end_date, date_to) if rec.end_date else date_to
        dates = generate_installment_dates(
            start_date=rec.start_date,
            frequency=rec.frequency,
            day_of_month=rec.day_of_month,
            end_date=limit,
            custom_months_interval=rec.custom_months_interval,
            max_count=_MAX_OCCURRENCES,
        )
        for due in dates:
            if due < date_from or (rec.id, due) in materialized:
                continue
            events.append(
                CalendarEvent(
                    key=f"recurrence:{rec.id}:{due.isoformat()}",
                    source="RECURRENCE_FORECAST",
                    source_id=rec.id,
                    ref_id=bill.id,
                    date=due,
                    title=bill.name,
                    subtitle="Previsão de recorrência",
                    direction="OUT",
                    amount_cents=bill.default_amount_cents,
                    open_cents=bill.default_amount_cents,
                    status="FORECAST",
                    color=bill.color,
                )
            )
    return events


def _planned_events(db: Session, date_from: date, date_to: date, today: date) -> list[CalendarEvent]:
    txs = db.scalars(
        select(Transaction).where(
            Transaction.status == "PLANNED",
            Transaction.kind.in_(("INCOME", "EXPENSE")),
            Transaction.effective_date.between(date_from, date_to),
        )
    ).all()
    events = []
    for tx in txs:
        amount = abs(tx.amount_cents)
        events.append(
            CalendarEvent(
                key=f"transaction:{tx.id}",
                source="PLANNED_TRANSACTION",
                source_id=tx.id,
                ref_id=tx.account_id,
                date=tx.effective_date,
                title=tx.description,
                subtitle=tx.category.name if tx.category else tx.account.name,
                direction="IN" if tx.kind == "INCOME" else "OUT",
                amount_cents=amount,
                open_cents=amount,
                status="OVERDUE" if tx.effective_date < today else "PENDING",
                color=tx.category.color if tx.category else tx.account.color,
            )
        )
    return events


def _party_events(db: Session, date_from: date, date_to: date, today: date) -> list[CalendarEvent]:
    rows = db.scalars(
        select(PartyBalance).where(
            PartyBalance.cancelled_at.is_(None),
            PartyBalance.due_date.between(date_from, date_to),
        )
    ).unique().all()
    aggs = party_aggregates(db, [b.id for b in rows])
    status_map = {"SETTLED": "PAID", "OVERDUE": "OVERDUE", "PARTIALLY_SETTLED": "PARTIAL"}
    events = []
    for b in rows:
        out = party_to_out(b, aggs[b.id], today)
        receivable = b.direction == "RECEIVABLE"
        events.append(
            CalendarEvent(
                key=f"party_balance:{b.id}",
                source="PARTY_BALANCE",
                source_id=b.id,
                ref_id=b.person_id,
                date=b.due_date,
                title=f"{'Receber de' if receivable else 'Pagar a'} {out.person_name}",
                subtitle=b.description,
                direction="IN" if receivable else "OUT",
                amount_cents=out.principal_cents + out.charges_cents - out.discounts_cents,
                open_cents=out.open_cents,
                status=status_map.get(out.status, "PENDING"),
                color="#0EA5E9" if receivable else "#F97316",
            )
        )
    return events


_STATUS_ORDER = {"OVERDUE": 0, "PARTIAL": 1, "PENDING": 2, "FORECAST": 3, "PAID": 4, "SKIPPED": 5, "REVERSED": 6}


def build_calendar(db: Session, date_from: date, date_to: date) -> CalendarResponse:
    _validate_range(date_from, date_to)
    today = today_local()

    events = (
        _statement_events(db, date_from, date_to, today)
        + _bill_events(db, date_from, date_to, today)
        + _forecast_events(db, date_from, date_to)
        + _planned_events(db, date_from, date_to, today)
        + _party_events(db, date_from, date_to, today)
    )
    # Defesa extra: nenhuma chave repetida chega ao cliente.
    unique = {e.key: e for e in events}
    events = sorted(unique.values(), key=lambda e: (e.date, _STATUS_ORDER.get(e.status, 9), -e.open_cents, e.title))

    summary = CalendarSummary(
        to_pay_cents=0, to_receive_cents=0, paid_cents=0, overdue_cents=0, overdue_count=0, event_count=len(events)
    )
    per_day: dict[date, dict[str, int]] = defaultdict(lambda: {"out_cents": 0, "in_cents": 0, "count": 0})
    for e in events:
        day = per_day[e.date]
        day["count"] += 1
        if e.status in _OPEN_STATUSES:
            if e.direction == "OUT":
                summary.to_pay_cents += e.open_cents
                day["out_cents"] += e.open_cents
            else:
                summary.to_receive_cents += e.open_cents
                day["in_cents"] += e.open_cents
        if e.status == "OVERDUE":
            summary.overdue_cents += e.open_cents
            summary.overdue_count += 1
        paid_part = e.amount_cents - e.open_cents if e.status in ("PAID", "PARTIAL", "OVERDUE") else 0
        if e.direction == "OUT" and paid_part > 0:
            summary.paid_cents += paid_part

    days = [CalendarDay(date=d, **v) for d, v in sorted(per_day.items())]
    return CalendarResponse(
        date_from=date_from, date_to=date_to, today=today, summary=summary, days=days, events=events
    )
