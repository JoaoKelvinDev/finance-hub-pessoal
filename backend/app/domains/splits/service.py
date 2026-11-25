"""Rateio da casa (Fluxo D): uma despesa, um pagamento, um recebível por pessoa.

A despesa original continua bruta. Cada parte alheia vira um PartyBalance OWED_TO_ME
ligado ao rateio; os repasses usam o fluxo de acertos de terceiros.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, NotFound
from app.domains.parties import service as parties
from app.domains.splits.rules import compute_shares
from app.domains.support import audit, run_idempotent, today_local
from app.models import Bill, BillInstallment, ExpenseSplit, ExpenseSplitPart, PartyBalance, Person
from app.schemas.splits import SplitCreate, SplitOut, SplitPartOut

_BLOCKED_STATUSES = ("CANCELLED", "SKIPPED", "REVERSED")


def _installment(db: Session, installment_id: uuid.UUID, lock: bool = False) -> BillInstallment:
    q = select(BillInstallment).where(BillInstallment.id == installment_id)
    if lock:
        q = q.with_for_update()
    inst = db.scalar(q)
    if inst is None:
        raise NotFound("Parcela")
    return inst


def create_split(
    db: Session, installment_id: uuid.UUID, data: SplitCreate, request_id: str | None
) -> tuple[uuid.UUID, bool]:
    payload = {"installment_id": installment_id, **data.model_dump(exclude={"idempotency_key"})}

    def _create() -> uuid.UUID:
        inst = _installment(db, installment_id, lock=True)
        if inst.status in _BLOCKED_STATUSES:
            raise DomainError("installment_closed", "Não é possível ratear uma parcela cancelada, pulada ou estornada.")
        if inst.is_estimate:
            raise DomainError("installment_estimate", "Confirme o valor real da conta antes de ratear.")
        if inst.split is not None:
            raise DomainError("split_exists", "Esta parcela já tem um rateio ativo.", status_code=409)

        people: dict[uuid.UUID, Person] = {}
        for p in data.participants:
            person = db.get(Person, p.person_id)
            if person is None:
                raise NotFound("Pessoa")
            if person.archived_at is not None:
                raise DomainError("person_archived", f"O contato '{person.display_name}' está arquivado.")
            people[person.id] = person

        owner_share, shares = compute_shares(
            inst.amount_cents,
            data.method,
            data.include_owner,
            [p.amount_cents for p in data.participants],
            [p.percent_bp for p in data.participants],
        )

        bill = db.get(Bill, inst.bill_id)
        today = today_local()
        due = data.due_date or max(inst.due_date, today)
        split = ExpenseSplit(
            bill_installment_id=inst.id,
            method=data.method,
            include_owner=data.include_owner,
            total_cents=inst.amount_cents,
            owner_share_cents=owner_share,
        )
        db.add(split)
        db.flush()

        label = f"Rateio {bill.name} {inst.due_date:%m/%Y}"
        for p, share in zip(data.participants, shares, strict=True):
            balance = PartyBalance(
                person_id=p.person_id,
                direction="RECEIVABLE",
                origin_type="OWED_TO_ME",
                description=label[:160],
                principal_cents=share,
                operation_date=today,
                due_date=due,
                notes=f"Parte de {people[p.person_id].display_name} no rateio de {bill.name}.",
            )
            db.add(balance)
            db.flush()
            db.add(
                ExpenseSplitPart(
                    split_id=split.id,
                    person_id=p.person_id,
                    share_cents=share,
                    percent_bp=p.percent_bp if data.method == "PERCENT" else None,
                    party_balance_id=balance.id,
                )
            )
            audit(db, "party_balance", balance.id, "create", None, {"split_id": split.id, "share_cents": share}, request_id)
        db.flush()
        audit(
            db, "expense_split", split.id, "create", None,
            {"installment_id": inst.id, "total_cents": split.total_cents, "owner_share_cents": owner_share,
             "shares": shares, "method": data.method},
            request_id,
        )
        return split.id

    return run_idempotent(db, data.idempotency_key, "expense_split.create", payload, _create)


def cancel_split(db: Session, split_id: uuid.UUID, reason: str, request_id: str | None) -> ExpenseSplit:
    split = db.scalar(select(ExpenseSplit).where(ExpenseSplit.id == split_id).with_for_update())
    if split is None:
        raise NotFound("Rateio")
    if split.cancelled_at is not None:
        raise DomainError("already_cancelled", "Este rateio já foi desfeito.", status_code=409)
    for part in split.parts:
        # cancel_balance recusa (409) se houver repasse ativo: rateio com reembolso não é desfeito.
        balance = db.get(PartyBalance, part.party_balance_id)
        if balance.cancelled_at is None:
            parties.cancel_balance(db, balance.id, f"Rateio desfeito: {reason}", request_id, from_split=True)
    split.cancelled_at = datetime.now(UTC)
    split.cancel_reason = reason
    audit(db, "expense_split", split.id, "cancel", None, {"reason": reason}, request_id)
    db.flush()
    return split


def split_out(db: Session, split: ExpenseSplit) -> SplitOut:
    inst = db.get(BillInstallment, split.bill_installment_id)
    bill = db.get(Bill, inst.bill_id)
    ids = [p.party_balance_id for p in split.parts]
    aggs = parties.aggregates(db, ids)
    balances = {b.id: b for b in db.scalars(select(PartyBalance).where(PartyBalance.id.in_(ids))).unique()}
    today = today_local()
    parts = []
    for p in split.parts:
        out = parties.to_out(balances[p.party_balance_id], aggs[p.party_balance_id], today)
        parts.append(
            SplitPartOut(
                id=p.id,
                person_id=p.person_id,
                person_name=p.person.display_name,
                share_cents=p.share_cents,
                percent_bp=p.percent_bp,
                party_balance_id=p.party_balance_id,
                received_cents=out.settled_cents,
                open_cents=out.open_cents,
                status=out.status,
            )
        )
    received = sum(p.received_cents for p in parts)
    return SplitOut(
        id=split.id,
        bill_installment_id=inst.id,
        bill_name=bill.name,
        due_date=inst.due_date,
        method=split.method,
        include_owner=split.include_owner,
        total_cents=split.total_cents,
        owner_share_cents=split.owner_share_cents,
        others_cents=split.total_cents - split.owner_share_cents,
        received_cents=received,
        net_cost_cents=split.total_cents - received,
        cancelled_at=split.cancelled_at,
        cancel_reason=split.cancel_reason,
        created_at=split.created_at,
        parts=parts,
    )


def active_split_for(db: Session, installment_id: uuid.UUID) -> ExpenseSplit:
    inst = _installment(db, installment_id)
    if inst.split is None:
        raise NotFound("Rateio")
    return db.get(ExpenseSplit, inst.split.id)
