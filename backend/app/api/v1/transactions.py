import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import case, func, or_, select

from app.api.v1.deps import DB, RequestId
from app.domains.ledger import service
from app.models import Transaction
from app.schemas.finance import (
    TransactionCancel,
    TransactionCreate,
    TransactionOut,
    TransactionPage,
    TransactionPost,
    TransactionTotals,
    TransferCreate,
    TransferOut,
    TxKind,
    TxStatus,
)

router = APIRouter(tags=["Lançamentos"])


@router.get("/transactions", response_model=TransactionPage)
def list_transactions(
    db: DB,
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    kind: list[TxKind] | None = Query(None),
    status_: list[TxStatus] | None = Query(None, alias="status"),
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
    group: Literal["all", "income", "expense", "transfer"] = "all",
    q: str | None = Query(None, max_length=80),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    conds = []
    if date_from:
        conds.append(Transaction.effective_date >= date_from)
    if date_to:
        conds.append(Transaction.effective_date <= date_to)
    groups = {
        "income": ["INCOME"],
        "expense": ["EXPENSE"],
        "transfer": ["TRANSFER_IN", "TRANSFER_OUT"],
    }
    if group != "all":
        conds.append(Transaction.kind.in_(groups[group]))
    if kind:
        conds.append(Transaction.kind.in_(kind))
    if status_:
        conds.append(Transaction.status.in_(status_))
    if account_id:
        conds.append(Transaction.account_id == account_id)
    if category_id:
        conds.append(Transaction.category_id == category_id)
    if person_id:
        conds.append(Transaction.counterparty_id == person_id)
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(Transaction.description.ilike(like), Transaction.notes.ilike(like)))

    # Totalizadores usam exatamente o mesmo filtro da lista; só efetivados somam.
    posted = Transaction.status == "POSTED"
    inc = func.coalesce(func.sum(case(((Transaction.kind == "INCOME") & posted, Transaction.amount_cents), else_=0)), 0)
    exp = func.coalesce(func.sum(case(((Transaction.kind == "EXPENSE") & posted, -Transaction.amount_cents), else_=0)), 0)
    income, expense, count = db.execute(select(inc, exp, func.count()).where(*conds)).one()

    items = db.scalars(
        select(Transaction)
        .where(*conds)
        .order_by(Transaction.effective_date.desc(), Transaction.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).unique()
    return TransactionPage(
        items=[TransactionOut.from_model(t) for t in items],
        totals=TransactionTotals(
            income_cents=int(income), expense_cents=int(expense), net_cents=int(income - expense), count=count
        ),
        total=count,
        page=page,
        limit=limit,
    )


@router.post("/transactions", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(data: TransactionCreate, db: DB, rid: RequestId, response: Response):
    tx_id, created = service.create_transaction(db, data, rid)
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return TransactionOut.from_model(service.get_transaction(db, tx_id))


@router.get("/transactions/{tx_id}", response_model=TransactionOut)
def get_transaction(tx_id: uuid.UUID, db: DB):
    return TransactionOut.from_model(service.get_transaction(db, tx_id))


@router.post("/transactions/{tx_id}/cancel", response_model=TransactionOut)
def cancel(tx_id: uuid.UUID, data: TransactionCancel, db: DB, rid: RequestId):
    tx = service.cancel_transaction(db, tx_id, data.reason, rid)
    db.commit()
    return TransactionOut.from_model(tx)


@router.post("/transactions/{tx_id}/post", response_model=TransactionOut)
def post(tx_id: uuid.UUID, data: TransactionPost, db: DB, rid: RequestId):
    tx = service.post_transaction(db, tx_id, data.effective_date, rid)
    db.commit()
    return TransactionOut.from_model(tx)


@router.post("/transfers", response_model=TransferOut, status_code=status.HTTP_201_CREATED)
def create_transfer(data: TransferCreate, db: DB, rid: RequestId, response: Response):
    group, created = service.transfer(db, data, rid)
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    out_leg, in_leg = service.transfer_legs(db, group)
    return TransferOut(
        transfer_group_id=group,
        out_leg=TransactionOut.from_model(out_leg),
        in_leg=TransactionOut.from_model(in_leg),
    )
