import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.v1.deps import DB, RequestId
from app.core.errors import NotFound
from app.domains.ledger.service import balances, create_account
from app.domains.support import audit, snapshot
from app.models import FinancialAccount, Transaction
from app.schemas.finance import AccountCreate, AccountOut, AccountUpdate, LedgerOut, TransactionOut

router = APIRouter(prefix="/accounts", tags=["Contas"])
FIELDS = ("name", "institution", "color", "notes", "archived_at")


def _out(acc: FinancialAccount, bal: dict) -> AccountOut:
    current, with_planned = bal.get(acc.id, (acc.opening_balance_cents, acc.opening_balance_cents))
    return AccountOut.model_validate(acc).model_copy(
        update={"balance_cents": current, "planned_balance_cents": with_planned}
    )


def _get(db, account_id: uuid.UUID) -> FinancialAccount:
    acc = db.get(FinancialAccount, account_id)
    if acc is None:
        raise NotFound("Conta")
    return acc


@router.get("", response_model=list[AccountOut])
def list_accounts(db: DB, include_archived: bool = False):
    q = select(FinancialAccount).order_by(FinancialAccount.archived_at.is_not(None), FinancialAccount.name)
    if not include_archived:
        q = q.where(FinancialAccount.archived_at.is_(None))
    accounts = db.scalars(q).all()
    bal = balances(db, [a.id for a in accounts])
    return [_out(a, bal) for a in accounts]


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def post_account(data: AccountCreate, db: DB, rid: RequestId):
    acc = create_account(db, data, rid)
    db.commit()
    return _out(acc, balances(db, [acc.id]))


@router.patch("/{account_id}", response_model=AccountOut)
def patch_account(account_id: uuid.UUID, data: AccountUpdate, db: DB, rid: RequestId):
    acc = _get(db, account_id)
    before = snapshot(acc, FIELDS)
    changes = data.model_dump(exclude_unset=True)
    archived = changes.pop("archived", None)
    for k, v in changes.items():
        setattr(acc, k, v)
    if archived is not None:
        acc.archived_at = datetime.now(UTC) if archived else None
    audit(db, "financial_account", acc.id, "update", before, snapshot(acc, FIELDS), rid)
    db.commit()
    return _out(acc, balances(db, [acc.id]))


@router.get("/{account_id}/ledger", response_model=LedgerOut)
def ledger(
    account_id: uuid.UUID,
    db: DB,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    acc = _get(db, account_id)
    where = Transaction.account_id == account_id
    total = db.scalar(select(func.count()).where(where)) or 0
    items = db.scalars(
        select(Transaction)
        .where(where)
        .order_by(Transaction.effective_date.desc(), Transaction.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).unique()
    return LedgerOut(
        account=_out(acc, balances(db, [acc.id])),
        items=[TransactionOut.from_model(t) for t in items],
        total=total,
        page=page,
        limit=limit,
    )
