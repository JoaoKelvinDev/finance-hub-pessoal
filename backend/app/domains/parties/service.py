"""Valores com terceiros: empréstimos, adiantamentos, dívidas e acertos.

Regras (docs/FINANCIAL_RULES.md e FINANCE_HUB_PESSOAL.md §8):
- Empréstimo concedido/adiantamento: LOAN_OUT (−) + a receber. Empréstimo tomado: LOAN_IN (+) + a devolver.
- Acertos: SETTLEMENT_IN (+) reduz o a receber; SETTLEMENT_OUT (−) reduz o a devolver.
- Nenhum desses kinds é receita ou despesa (dashboard filtra por kind).
- Saldo em aberto = principal + encargos − descontos − acertos ativos; nunca negativo.
- Dívidas em sentidos opostos com a mesma pessoa NÃO são compensadas automaticamente.
"""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, NotFound
from app.domains.ledger import rules as ledger_rules
from app.domains.ledger.service import TX_AUDIT_FIELDS, _active_account, _check_date
from app.domains.money import format_brl
from app.domains.support import audit, run_idempotent, snapshot, today_local
from app.models import (
    ExpenseSplit,
    ExpenseSplitPart,
    PartyAdjustment,
    PartyBalance,
    PartySettlement,
    Person,
    Transaction,
)
from app.schemas.parties import (
    CASH_ORIGINS,
    DIRECTION_BY_ORIGIN,
    AdjustmentCreate,
    AdjustmentOut,
    PartyBalanceCreate,
    PartyBalanceDetail,
    PartyBalanceOut,
    PartySummary,
    SettlementCreate,
    SettlementOut,
)

BALANCE_FIELDS = (
    "person_id", "direction", "origin_type", "description", "principal_cents",
    "operation_date", "due_date", "account_id", "origin_transaction_id", "cancelled_at",
)
ORIGIN_LABEL = {
    "LOAN_GIVEN": "Empréstimo para",
    "ADVANCE": "Pago por",
    "LOAN_TAKEN": "Empréstimo de",
}


# ---------- agregados (sem N+1) ----------

class _Agg:
    __slots__ = ("charges", "discounts", "from_split", "settled")

    def __init__(self) -> None:
        self.charges = 0
        self.discounts = 0
        self.settled = 0
        self.from_split = False


def aggregates(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, _Agg]:
    out: dict[uuid.UUID, _Agg] = defaultdict(_Agg)
    if not ids:
        return out
    for bid, kind, total in db.execute(
        select(PartyAdjustment.party_balance_id, PartyAdjustment.kind, func.sum(PartyAdjustment.amount_cents))
        .where(PartyAdjustment.party_balance_id.in_(ids), PartyAdjustment.reversed_at.is_(None))
        .group_by(PartyAdjustment.party_balance_id, PartyAdjustment.kind)
    ):
        if kind == "CHARGE":
            out[bid].charges = int(total)
        else:
            out[bid].discounts = int(total)
    for bid, total in db.execute(
        select(PartySettlement.party_balance_id, func.sum(PartySettlement.amount_cents))
        .where(PartySettlement.party_balance_id.in_(ids), PartySettlement.reversed_at.is_(None))
        .group_by(PartySettlement.party_balance_id)
    ):
        out[bid].settled = int(total)
    for (bid,) in db.execute(
        select(ExpenseSplitPart.party_balance_id)
        .join(ExpenseSplit, ExpenseSplit.id == ExpenseSplitPart.split_id)
        .where(ExpenseSplitPart.party_balance_id.in_(ids), ExpenseSplit.cancelled_at.is_(None))
    ):
        out[bid].from_split = True
    return out


def _open_cents(b: PartyBalance, agg: _Agg) -> int:
    return max(b.principal_cents + agg.charges - agg.discounts - agg.settled, 0)


def derive_status(b: PartyBalance, agg: _Agg, today: date) -> str:
    if b.cancelled_at is not None:
        return "CANCELLED"
    open_ = _open_cents(b, agg)
    if open_ == 0:
        return "SETTLED"
    if b.due_date and b.due_date < today:
        return "OVERDUE"
    if agg.settled > 0 or agg.discounts > 0:
        return "PARTIALLY_SETTLED"
    return "OPEN"


def to_out(b: PartyBalance, agg: _Agg, today: date) -> PartyBalanceOut:
    return PartyBalanceOut(
        id=b.id,
        person_id=b.person_id,
        person_name=b.person.display_name,
        direction=b.direction,
        origin_type=b.origin_type,
        description=b.description,
        principal_cents=b.principal_cents,
        charges_cents=agg.charges,
        discounts_cents=agg.discounts,
        settled_cents=agg.settled,
        open_cents=0 if b.cancelled_at else _open_cents(b, agg),
        operation_date=b.operation_date,
        due_date=b.due_date,
        account_id=b.account_id,
        account_name=b.account.name if b.account else None,
        origin_transaction_id=b.origin_transaction_id,
        status=derive_status(b, agg, today),
        from_split=agg.from_split,
        notes=b.notes,
        cancel_reason=b.cancel_reason,
        created_at=b.created_at,
    )


def to_detail(db: Session, b: PartyBalance, agg: _Agg, today: date) -> PartyBalanceDetail:
    settlements = db.scalars(
        select(PartySettlement)
        .where(PartySettlement.party_balance_id == b.id)
        .order_by(PartySettlement.settled_on.desc(), PartySettlement.created_at.desc())
    ).all()
    adjustments = db.scalars(
        select(PartyAdjustment)
        .where(PartyAdjustment.party_balance_id == b.id, PartyAdjustment.reversed_at.is_(None))
        .order_by(PartyAdjustment.applied_on.desc(), PartyAdjustment.created_at.desc())
    ).all()
    return PartyBalanceDetail(
        **to_out(b, agg, today).model_dump(),
        settlements=[
            SettlementOut(
                id=s.id,
                party_balance_id=s.party_balance_id,
                transaction_id=s.transaction_id,
                account_id=s.transaction.account_id,
                account_name=s.transaction.account.name,
                amount_cents=s.amount_cents,
                settled_on=s.settled_on,
                notes=s.notes,
                reversed_at=s.reversed_at,
                reverse_reason=s.reverse_reason,
                created_at=s.created_at,
            )
            for s in settlements
        ],
        adjustments=[AdjustmentOut.model_validate(a, from_attributes=True) for a in adjustments],
    )


def summarize(items: list[PartyBalanceOut]) -> PartySummary:
    s = PartySummary(
        receivable_open_cents=0, payable_open_cents=0,
        receivable_overdue_cents=0, payable_overdue_cents=0, open_count=0,
    )
    for i in items:
        if i.status in ("CANCELLED", "SETTLED"):
            continue
        s.open_count += 1
        if i.direction == "RECEIVABLE":
            s.receivable_open_cents += i.open_cents
            if i.status == "OVERDUE":
                s.receivable_overdue_cents += i.open_cents
        else:
            s.payable_open_cents += i.open_cents
            if i.status == "OVERDUE":
                s.payable_overdue_cents += i.open_cents
    return s


# ---------- leitura ----------

def get_balance(db: Session, balance_id: uuid.UUID, lock: bool = False) -> PartyBalance:
    q = select(PartyBalance).where(PartyBalance.id == balance_id)
    if lock:
        # FOR UPDATE não pode ser usado com o LEFT JOIN do eager load de `account`.
        q = q.with_for_update(of=PartyBalance)
    b = db.scalar(q)
    if b is None:
        raise NotFound("Registro com terceiro")
    return b


def list_balances(
    db: Session,
    person_id: uuid.UUID | None = None,
    direction: str | None = None,
    include_cancelled: bool = False,
) -> list[PartyBalanceOut]:
    q = select(PartyBalance).order_by(
        PartyBalance.due_date.is_(None), PartyBalance.due_date, PartyBalance.operation_date.desc()
    )
    if person_id:
        q = q.where(PartyBalance.person_id == person_id)
    if direction:
        q = q.where(PartyBalance.direction == direction)
    if not include_cancelled:
        q = q.where(PartyBalance.cancelled_at.is_(None))
    rows = db.scalars(q).unique().all()
    aggs = aggregates(db, [b.id for b in rows])
    today = today_local()
    return [to_out(b, aggs[b.id], today) for b in rows]


def balance_detail(db: Session, balance_id: uuid.UUID) -> PartyBalanceDetail:
    b = get_balance(db, balance_id)
    return to_detail(db, b, aggregates(db, [b.id])[b.id], today_local())


def person_details(db: Session, person_id: uuid.UUID) -> list[PartyBalanceDetail]:
    rows = db.scalars(
        select(PartyBalance)
        .where(PartyBalance.person_id == person_id)
        .order_by(PartyBalance.cancelled_at.is_not(None), PartyBalance.operation_date.desc())
    ).unique().all()
    aggs = aggregates(db, [b.id for b in rows])
    today = today_local()
    return [to_detail(db, b, aggs[b.id], today) for b in rows]


def open_totals(db: Session) -> tuple[int, int]:
    """(a receber em aberto, a devolver em aberto) — usado pelo dashboard."""
    s = summarize(list_balances(db))
    return s.receivable_open_cents, s.payable_open_cents


# ---------- escrita ----------

def _cash_tx(
    db: Session,
    *,
    account_id: uuid.UUID,
    kind: str,
    amount_cents: int,
    effective_date: date,
    description: str,
    person_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
    request_id: str | None,
) -> Transaction:
    acc = _active_account(db, account_id, lock=True)
    _check_date(acc, effective_date)
    ledger_rules.validate_status_date("POSTED", effective_date, today_local())
    sign = 1 if kind in ("LOAN_IN", "SETTLEMENT_IN") else -1
    tx = Transaction(
        account_id=acc.id,
        amount_cents=sign * amount_cents,
        kind=kind,
        status="POSTED",
        effective_date=effective_date,
        description=description[:160],
        counterparty_id=person_id,
        source_type=source_type,
        source_id=source_id,
    )
    db.add(tx)
    db.flush()
    audit(db, "transaction", tx.id, "create", None, snapshot(tx, TX_AUDIT_FIELDS), request_id)
    return tx


def create_balance(db: Session, data: PartyBalanceCreate, request_id: str | None) -> tuple[uuid.UUID, bool]:
    payload = data.model_dump(exclude={"idempotency_key"})

    def _create() -> uuid.UUID:
        person = db.get(Person, data.person_id)
        if person is None:
            raise NotFound("Pessoa")
        if person.archived_at is not None:
            raise DomainError("person_archived", f"O contato '{person.display_name}' está arquivado.")

        balance_id = uuid.uuid4()
        tx_id = None
        if data.origin_type in CASH_ORIGINS:
            kind = "LOAN_IN" if data.origin_type == "LOAN_TAKEN" else "LOAN_OUT"
            tx = _cash_tx(
                db,
                account_id=data.account_id,
                kind=kind,
                amount_cents=data.principal_cents,
                effective_date=data.operation_date,
                description=f"{ORIGIN_LABEL[data.origin_type]} {person.display_name}: {data.description}",
                person_id=person.id,
                source_type="party_balance",
                source_id=balance_id,
                request_id=request_id,
            )
            tx_id = tx.id

        b = PartyBalance(
            id=balance_id,
            person_id=person.id,
            direction=DIRECTION_BY_ORIGIN[data.origin_type],
            origin_type=data.origin_type,
            description=data.description,
            principal_cents=data.principal_cents,
            operation_date=data.operation_date,
            due_date=data.due_date,
            account_id=data.account_id,
            origin_transaction_id=tx_id,
            notes=data.notes,
        )
        db.add(b)
        db.flush()
        audit(db, "party_balance", b.id, "create", None, snapshot(b, BALANCE_FIELDS), request_id)
        return b.id

    return run_idempotent(db, data.idempotency_key, "party_balance.create", payload, _create)


def _require_open(db: Session, b: PartyBalance) -> _Agg:
    if b.cancelled_at is not None:
        raise DomainError("balance_cancelled", "Este registro está cancelado.", status_code=409)
    return aggregates(db, [b.id])[b.id]


def settle(
    db: Session, balance_id: uuid.UUID, data: SettlementCreate, request_id: str | None
) -> tuple[uuid.UUID, bool]:
    payload = {"balance_id": balance_id, **data.model_dump(exclude={"idempotency_key"})}

    def _create() -> uuid.UUID:
        b = get_balance(db, balance_id, lock=True)
        agg = _require_open(db, b)
        open_ = _open_cents(b, agg)
        if open_ == 0:
            raise DomainError("already_settled", "Este registro já está quitado.", status_code=409)
        if data.amount_cents > open_:
            raise DomainError(
                "amount_exceeds_open",
                f"O valor excede o saldo em aberto ({format_brl(open_)}).",
                details={"open_cents": open_},
            )
        if data.settled_on < b.operation_date:
            raise DomainError("settled_before_operation", "O acerto não pode ser anterior à operação.")

        settlement_id = uuid.uuid4()
        receivable = b.direction == "RECEIVABLE"
        tx = _cash_tx(
            db,
            account_id=data.account_id,
            kind="SETTLEMENT_IN" if receivable else "SETTLEMENT_OUT",
            amount_cents=data.amount_cents,
            effective_date=data.settled_on,
            description=f"{'Recebido de' if receivable else 'Pago a'} {b.person.display_name}: {b.description}",
            person_id=b.person_id,
            source_type="party_settlement",
            source_id=settlement_id,
            request_id=request_id,
        )
        s = PartySettlement(
            id=settlement_id,
            party_balance_id=b.id,
            transaction_id=tx.id,
            amount_cents=data.amount_cents,
            settled_on=data.settled_on,
            notes=data.notes,
        )
        db.add(s)
        db.flush()
        audit(
            db, "party_settlement", s.id, "create", None,
            {"balance_id": b.id, "amount_cents": s.amount_cents, "settled_on": s.settled_on, "transaction_id": tx.id},
            request_id,
        )
        return s.id

    return run_idempotent(db, data.idempotency_key, "party_balance.settle", payload, _create)


def reverse_settlement(db: Session, settlement_id: uuid.UUID, reason: str, request_id: str | None) -> PartySettlement:
    s = db.get(PartySettlement, settlement_id)
    if s is None:
        raise NotFound("Acerto")
    b = get_balance(db, s.party_balance_id, lock=True)
    if b.cancelled_at is not None:
        raise DomainError("balance_cancelled", "Este registro está cancelado.", status_code=409)
    if s.reversed_at is not None:
        raise DomainError("already_reversed", "Este acerto já foi estornado.", status_code=409)

    now = datetime.now(UTC)
    tx = s.transaction
    before = snapshot(tx, TX_AUDIT_FIELDS)
    tx.status = "CANCELLED"
    tx.cancelled_at = now
    tx.cancel_reason = f"Estorno de acerto: {reason}"[:200]
    audit(db, "transaction", tx.id, "cancel", before, {"status": "CANCELLED", "reason": reason}, request_id)

    s.reversed_at = now
    s.reverse_reason = reason
    audit(db, "party_settlement", s.id, "reverse", None, {"reason": reason}, request_id)
    db.flush()
    return s


def adjust(
    db: Session, balance_id: uuid.UUID, data: AdjustmentCreate, request_id: str | None
) -> tuple[uuid.UUID, bool]:
    payload = {"balance_id": balance_id, **data.model_dump(exclude={"idempotency_key"})}

    def _create() -> uuid.UUID:
        b = get_balance(db, balance_id, lock=True)
        agg = _require_open(db, b)
        if data.kind == "DISCOUNT":
            open_ = _open_cents(b, agg)
            if data.amount_cents > open_:
                raise DomainError(
                    "amount_exceeds_open", "O desconto excede o saldo em aberto.", details={"open_cents": open_}
                )
        if data.applied_on < b.operation_date:
            raise DomainError("adjustment_before_operation", "O ajuste não pode ser anterior à operação.")
        a = PartyAdjustment(
            party_balance_id=b.id,
            kind=data.kind,
            amount_cents=data.amount_cents,
            applied_on=data.applied_on,
            reason=data.reason,
        )
        db.add(a)
        db.flush()
        audit(db, "party_adjustment", a.id, "create", None, payload, request_id)
        return a.id

    return run_idempotent(db, data.idempotency_key, "party_balance.adjust", payload, _create)


def cancel_balance(
    db: Session, balance_id: uuid.UUID, reason: str, request_id: str | None, *, from_split: bool = False
) -> PartyBalance:
    b = get_balance(db, balance_id, lock=True)
    if b.cancelled_at is not None:
        raise DomainError("already_cancelled", "Este registro já está cancelado.", status_code=409)
    if not from_split and db.scalar(
        select(func.count())
        .select_from(ExpenseSplitPart)
        .join(ExpenseSplit, ExpenseSplit.id == ExpenseSplitPart.split_id)
        .where(ExpenseSplitPart.party_balance_id == b.id, ExpenseSplit.cancelled_at.is_(None))
    ):
        raise DomainError(
            "managed_by_split",
            "Este valor vem de um rateio de conta da casa; desfaça o rateio por lá.",
            status_code=409,
        )
    active = db.scalar(
        select(func.count()).where(PartySettlement.party_balance_id == b.id, PartySettlement.reversed_at.is_(None))
    )
    if active:
        raise DomainError(
            "has_settlements", "Estorne os acertos antes de cancelar o registro.", status_code=409
        )

    now = datetime.now(UTC)
    before = snapshot(b, BALANCE_FIELDS)
    if b.origin_transaction_id:
        tx = db.get(Transaction, b.origin_transaction_id)
        if tx and tx.status != "CANCELLED":
            tx_before = snapshot(tx, TX_AUDIT_FIELDS)
            tx.status = "CANCELLED"
            tx.cancelled_at = now
            tx.cancel_reason = f"Registro com terceiro cancelado: {reason}"[:200]
            audit(db, "transaction", tx.id, "cancel", tx_before, {"status": "CANCELLED", "reason": reason}, request_id)
    b.cancelled_at = now
    b.cancel_reason = reason
    audit(db, "party_balance", b.id, "cancel", before, {"reason": reason}, request_id)
    db.flush()
    return b
