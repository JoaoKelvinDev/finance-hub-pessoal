"""Serviços para contas da casa (bills), recorrências e parcelas."""

import uuid
from datetime import date, datetime
from typing import Literal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.domains.support import today_local
from app.domains.bills.rules import (
    calculate_installment_amounts,
    generate_installment_dates,
    get_next_posting_dates,
    is_recurrence_active,
    validate_day_of_month_for_frequency,
    validate_recurrence_consistency,
)
from app.models.entities import (
    BILL_INSTALLMENT_STATUS,
    BILL_CATEGORIES,
    RECURRENCE_FREQUENCY,
    RECURRENCE_STATUS,
    Bill,
    BillInstallment,
    BillRecurrence,
    FinancialAccount,
    Transaction,
)
from app.schemas.finance import (
    BillCreate,
    BillInstallmentCreate,
    BillInstallmentUpdate,
    BillUpdate,
    RecurrenceCreate,
    RecurrenceUpdate,
)


# ---------- Bills (Contas da casa) ----------

def create_bill(
    db: Session,
    data: BillCreate,
    request_id: str | None = None,
) -> Bill:
    """Cria uma nova conta da casa."""
    bill = Bill(
        name=data.name,
        category=data.category,
        description=data.description,
        account_id=data.account_id,
        default_amount_cents=data.default_amount_cents,
        color=data.color,
    )
    db.add(bill)
    db.flush()
    return bill


def update_bill(
    db: Session,
    bill_id: uuid.UUID,
    data: BillUpdate,
) -> Bill | None:
    """Atualiza uma conta da casa."""
    bill = db.get(Bill, bill_id)
    if not bill:
        return None

    update_data = data.model_dump(exclude_unset=True)
    if "archived" in update_data:
        archived = update_data.pop("archived")
        if archived:
            bill.archived_at = datetime.now()
        else:
            bill.archived_at = None

    for key, value in update_data.items():
        setattr(bill, key, value)

    db.flush()
    return bill


def archive_bill(db: Session, bill_id: uuid.UUID) -> Bill | None:
    """Arquiva uma conta da casa (soft delete)."""
    bill = db.get(Bill, bill_id)
    if not bill or bill.archived_at:
        return None
    bill.archived_at = datetime.now()
    db.flush()
    return bill


def restore_bill(db: Session, bill_id: uuid.UUID) -> Bill | None:
    """Restaura uma conta arquivada."""
    bill = db.get(Bill, bill_id)
    if not bill or not bill.archived_at:
        return None
    bill.archived_at = None
    db.flush()
    return bill


def get_bill(db: Session, bill_id: uuid.UUID) -> Bill | None:
    """Busca uma conta por ID."""
    return db.get(Bill, bill_id)


def list_bills(
    db: Session,
    include_archived: bool = False,
    category: str | None = None,
    account_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Bill]:
    """Lista contas da casa com filtros."""
    stmt = select(Bill).options(selectinload(Bill.account))

    if not include_archived:
        stmt = stmt.where(Bill.archived_at.is_(None))

    if category:
        stmt = stmt.where(Bill.category == category)

    if account_id:
        stmt = stmt.where(Bill.account_id == account_id)

    stmt = stmt.order_by(Bill.name).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def count_bills(
    db: Session,
    include_archived: bool = False,
    category: str | None = None,
    account_id: uuid.UUID | None = None,
) -> int:
    """Conta total de contas (para paginação)."""
    stmt = select(func.count()).select_from(Bill)

    if not include_archived:
        stmt = stmt.where(Bill.archived_at.is_(None))

    if category:
        stmt = stmt.where(Bill.category == category)

    if account_id:
        stmt = stmt.where(Bill.account_id == account_id)

    return db.scalar(stmt) or 0


# ---------- Recorrências ----------

def create_recurrence(
    db: Session,
    data: RecurrenceCreate,
    request_id: str | None = None,
) -> BillRecurrence:
    """Cria uma nova recorrência para uma conta."""
    validate_recurrence_consistency(data.frequency, data.custom_months_interval)
    validate_day_of_month_for_frequency(data.frequency, data.day_of_month)

    recurrence = BillRecurrence(
        bill_id=data.bill_id,
        frequency=data.frequency,
        day_of_month=data.day_of_month,
        start_date=data.start_date,
        end_date=data.end_date,
        custom_months_interval=data.custom_months_interval,
        auto_post=data.auto_post,
        status="ACTIVE",
    )
    db.add(recurrence)
    db.flush()
    return recurrence


def update_recurrence(
    db: Session,
    recurrence_id: uuid.UUID,
    data: RecurrenceUpdate,
) -> BillRecurrence | None:
    """Atualiza uma recorrência."""
    recurrence = db.get(BillRecurrence, recurrence_id)
    if not recurrence:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # Validações se frequency ou day_of_month mudaram
    if "frequency" in update_data or "custom_months_interval" in update_data:
        freq = update_data.get("frequency", recurrence.frequency)
        custom_interval = update_data.get("custom_months_interval", recurrence.custom_months_interval)
        validate_recurrence_consistency(freq, custom_interval)

    if "day_of_month" in update_data or "frequency" in update_data:
        freq = update_data.get("frequency", recurrence.frequency)
        day = update_data.get("day_of_month", recurrence.day_of_month)
        validate_day_of_month_for_frequency(freq, day)

    for key, value in update_data.items():
        setattr(recurrence, key, value)

    db.flush()
    return recurrence


def get_recurrence(db: Session, recurrence_id: uuid.UUID) -> BillRecurrence | None:
    """Busca uma recorrência por ID."""
    return db.get(BillRecurrence, recurrence_id)


def list_recurrences(
    db: Session,
    bill_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[BillRecurrence]:
    """Lista recorrências com filtros."""
    stmt = select(BillRecurrence).options(selectinload(BillRecurrence.bill))

    if bill_id:
        stmt = stmt.where(BillRecurrence.bill_id == bill_id)

    if status:
        stmt = stmt.where(BillRecurrence.status == status)

    stmt = stmt.order_by(BillRecurrence.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


# ---------- Parcelas (BillInstallments) ----------

def create_bill_installment(
    db: Session,
    data: BillInstallmentCreate,
    request_id: str | None = None,
) -> BillInstallment:
    """Cria uma parcela manual (não vinculada a recorrência)."""
    # Verifica idempotência se chave fornecida
    if data.idempotency_key:
        existing = db.execute(
            select(BillInstallment).where(BillInstallment.notes == data.idempotency_key)
        ).scalar_one_or_none()
        if existing:
            return existing

    installment = BillInstallment(
        bill_id=data.bill_id,
        recurrence_id=data.recurrence_id,
        due_date=data.due_date,
        amount_cents=data.amount_cents,
        status="PENDING",
        notes=data.notes,
    )
    db.add(installment)
    db.flush()
    return installment


def create_installments_from_recurrence(
    db: Session,
    recurrence: BillRecurrence,
    up_to_date: date | None = None,
    request_id: str | None = None,
) -> list[BillInstallment]:
    """
    Gera parcelas para uma recorrência até uma data limite.
    Usa o default_amount_cents da conta como base, dividindo igualmente se houver múltiplas parcelas no período.
    """
    if not is_recurrence_active(recurrence.status, today_local(), recurrence.start_date, recurrence.end_date):
        return []

    if up_to_date is None:
        up_to_date = today_local()

    # Busca última parcela já criada para esta recorrência
    # Só a data importa; scalar_one_or_none quebrava (MultipleResultsFound) com 2+ parcelas.
    last_due = db.scalar(
        select(func.max(BillInstallment.due_date)).where(BillInstallment.recurrence_id == recurrence.id)
    )

    # Gera datas que precisam ser criadas
    due_dates = get_next_posting_dates(
        last_posted_due=last_due,
        recurrence_start=recurrence.start_date,
        frequency=recurrence.frequency,
        day_of_month=recurrence.day_of_month,
        end_date=recurrence.end_date,
        custom_months_interval=recurrence.custom_months_interval,
    )

    # Filtra apenas até up_to_date
    due_dates = [d for d in due_dates if d <= up_to_date]

    if not due_dates:
        return []

    # Para cada data, cria uma parcela
    # Usa o valor padrão da conta
    bill = db.get(Bill, recurrence.bill_id)
    if not bill:
        raise ValueError("Conta não encontrada para a recorrência")

    installments = []
    for due_date in due_dates:
        # Verifica se já existe parcela para esta data (idempotência por recurrence_id + due_date)
        existing = db.execute(
            select(BillInstallment).where(
                and_(
                    BillInstallment.recurrence_id == recurrence.id,
                    BillInstallment.due_date == due_date,
                )
            )
        ).scalar_one_or_none()

        if existing:
            continue

        installment = BillInstallment(
            bill_id=recurrence.bill_id,
            recurrence_id=recurrence.id,
            due_date=due_date,
            amount_cents=bill.default_amount_cents,
            status="PENDING",
        )
        db.add(installment)
        installments.append(installment)

    db.flush()
    return installments


def auto_post_all_recurrences(
    db: Session,
    up_to_date: date | None = None,
    request_id: str | None = None,
) -> list[BillInstallment]:
    """
    Processa todas as recorrências ativas com auto_post=True,
    gerando parcelas até a data especificada.
    """
    if up_to_date is None:
        up_to_date = today_local()

    recurrences = db.execute(
        select(BillRecurrence).where(
            and_(
                BillRecurrence.status == "ACTIVE",
                BillRecurrence.auto_post == True,
            )
        )
    ).scalars().all()

    all_created = []
    for recurrence in recurrences:
        created = create_installments_from_recurrence(db, recurrence, up_to_date, request_id)
        all_created.extend(created)

    return all_created


def update_bill_installment(
    db: Session,
    installment_id: uuid.UUID,
    data: BillInstallmentUpdate,
) -> BillInstallment | None:
    """Atualiza uma parcela."""
    installment = db.get(BillInstallment, installment_id)
    if not installment:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(installment, key, value)

    db.flush()
    return installment


def pay_bill_installment(
    db: Session,
    installment_id: uuid.UUID,
    account_id: uuid.UUID,
    paid_on: date,
    amount_cents: int | None = None,
    idempotency_key: str | None = None,
    request_id: str | None = None,
) -> tuple[BillInstallment, Transaction]:
    """
    Paga uma parcela de conta da casa.
    Cria uma transação do tipo EXPENSE na conta e marca a parcela como PAID.
    """
    installment = db.get(BillInstallment, installment_id)
    if not installment:
        raise ValueError("Parcela não encontrada")

    # Verifica idempotência PRIMEIRO - antes de checar status
    if idempotency_key:
        existing = db.execute(
            select(BillInstallment).where(BillInstallment.notes == idempotency_key)
        ).scalar_one_or_none()
        if existing:
            tx = db.get(Transaction, existing.transaction_id)
            return existing, tx

    if installment.status in ("PAID", "REVERSED", "CANCELLED"):
        raise ValueError(f"Parcela não pode ser paga (status: {installment.status})")

    # Usa valor da parcela se não especificado
    pay_amount = amount_cents or installment.amount_cents
    if pay_amount != installment.amount_cents:
        raise ValueError("Valor do pagamento deve ser igual ao valor da parcela")

    # Busca conta
    account = db.get(FinancialAccount, account_id)
    if not account:
        raise ValueError("Conta não encontrada")

    # Cria transação de despesa
    bill = db.get(Bill, installment.bill_id)
    tx = Transaction(
        account_id=account_id,
        kind="EXPENSE",
        amount_cents=-pay_amount,
        status="POSTED",
        effective_date=paid_on,
        description=f"Pagamento: {bill.name if bill else 'Conta'}",
        category_id=None,
        source_type="bill_payment",
        source_id=installment.id,
        notes=f"Parcela {installment.due_date.strftime('%m/%Y')}",
    )
    db.add(tx)
    db.flush()

    # Atualiza parcela
    installment.status = "PAID"
    installment.paid_at = datetime.now()
    installment.transaction_id = tx.id
    if idempotency_key:
        installment.notes = idempotency_key

    db.flush()
    return installment, tx


def reverse_bill_installment_payment(
    db: Session,
    installment_id: uuid.UUID,
    idempotency_key: str | None = None,
    request_id: str | None = None,
) -> tuple[BillInstallment, Transaction | None]:
    """
    Estorna o pagamento de uma parcela.
    Cria transação de estorno (ADJUSTMENT positivo) e marca parcela como REVERSED.
    """
    installment = db.get(BillInstallment, installment_id)
    if not installment:
        raise ValueError("Parcela não encontrada")

    if installment.status != "PAID":
        raise ValueError("Só é possível estornar parcelas pagas")

    if not installment.transaction_id:
        raise ValueError("Parcela não tem transação associada")

    original_tx = db.get(Transaction, installment.transaction_id)
    if not original_tx:
        raise ValueError("Transação original não encontrada")

    # Verifica idempotência
    if idempotency_key:
        existing_reversal = db.execute(
            select(Transaction).where(
                and_(
                    Transaction.source_type == "bill_payment_reversal",
                    Transaction.source_id == installment_id,
                    Transaction.notes == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing_reversal:
            return installment, existing_reversal

    # Cria transação de estorno (entrada positiva para cancelar a saída)
    bill = db.get(Bill, installment.bill_id)
    reversal_tx = Transaction(
        account_id=original_tx.account_id,
        kind="ADJUSTMENT",
        amount_cents=abs(original_tx.amount_cents),  # positivo para cancelar despesa
        status="POSTED",
        effective_date=today_local(),
        description=f"Estorno: {bill.name if bill else 'Conta'}",
        source_type="bill_payment_reversal",
        source_id=installment.id,
        notes=idempotency_key or f"Estorno parcela {installment.due_date.strftime('%m/%Y')}",
    )
    db.add(reversal_tx)
    db.flush()

    # Atualiza parcela
    installment.status = "REVERSED"
    installment.reversed_at = datetime.now()
    installment.transaction_id = reversal_tx.id

    db.flush()
    return installment, reversal_tx


def skip_bill_installment(
    db: Session,
    installment_id: uuid.UUID,
    idempotency_key: str | None = None,
) -> BillInstallment:
    """Marca uma parcela como SKIPPED (pulou o pagamento)."""
    installment = db.get(BillInstallment, installment_id)
    if not installment:
        raise ValueError("Parcela não encontrada")

    if installment.status in ("PAID", "REVERSED", "CANCELLED"):
        raise ValueError(f"Parcela não pode ser pulada (status: {installment.status})")

    installment.status = "SKIPPED"
    if idempotency_key:
        installment.notes = idempotency_key
    db.flush()
    return installment


def cancel_bill_installment(
    db: Session,
    installment_id: uuid.UUID,
    idempotency_key: str | None = None,
) -> BillInstallment:
    """Cancela uma parcela."""
    installment = db.get(BillInstallment, installment_id)
    if not installment:
        raise ValueError("Parcela não encontrada")

    if installment.status in ("PAID", "REVERSED"):
        raise ValueError("Não é possível cancelar parcela paga ou estornada")

    installment.status = "CANCELLED"
    if idempotency_key:
        installment.notes = idempotency_key
    db.flush()
    return installment


def get_bill_installment(db: Session, installment_id: uuid.UUID) -> BillInstallment | None:
    """Busca uma parcela por ID."""
    return db.get(BillInstallment, installment_id)


def list_bill_installments(
    db: Session,
    bill_id: uuid.UUID | None = None,
    recurrence_id: uuid.UUID | None = None,
    status: str | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[BillInstallment]:
    """Lista parcelas com filtros."""
    stmt = select(BillInstallment).options(
        selectinload(BillInstallment.bill),
        selectinload(BillInstallment.recurrence),
        selectinload(BillInstallment.transaction),
    )

    if bill_id:
        stmt = stmt.where(BillInstallment.bill_id == bill_id)

    if recurrence_id:
        stmt = stmt.where(BillInstallment.recurrence_id == recurrence_id)

    if status:
        stmt = stmt.where(BillInstallment.status == status)

    if due_from:
        stmt = stmt.where(BillInstallment.due_date >= due_from)

    if due_to:
        stmt = stmt.where(BillInstallment.due_date <= due_to)

    stmt = stmt.order_by(BillInstallment.due_date.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def count_bill_installments(
    db: Session,
    bill_id: uuid.UUID | None = None,
    recurrence_id: uuid.UUID | None = None,
    status: str | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
) -> int:
    """Conta total de parcelas (para paginação)."""
    stmt = select(func.count()).select_from(BillInstallment)

    if bill_id:
        stmt = stmt.where(BillInstallment.bill_id == bill_id)

    if recurrence_id:
        stmt = stmt.where(BillInstallment.recurrence_id == recurrence_id)

    if status:
        stmt = stmt.where(BillInstallment.status == status)

    if due_from:
        stmt = stmt.where(BillInstallment.due_date >= due_from)

    if due_to:
        stmt = stmt.where(BillInstallment.due_date <= due_to)

    return db.scalar(stmt) or 0


def get_upcoming_bill_installments(
    db: Session,
    days_ahead: int = 30,
    limit: int = 20,
) -> list[BillInstallment]:
    """Busca parcelas próximas do vencimento (PENDING ou POSTED)."""
    today = today_local()
    limit_date = today + __import__("datetime").timedelta(days=days_ahead)

    stmt = (
        select(BillInstallment)
        .options(selectinload(BillInstallment.bill))
        .where(
            and_(
                BillInstallment.status.in_(["PENDING", "POSTED"]),
                BillInstallment.due_date >= today,
                BillInstallment.due_date <= limit_date,
            )
        )
        .order_by(BillInstallment.due_date)
        .limit(limit)
    )
    return list(db.scalars(stmt))


def get_overdue_bill_installments(db: Session, limit: int = 50) -> list[BillInstallment]:
    """Busca parcelas vencidas e não pagas."""
    today = today_local()

    stmt = (
        select(BillInstallment)
        .options(selectinload(BillInstallment.bill))
        .where(
            and_(
                BillInstallment.status.in_(["PENDING", "POSTED"]),
                BillInstallment.due_date < today,
            )
        )
        .order_by(BillInstallment.due_date)
        .limit(limit)
    )
    return list(db.scalars(stmt))