"""Serviços de domínio para cartões: CRUD, ciclos, compras, parcelas, pagamentos."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, NotFound
from app.domains.cards import rules
from app.domains.ledger.service import _active_account
from app.domains.support import audit, run_idempotent, snapshot, today_local
from app.models import (
    CardInstallment,
    CardPurchase,
    CardStatement,
    CreditCard,
    FinancialAccount,
    StatementPayment,
    Transaction,
)
from app.schemas.finance import CardCreate, CardUpdate, PurchaseCreate, StatementPaymentCreate

CARD_AUDIT_FIELDS = (
    "name", "bank", "nickname", "last_four", "brand", "type", "limit_cents",
    "closing_day", "due_day", "due_month_offset", "purchase_boundary_policy",
    "default_payment_account_id", "color", "archived_at",
)

PURCHASE_AUDIT_FIELDS = (
    "card_id", "description", "merchant", "purchased_on", "total_cents",
    "installments_count", "category_id", "person_id", "status", "notes",
)

STATEMENT_AUDIT_FIELDS = (
    "card_id", "cycle_start_date", "cycle_end_exclusive", "due_date",
    "status", "paid_cents", "closed_at", "cancelled_at", "cancel_reason",
)


# ---------- Helpers ----------
def _get_card(db: Session, card_id: uuid.UUID, lock: bool = False) -> CreditCard:
    q = select(CreditCard).where(CreditCard.id == card_id)
    if lock:
        q = q.with_for_update()
    card = db.scalar(q)
    if card is None:
        raise NotFound("Cartão")
    if card.archived_at is not None:
        raise DomainError("card_archived", f"O cartão '{card.name}' está arquivado.")
    return card


def _get_statement(db: Session, statement_id: uuid.UUID, lock: bool = False) -> CardStatement:
    q = select(CardStatement).where(CardStatement.id == statement_id)
    if lock:
        q = q.with_for_update()
    stmt = db.scalar(q)
    if stmt is None:
        raise NotFound("Fatura")
    return stmt


def _get_purchase(db: Session, purchase_id: uuid.UUID) -> CardPurchase:
    p = db.get(CardPurchase, purchase_id)
    if p is None:
        raise NotFound("Compra")
    return p


def _active_payment_account(db: Session, account_id: uuid.UUID) -> FinancialAccount:
    return _active_account(db, account_id)


def _find_or_create_statement(db: Session, card: CreditCard, cycle_start: date) -> CardStatement:
    """Encontra ou cria a fatura do ciclo que começa em `cycle_start`."""
    cycle_start, cycle_end = rules.resolve_cycle_dates(cycle_start)
    due_date = rules.resolve_due_date(cycle_end, card.due_day, card.due_month_offset)

    # Busca fatura existente para este ciclo
    stmt = db.scalar(
        select(CardStatement).where(
            CardStatement.card_id == card.id,
            CardStatement.cycle_start_date == cycle_start,
        )
    )

    if stmt:
        return stmt

    # Cria nova fatura
    stmt = CardStatement(
        card_id=card.id,
        cycle_start_date=cycle_start,
        cycle_end_exclusive=cycle_end,
        due_date=due_date,
        status="OPEN",
        paid_cents=0,
    )
    db.add(stmt)
    db.flush()
    return stmt


def _recalc_statement_total(db: Session, statement_id: uuid.UUID) -> int:
    """Recalcula o total da fatura somando parcelas vinculadas (não canceladas)."""
    total = db.scalar(
        select(func.coalesce(func.sum(CardInstallment.amount_cents), 0))
        .where(
            CardInstallment.statement_id == statement_id,
            CardInstallment.status.notin_(("REVERSED", "CANCELLED")),
        )
    ) or 0
    return int(total)


def _update_statement_status(db: Session, stmt: CardStatement) -> None:
    """Atualiza status da fatura baseado em paid_cents, total e due_date."""
    total = _recalc_statement_total(db, stmt.id)
    new_status = rules.derive_statement_status(stmt.paid_cents, total, stmt.due_date, today_local())
    if stmt.status != new_status:
        stmt.status = new_status
        if new_status in ("PAID", "OVERDUE") and stmt.closed_at is None:
            stmt.closed_at = datetime.now(UTC)


# ---------- Cartões ----------
def create_card(db: Session, data: CardCreate, request_id: str | None) -> CreditCard:
    if data.default_payment_account_id:
        _active_payment_account(db, data.default_payment_account_id)

    rules.validate_closing_day(data.closing_day)
    rules.validate_due_day(data.due_day)
    rules.validate_due_month_offset(data.due_month_offset)
    rules.validate_due_after_closing(data.closing_day, data.due_day, data.due_month_offset)

    card = CreditCard(**data.model_dump())
    db.add(card)
    db.flush()
    audit(db, "credit_card", card.id, "create", None, data.model_dump(), request_id)
    return card


def update_card(db: Session, card_id: uuid.UUID, data: CardUpdate, request_id: str | None) -> CreditCard:
    card = _get_card(db, card_id)
    before = snapshot(card, CARD_AUDIT_FIELDS)
    changes = data.model_dump(exclude_unset=True)

    archived = changes.pop("archived", None)
    if archived is not None:
        card.archived_at = datetime.now(UTC) if archived else None

    if "closing_day" in changes:
        rules.validate_closing_day(changes["closing_day"])
    if "due_day" in changes:
        rules.validate_due_day(changes["due_day"])
    if "due_month_offset" in changes:
        rules.validate_due_month_offset(changes["due_month_offset"])
    if changes.get("default_payment_account_id"):
        _active_payment_account(db, changes["default_payment_account_id"])
    rules.validate_due_after_closing(
        changes.get("closing_day", card.closing_day),
        changes.get("due_day", card.due_day),
        changes.get("due_month_offset", card.due_month_offset),
    )

    for k, v in changes.items():
        setattr(card, k, v)

    audit(db, "credit_card", card.id, "update", before, snapshot(card, CARD_AUDIT_FIELDS), request_id)
    db.flush()
    return card


def list_cards(db: Session, include_archived: bool = False):
    q = select(CreditCard).order_by(CreditCard.archived_at.is_not(None), CreditCard.name)
    if not include_archived:
        q = q.where(CreditCard.archived_at.is_(None))
    return db.scalars(q).all()


def get_card_with_limits(db: Session, card_id: uuid.UUID) -> tuple[CreditCard, int, int]:
    """Retorna cartão, limite usado e limite disponível."""
    card = _get_card(db, card_id)

    # Soma parcelas não canceladas e não pagas de compras ativas deste cartão
    used = db.scalar(
        select(func.coalesce(func.sum(CardInstallment.amount_cents), 0))
        .join(CardPurchase, CardPurchase.id == CardInstallment.purchase_id)
        .where(
            CardPurchase.card_id == card.id,
            CardPurchase.status == "ACTIVE",
            CardInstallment.status.notin_(("REVERSED", "CANCELLED", "PAID")),
        )
    ) or 0

    used = int(used)
    available = card.limit_cents - used
    return card, used, available


# ---------- Compras ----------
def create_purchase(db: Session, data: PurchaseCreate, request_id: str | None) -> tuple[uuid.UUID, bool]:
    payload = data.model_dump(exclude={"idempotency_key"})

    def _create() -> uuid.UUID:
        card = _get_card(db, data.card_id, lock=True)
        rules.validate_purchase_date_not_future(data.purchased_on, today_local())

        if data.category_id:
            from app.models import Category
            cat = db.get(Category, data.category_id)
            if cat is None:
                raise NotFound("Categoria")
            if cat.kind != "EXPENSE":
                raise DomainError("category_kind_mismatch", "Categoria deve ser do tipo DESPESA.")

        if data.person_id:
            from app.models import Person
            if db.get(Person, data.person_id) is None:
                raise NotFound("Pessoa")

        # Ciclo da 1ª parcela; a parcela N vai para o ciclo N−1 meses depois.
        first_cycle = rules.resolve_cycle_start(card.closing_day, data.purchased_on, card.purchase_boundary_policy)

        # Cria compra
        purchase = CardPurchase(
            card_id=card.id,
            description=data.description,
            merchant=data.merchant,
            purchased_on=data.purchased_on,
            total_cents=data.total_cents,
            installments_count=data.installments_count,
            category_id=data.category_id,
            person_id=data.person_id,
            notes=data.notes,
            status="ACTIVE",
        )
        db.add(purchase)
        db.flush()

        # Cria parcelas: uma por fatura, em ciclos consecutivos (antes iam todas para a 1ª fatura).
        amounts = rules.split_installments(data.total_cents, data.installments_count)
        statements: list[CardStatement] = []
        for idx, amt in enumerate(amounts, start=1):
            stmt = _find_or_create_statement(db, card, rules.add_months(first_cycle, idx - 1))
            statements.append(stmt)
            inst = CardInstallment(
                purchase_id=purchase.id,
                statement_id=stmt.id,
                installment_number=idx,
                amount_cents=amt,
                status="PENDING" if data.purchased_on >= stmt.cycle_start_date else "POSTED",
            )
            db.add(inst)

        db.flush()

        audit(db, "card_purchase", purchase.id, "create", None, snapshot(purchase, PURCHASE_AUDIT_FIELDS), request_id)
        for stmt in statements:
            stmt_total = _recalc_statement_total(db, stmt.id)
            _update_statement_status(db, stmt)
            audit(db, "card_statement", stmt.id, "update", {"total_cents": stmt_total},
                  snapshot(stmt, STATEMENT_AUDIT_FIELDS), request_id)

        return purchase.id

    return run_idempotent(db, data.idempotency_key, "purchase.create", payload, _create)


def list_purchases(
    db: Session,
    card_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
):
    q = select(CardPurchase)
    if card_id:
        q = q.where(CardPurchase.card_id == card_id)
    if date_from:
        q = q.where(CardPurchase.purchased_on >= date_from)
    if date_to:
        q = q.where(CardPurchase.purchased_on <= date_to)
    if status:
        q = q.where(CardPurchase.status == status)
    q = q.order_by(CardPurchase.purchased_on.desc(), CardPurchase.created_at.desc())
    return db.scalars(q).all()


# ---------- Pagamentos de fatura ----------
def pay_statement(db: Session, data: StatementPaymentCreate, request_id: str | None) -> tuple[uuid.UUID, bool]:
    """Registra pagamento de fatura: cria transação na conta bancária e statement_payment."""
    payload = data.model_dump(exclude={"idempotency_key"})

    def _create() -> uuid.UUID:
        stmt = _get_statement(db, data.statement_id, lock=True)
        card = _get_card(db, stmt.card_id, lock=True)

        # Valida conta de pagamento
        pay_account = _active_payment_account(db, data.account_id)
        _check_date(pay_account, data.paid_on)

        # Valor a pagar não pode exceder saldo devedor (exceto crédito explícito)
        total = _recalc_statement_total(db, stmt.id)
        due = total - stmt.paid_cents
        if data.amount_cents > due:
            raise DomainError("overpayment", f"Valor excede o saldo devedor da fatura (R$ {due/100:.2f}).")

        # Cria transação de saída na conta bancária
        tx = Transaction(
            account_id=pay_account.id,
            amount_cents=-data.amount_cents,
            kind="EXPENSE",
            status="POSTED",
            effective_date=data.paid_on,
            description=f"Pagamento fatura {card.name} ({stmt.cycle_start_date:%m/%Y})",
            source_type="statement_payment",
            source_id=stmt.id,
        )
        db.add(tx)
        db.flush()

        # Registra pagamento da fatura
        sp = StatementPayment(
            statement_id=stmt.id,
            transaction_id=tx.id,
            amount_cents=data.amount_cents,
            paid_on=data.paid_on,
            idempotency_key=data.idempotency_key,
        )
        db.add(sp)

        # Atualiza fatura
        before_stmt = snapshot(stmt, STATEMENT_AUDIT_FIELDS)
        stmt.paid_cents += data.amount_cents
        _update_statement_status(db, stmt)

        # Atualiza parcelas: marca como PAID as que couberem no valor pago
        _apply_payment_to_installments(db, stmt.id, data.amount_cents)

        db.flush()

        audit(db, "statement_payment", sp.id, "create", None, payload, request_id)
        audit(db, "card_statement", stmt.id, "update", before_stmt, snapshot(stmt, STATEMENT_AUDIT_FIELDS), request_id)
        audit(db, "transaction", tx.id, "create", None, {"kind": "EXPENSE", "amount_cents": -data.amount_cents}, request_id)

        return sp.id

    return run_idempotent(db, data.idempotency_key, "statement_payment.create", payload, _create)


def _apply_payment_to_installments(db: Session, statement_id: uuid.UUID, amount_cents: int) -> None:
    """Aplica pagamento às parcelas da fatura (FIFO: mais antigas primeiro)."""
    remaining = amount_cents
    insts = db.scalars(
        select(CardInstallment)
        .where(
            CardInstallment.statement_id == statement_id,
            CardInstallment.status.in_(("PENDING", "POSTED")),
        )
        .order_by(CardInstallment.installment_number)
    ).all()

    for inst in insts:
        if remaining <= 0:
            break
        if remaining >= inst.amount_cents:
            inst.status = "PAID"
            inst.paid_at = datetime.now(UTC)
            remaining -= inst.amount_cents
        else:
            # Pagamento parcial não é suportado no MVP; deixa pendente
            pass


def _check_date(acc: FinancialAccount, effective_date: date) -> None:
    if effective_date < acc.opening_date:
        raise DomainError(
            "before_opening",
            f"Data anterior ao saldo inicial da conta '{acc.name}' ({acc.opening_date:%d/%m/%Y}).",
        )


# ---------- Utilitários ----------
def get_statement_detail(db: Session, statement_id: uuid.UUID) -> CardStatement:
    stmt = _get_statement(db, statement_id)
    _update_statement_status(db, stmt)
    return stmt


def list_statements(
    db: Session,
    card_id: uuid.UUID,
    status: str | None = None,
):
    q = select(CardStatement).where(CardStatement.card_id == card_id)
    if status:
        q = q.where(CardStatement.status == status)
    q = q.order_by(CardStatement.cycle_start_date.desc())
    return db.scalars(q).all()


def get_upcoming_installments(db: Session, card_id: uuid.UUID, limit: int = 20):
    """Parcelas futuras não pagas."""
    return db.scalars(
        select(CardInstallment)
        .join(CardPurchase, CardPurchase.id == CardInstallment.purchase_id)
        .where(
            CardPurchase.card_id == card_id,
            CardPurchase.status == "ACTIVE",
            CardInstallment.status.in_(("PENDING", "POSTED")),
        )
        .order_by(CardInstallment.installment_number)
        .limit(limit)
    ).all()