import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk

ACCOUNT_TYPES = ("CHECKING", "SAVINGS", "CASH", "DIGITAL_WALLET", "OTHER")
CATEGORY_KINDS = ("INCOME", "EXPENSE")
TX_KINDS = ("INCOME", "EXPENSE", "TRANSFER_IN", "TRANSFER_OUT", "ADJUSTMENT")
TX_STATUSES = ("PLANNED", "POSTED", "CANCELLED")

CARD_TYPES = ("CREDIT", "DEBIT", "PREPAID")
CARD_BRANDS = ("VISA", "MASTERCARD", "ELO", "AMEX", "HIPERCARD", "OTHER")
STATEMENT_STATUS = ("OPEN", "CLOSED", "PARTIALLY_PAID", "PAID", "OVERDUE", "CANCELLED")
PURCHASE_STATUS = ("ACTIVE", "REVERSED", "CANCELLED")
INSTALLMENT_STATUS = ("PENDING", "POSTED", "PAID", "REVERSED", "CANCELLED")
PURCHASE_BOUNDARY_POLICY = ("INCLUSIVE", "EXCLUSIVE")

BILL_CATEGORIES = ("WATER", "ELECTRICITY", "GAS", "INTERNET", "PHONE", "RENT", "CONDOMINIUM", "INSURANCE", "SUBSCRIPTION", "OTHER")
BILL_STATUS = ("ACTIVE", "PAID", "OVERDUE", "CANCELLED", "SKIPPED")
RECURRENCE_FREQUENCY = ("MONTHLY", "BIMONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL", "CUSTOM")
BILL_INSTALLMENT_STATUS = ("PENDING", "POSTED", "PAID", "REVERSED", "CANCELLED", "SKIPPED")
RECURRENCE_STATUS = ("ACTIVE", "PAUSED", "ENDED")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


class AppSettings(Base, Timestamps):
    __tablename__ = "app_settings"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    locale: Mapped[str] = mapped_column(String(10), default="pt-BR")
    timezone: Mapped[str] = mapped_column(String(64), default="America/Fortaleza")
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    theme: Mapped[str] = mapped_column(String(10), default="system")


class FinancialAccount(Base, UUIDPk, Timestamps):
    __tablename__ = "financial_accounts"
    __table_args__ = (
        CheckConstraint(_in("type", ACCOUNT_TYPES), name="type_valid"),
        CheckConstraint("currency = 'BRL'", name="currency_brl"),
    )

    name: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(20))
    institution: Mapped[str | None] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(9), default="#3B82F6")
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    opening_balance_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    opening_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}


class Category(Base, UUIDPk, Timestamps):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint(_in("kind", CATEGORY_KINDS), name="kind_valid"),
        UniqueConstraint("parent_id", "name", "kind", name="uq_categories_name", postgresql_nulls_not_distinct=True),
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(10))
    color: Mapped[str] = mapped_column(String(9), default="#64748B")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Person(Base, UUIDPk, Timestamps):
    """Contato financeiro. NÃO é usuário e não tem acesso ao sistema."""

    __tablename__ = "persons"

    display_name: Mapped[str] = mapped_column(String(80))
    contact: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Transaction(Base, UUIDPk, Timestamps):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(_in("kind", TX_KINDS), name="kind_valid"),
        CheckConstraint(_in("status", TX_STATUSES), name="status_valid"),
        CheckConstraint("amount_cents <> 0", name="amount_nonzero"),
        CheckConstraint(
            "(kind IN ('INCOME','TRANSFER_IN') AND amount_cents > 0)"
            " OR (kind IN ('EXPENSE','TRANSFER_OUT') AND amount_cents < 0)"
            " OR kind = 'ADJUSTMENT'",
            name="sign_matches_kind",
        ),
        CheckConstraint(
            "(kind IN ('TRANSFER_IN','TRANSFER_OUT')) = (transfer_group_id IS NOT NULL)",
            name="transfer_group_consistent",
        ),
        Index("ix_transactions_account_date", "account_id", "effective_date"),
        Index("ix_transactions_date", "effective_date"),
        Index("ix_transactions_transfer_group", "transfer_group_id"),
        Index(
            "uq_transactions_transfer_leg", "transfer_group_id", "kind", unique=True,
            postgresql_where=text("transfer_group_id IS NOT NULL"),
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("financial_accounts.id", ondelete="RESTRICT"))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(12), default="POSTED")
    effective_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(160))
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    counterparty_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("persons.id", ondelete="RESTRICT"))
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_type: Mapped[str | None] = mapped_column(String(40))
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(200))

    account: Mapped[FinancialAccount] = relationship(lazy="joined")
    category: Mapped[Category | None] = relationship(lazy="joined")
    counterparty: Mapped[Person | None] = relationship(lazy="joined")


class IdempotencyRecord(Base, Timestamps):
    __tablename__ = "idempotency_records"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    operation: Mapped[str] = mapped_column(String(40))
    payload_hash: Mapped[str] = mapped_column(String(64))
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))


class AuditEvent(Base, UUIDPk):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)

    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    operation: Mapped[str] = mapped_column(String(40))
    before_json: Mapped[dict | None] = mapped_column(JSONB)
    after_json: Mapped[dict | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    request_id: Mapped[str | None] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(20), default="owner")


class CreditCard(Base, UUIDPk, Timestamps):
    __tablename__ = "credit_cards"
    __table_args__ = (
        CheckConstraint(_in("type", CARD_TYPES), name="card_type_valid"),
        CheckConstraint(_in("brand", CARD_BRANDS), name="card_brand_valid"),
        CheckConstraint("closing_day BETWEEN 1 AND 28", name="closing_day_valid"),
        CheckConstraint("due_day BETWEEN 1 AND 28", name="due_day_valid"),
        CheckConstraint("due_month_offset IN (0, 1)", name="due_month_offset_valid"),
        CheckConstraint(_in("purchase_boundary_policy", PURCHASE_BOUNDARY_POLICY), name="purchase_boundary_valid"),
        CheckConstraint("limit_cents > 0", name="limit_positive"),
        CheckConstraint("last_four IS NULL OR last_four ~ '^[0-9]{4}$'", name="last_four_format"),
        Index("ix_credit_cards_archived", "archived_at"),
    )

    name: Mapped[str] = mapped_column(String(80))
    bank: Mapped[str | None] = mapped_column(String(80))
    nickname: Mapped[str | None] = mapped_column(String(30))
    last_four: Mapped[str | None] = mapped_column(String(4))
    brand: Mapped[str | None] = mapped_column(String(20))
    type: Mapped[str] = mapped_column(String(20), default="CREDIT")
    limit_cents: Mapped[int] = mapped_column(BigInteger)
    closing_day: Mapped[int] = mapped_column(SmallInteger)
    due_day: Mapped[int] = mapped_column(SmallInteger)
    due_month_offset: Mapped[int] = mapped_column(SmallInteger, default=1)
    purchase_boundary_policy: Mapped[str] = mapped_column(String(20), default="EXCLUSIVE")
    default_payment_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("financial_accounts.id", ondelete="SET NULL"))
    color: Mapped[str] = mapped_column(String(9), default="#3B82F6")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}


class CardStatement(Base, UUIDPk, Timestamps):
    __tablename__ = "card_statements"
    __table_args__ = (
        CheckConstraint(_in("status", STATEMENT_STATUS), name="statement_status_valid"),
        CheckConstraint("paid_cents >= 0", name="paid_cents_nonneg"),
        CheckConstraint("cycle_end_exclusive > cycle_start_date", name="cycle_dates_order"),
        UniqueConstraint("card_id", "cycle_start_date", name="uq_card_statement_cycle"),
        Index("ix_card_statements_card_due", "card_id", "due_date"),
        Index("ix_card_statements_status", "status"),
    )

    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_cards.id", ondelete="CASCADE"))
    cycle_start_date: Mapped[date] = mapped_column(Date)
    cycle_end_exclusive: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    paid_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(200))

    card: Mapped[CreditCard] = relationship(lazy="select")


class CardPurchase(Base, UUIDPk, Timestamps):
    __tablename__ = "card_purchases"
    __table_args__ = (
        CheckConstraint(_in("status", PURCHASE_STATUS), name="purchase_status_valid"),
        CheckConstraint("installments_count BETWEEN 1 AND 99", name="installments_range"),
        CheckConstraint("total_cents > 0", name="purchase_total_positive"),
        Index("ix_card_purchases_card_date", "card_id", "purchased_on"),
        Index("ix_card_purchases_category", "category_id"),
        Index("ix_card_purchases_person", "person_id"),
    )

    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_cards.id", ondelete="CASCADE"))
    purchased_on: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(160))
    merchant: Mapped[str | None] = mapped_column(String(120))
    total_cents: Mapped[int] = mapped_column(BigInteger)
    installments_count: Mapped[int] = mapped_column(SmallInteger, default=1)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    person_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("persons.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    notes: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(200))

    card: Mapped[CreditCard] = relationship(lazy="joined")
    category: Mapped[Category | None] = relationship(lazy="joined")
    person: Mapped[Person | None] = relationship(lazy="joined")


class CardInstallment(Base, UUIDPk, Timestamps):
    __tablename__ = "card_installments"
    __table_args__ = (
        CheckConstraint(_in("status", INSTALLMENT_STATUS), name="installment_status_valid"),
        CheckConstraint("installment_number > 0", name="installment_number_positive"),
        CheckConstraint("amount_cents > 0", name="installment_amount_positive"),
        UniqueConstraint("purchase_id", "installment_number", name="uq_installment_number"),
        Index("ix_card_installments_statement", "statement_id"),
        Index("ix_card_installments_status", "status"),
    )

    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("card_purchases.id", ondelete="CASCADE"))
    statement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("card_statements.id", ondelete="RESTRICT"))
    installment_number: Mapped[int] = mapped_column(SmallInteger)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    purchase: Mapped[CardPurchase] = relationship(lazy="joined")
    statement: Mapped[CardStatement] = relationship(lazy="joined")


class StatementPayment(Base, UUIDPk, Timestamps):
    __tablename__ = "statement_payments"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="payment_amount_positive"),
        UniqueConstraint("statement_id", "idempotency_key", name="uq_statement_payment_idem"),
        Index("ix_statement_payments_statement", "statement_id"),
        Index("ix_statement_payments_transaction", "transaction_id"),
    )

    statement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("card_statements.id", ondelete="CASCADE"))
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    paid_on: Mapped[date] = mapped_column(Date)
    idempotency_key: Mapped[str] = mapped_column(String(100))

    statement: Mapped[CardStatement] = relationship(lazy="joined")
    transaction: Mapped[Transaction] = relationship(lazy="joined")


class Bill(Base, UUIDPk, Timestamps):
    __tablename__ = "bills"
    __table_args__ = (
        CheckConstraint("default_amount_cents > 0", name="bill_amount_positive"),
        CheckConstraint(_in("category", BILL_CATEGORIES), name="bill_category_valid"),
        Index("ix_bills_account", "account_id"),
        Index("ix_bills_archived", "archived_at"),
        Index("ix_bills_category", "category"),
    )

    name: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(String(200))
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("financial_accounts.id", ondelete="RESTRICT"))
    default_amount_cents: Mapped[int] = mapped_column(BigInteger)
    color: Mapped[str] = mapped_column(String(9), default="#EF4444")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    account: Mapped[FinancialAccount] = relationship(lazy="select")


class BillRecurrence(Base, UUIDPk, Timestamps):
    __tablename__ = "bill_recurrences"
    __table_args__ = (
        CheckConstraint(_in("frequency", RECURRENCE_FREQUENCY), name="recurrence_frequency_valid"),
        CheckConstraint("day_of_month IS NULL OR (day_of_month BETWEEN 1 AND 31)", name="recurrence_day_valid"),
        CheckConstraint("custom_months_interval IS NULL OR custom_months_interval > 0", name="recurrence_custom_interval_positive"),
        CheckConstraint(_in("status", RECURRENCE_STATUS), name="recurrence_status_valid"),
        CheckConstraint(
            "(frequency = 'CUSTOM' AND custom_months_interval IS NOT NULL) OR (frequency != 'CUSTOM' AND custom_months_interval IS NULL)",
            name="recurrence_custom_consistent",
        ),
        Index("ix_bill_recurrences_bill", "bill_id"),
        Index("ix_bill_recurrences_status", "status"),
    )

    bill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bills.id", ondelete="CASCADE"))
    frequency: Mapped[str] = mapped_column(String(20))
    day_of_month: Mapped[int | None] = mapped_column(SmallInteger)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    custom_months_interval: Mapped[int | None] = mapped_column(SmallInteger)
    auto_post: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")

    bill: Mapped[Bill] = relationship(lazy="select")


class BillInstallment(Base, UUIDPk, Timestamps):
    __tablename__ = "bill_installments"
    __table_args__ = (
        CheckConstraint(_in("status", BILL_INSTALLMENT_STATUS), name="bill_installment_status_valid"),
        CheckConstraint("amount_cents > 0", name="bill_installment_amount_positive"),
        Index("ix_bill_installments_bill_due", "bill_id", "due_date"),
        Index("ix_bill_installments_status", "status"),
        Index("ix_bill_installments_recurrence", "recurrence_id"),
        Index("ix_bill_installments_transaction", "transaction_id"),
    )

    bill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bills.id", ondelete="CASCADE"))
    recurrence_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bill_recurrences.id", ondelete="SET NULL"))
    due_date: Mapped[date] = mapped_column(Date)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"))
    notes: Mapped[str | None] = mapped_column(Text)

    bill: Mapped[Bill] = relationship(lazy="select")
    recurrence: Mapped[BillRecurrence | None] = relationship(lazy="select")
    transaction: Mapped[Transaction | None] = relationship(lazy="select")
