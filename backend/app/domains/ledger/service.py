import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, NotFound
from app.domains.ledger import rules
from app.domains.support import audit, run_idempotent, snapshot, today_local
from app.models import Category, FinancialAccount, Person, Transaction
from app.schemas.finance import AccountCreate, TransactionCreate, TransferCreate

TX_AUDIT_FIELDS = ("account_id", "amount_cents", "kind", "status", "effective_date", "description", "category_id")


# ---------- Saldos ----------
def balances(db: Session, account_ids: Iterable[uuid.UUID] | None = None) -> dict[uuid.UUID, tuple[int, int]]:
    """Retorna {conta: (saldo_atual, saldo_incluindo_previstos)} — previstos nunca entram no saldo atual."""
    posted = func.coalesce(func.sum(case((Transaction.status == "POSTED", Transaction.amount_cents), else_=0)), 0)
    planned = func.coalesce(func.sum(case((Transaction.status == "PLANNED", Transaction.amount_cents), else_=0)), 0)
    q = (
        select(FinancialAccount.id, FinancialAccount.opening_balance_cents, posted, planned)
        .outerjoin(Transaction, Transaction.account_id == FinancialAccount.id)
        .group_by(FinancialAccount.id)
    )
    if account_ids is not None:
        q = q.where(FinancialAccount.id.in_(list(account_ids)))
    # SUM(bigint) retorna NUMERIC no Postgres; converte para int sem perda.
    return {r[0]: (int(r[1] + r[2]), int(r[1] + r[2] + r[3])) for r in db.execute(q)}


# ---------- Contas ----------
def create_account(db: Session, data: AccountCreate, request_id: str | None) -> FinancialAccount:
    acc = FinancialAccount(**data.model_dump())
    db.add(acc)
    db.flush()
    audit(db, "financial_account", acc.id, "create", None, data.model_dump(), request_id)
    return acc


def _active_account(db: Session, account_id: uuid.UUID, lock: bool = False) -> FinancialAccount:
    q = select(FinancialAccount).where(FinancialAccount.id == account_id)
    if lock:
        q = q.with_for_update()
    acc = db.scalar(q)
    if acc is None:
        raise NotFound("Conta")
    if acc.archived_at is not None:
        raise DomainError("account_archived", f"A conta '{acc.name}' está arquivada; reative-a para lançar.")
    return acc


def _check_date(acc: FinancialAccount, effective_date: date) -> None:
    if effective_date < acc.opening_date:
        raise DomainError(
            "before_opening",
            f"Data anterior ao saldo inicial da conta '{acc.name}' "
            f"({acc.opening_date:%d/%m/%Y}). Lançamentos anteriores já estão no saldo inicial.",
        )


# ---------- Lançamentos ----------
def create_transaction(db: Session, data: TransactionCreate, request_id: str | None) -> tuple[uuid.UUID, bool]:
    payload = data.model_dump(exclude={"idempotency_key"})

    def _create() -> uuid.UUID:
        acc = _active_account(db, data.account_id)
        _check_date(acc, data.effective_date)
        rules.validate_status_date(data.status, data.effective_date, today_local())
        amount = rules.signed_amount(data.kind, data.amount_cents)

        if data.category_id:
            cat = db.get(Category, data.category_id)
            if cat is None:
                raise NotFound("Categoria")
            expected = rules.category_kind_for(data.kind)
            if expected and cat.kind != expected:
                raise DomainError("category_kind_mismatch", "A categoria não corresponde ao tipo do lançamento.")
        if data.counterparty_id and db.get(Person, data.counterparty_id) is None:
            raise NotFound("Pessoa")

        tx = Transaction(
            account_id=acc.id,
            amount_cents=amount,
            kind=data.kind,
            status=data.status,
            effective_date=data.effective_date,
            description=data.description,
            category_id=data.category_id,
            counterparty_id=data.counterparty_id,
            notes=data.notes,
            source_type="manual",
        )
        db.add(tx)
        db.flush()
        audit(db, "transaction", tx.id, "create", None, snapshot(tx, TX_AUDIT_FIELDS), request_id)
        return tx.id

    return run_idempotent(db, data.idempotency_key, "transaction.create", payload, _create)


def transfer(db: Session, data: TransferCreate, request_id: str | None) -> tuple[uuid.UUID, bool]:
    payload = data.model_dump(exclude={"idempotency_key"})

    def _create() -> uuid.UUID:
        # Ordem fixa de lock evita deadlock entre transferências concorrentes.
        first, second = sorted([data.from_account_id, data.to_account_id])
        locked = {a: _active_account(db, a, lock=True) for a in (first, second)}
        src, dst = locked[data.from_account_id], locked[data.to_account_id]
        for acc in (src, dst):
            _check_date(acc, data.effective_date)
        rules.validate_status_date("POSTED", data.effective_date, today_local())
        out_amount, in_amount = rules.transfer_legs(data.amount_cents)

        group = uuid.uuid4()
        common = dict(
            status="POSTED",
            effective_date=data.effective_date,
            transfer_group_id=group,
            source_type="transfer",
            source_id=group,
        )
        out_leg = Transaction(
            account_id=src.id, amount_cents=out_amount, kind="TRANSFER_OUT",
            description=f"{data.description} → {dst.name}", **common,
        )
        in_leg = Transaction(
            account_id=dst.id, amount_cents=in_amount, kind="TRANSFER_IN",
            description=f"{data.description} ← {src.name}", **common,
        )
        db.add_all([out_leg, in_leg])
        db.flush()
        audit(db, "transfer", group, "create", None, payload, request_id)
        return group

    return run_idempotent(db, data.idempotency_key, "transfer.create", payload, _create)


def get_transaction(db: Session, tx_id: uuid.UUID) -> Transaction:
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise NotFound("Lançamento")
    return tx


def transfer_legs(db: Session, group: uuid.UUID) -> tuple[Transaction, Transaction]:
    legs = db.scalars(select(Transaction).where(Transaction.transfer_group_id == group)).all()
    by_kind = {t.kind: t for t in legs}
    if set(by_kind) != {"TRANSFER_OUT", "TRANSFER_IN"}:
        raise NotFound("Transferência")
    return by_kind["TRANSFER_OUT"], by_kind["TRANSFER_IN"]


def cancel_transaction(db: Session, tx_id: uuid.UUID, reason: str, request_id: str | None) -> Transaction:
    """Cancelamento preserva o registro. Em transferência, as duas pernas são canceladas juntas."""
    tx = get_transaction(db, tx_id)
    if tx.status == "CANCELLED":
        raise DomainError("already_cancelled", "Lançamento já cancelado.", status_code=409)
    if tx.source_type in ("party_balance", "party_settlement"):
        # Cancelar aqui deixaria o saldo com o terceiro inconsistente.
        raise DomainError(
            "managed_by_parties",
            "Este lançamento pertence a Valores com terceiros; cancele ou estorne por lá.",
            status_code=409,
        )
    targets = list(transfer_legs(db, tx.transfer_group_id)) if tx.transfer_group_id else [tx]
    now = datetime.now(UTC)
    for t in targets:
        before = snapshot(t, TX_AUDIT_FIELDS)
        t.status = "CANCELLED"
        t.cancelled_at = now
        t.cancel_reason = reason
        audit(db, "transaction", t.id, "cancel", before, {"status": "CANCELLED", "reason": reason}, request_id)
    db.flush()
    return tx


def post_transaction(db: Session, tx_id: uuid.UUID, effective_date: date | None, request_id: str | None) -> Transaction:
    """Efetiva um lançamento previsto (ex.: conta paga)."""
    tx = get_transaction(db, tx_id)
    if tx.status != "PLANNED":
        raise DomainError("not_planned", "Apenas lançamentos previstos podem ser efetivados.", status_code=409)
    acc = _active_account(db, tx.account_id)
    new_date = effective_date or min(tx.effective_date, today_local())
    _check_date(acc, new_date)
    rules.validate_status_date("POSTED", new_date, today_local())
    before = snapshot(tx, TX_AUDIT_FIELDS)
    tx.status = "POSTED"
    tx.effective_date = new_date
    audit(db, "transaction", tx.id, "post", before, snapshot(tx, TX_AUDIT_FIELDS), request_id)
    db.flush()
    return tx
