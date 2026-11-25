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
TX_KINDS = (
    "INCOME", "EXPENSE", "TRANSFER_IN", "TRANSFER_OUT", "ADJUSTMENT",
    # Etapa 4 — terceiros: movimentam caixa, mas nunca são receita/despesa.
    "LOAN_OUT", "LOAN_IN", "SETTLEMENT_IN", "SETTLEMENT_OUT",
)
# Sinal obrigatório por kind (ADJUSTMENT é livre).
TX_POSITIVE_KINDS = ("INCOME", "TRANSFER_IN", "LOAN_IN", "SETTLEMENT_IN")
TX_NEGATIVE_KINDS = ("EXPENSE", "TRANSFER_OUT", "LOAN_OUT", "SETTLEMENT_OUT")

PARTY_DIRECTIONS = ("RECEIVABLE", "PAYABLE")
PARTY_ORIGINS = ("LOAN_GIVEN", "LOAN_TAKEN", "ADVANCE", "OWED_TO_ME", "I_OWE")
PARTY_ADJUSTMENT_KINDS = ("CHARGE", "DISCOUNT")
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


TX_SIGN_CHECK = (
    f"({_in('kind', TX_POSITIVE_KINDS)} AND amount_cents > 0)"
    f" OR ({_in('kind', TX_NEGATIVE_KINDS)} AND amount_cents < 0)"
    " OR kind = 'ADJUSTMENT'"
)


class AppSettings(Base, Timestamps):
    __tablename__ = "app_settings"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    locale: Mapped[str] = mapped_column(String(10), default="pt-BR")
    timezone: Mapped[str] = mapped_column(String(64), default="America/Fortaleza")
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    theme: Mapped[str] = mapped_column(String(10), default="system")
    # Alerta quando a fatura atual passar deste % do limite do cartão.
    alert_card_utilization_pct: Mapped[int] = mapped_column(SmallInteger, default=80)


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
        CheckConstraint(TX_SIGN_CHECK, name="sign_matches_kind"),
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
    # Conta variável (luz, água): parcelas geradas nascem como estimativa.
    variable_amount: Mapped[bool] = mapped_column(default=False)
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
    # Estimado × real: enquanto is_estimate, amount_cents é provisório.
    is_estimate: Mapped[bool] = mapped_column(default=False)
    # Valor estimado original, preservado quando o real é confirmado.
    estimated_amount_cents: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"))
    notes: Mapped[str | None] = mapped_column(Text)

    bill: Mapped[Bill] = relationship(lazy="select")
    recurrence: Mapped[BillRecurrence | None] = relationship(lazy="select")
    transaction: Mapped[Transaction | None] = relationship(lazy="select")
    # Rateio ativo (no máximo um por parcela).
    split: Mapped["ExpenseSplit | None"] = relationship(
        primaryjoin="and_(ExpenseSplit.bill_installment_id == BillInstallment.id, ExpenseSplit.cancelled_at.is_(None))",
        viewonly=True,
        uselist=False,
        lazy="select",
    )


# ---------- Etapa 4 — Valores com terceiros ----------

class PartyBalance(Base, UUIDPk, Timestamps):
    """Valor a receber de / a devolver para um contato (que NÃO é usuário).

    Saldo em aberto = principal + encargos − descontos − acertos ativos (sempre derivado).
    """

    __tablename__ = "party_balances"
    __table_args__ = (
        CheckConstraint(_in("direction", PARTY_DIRECTIONS), name="direction_valid"),
        CheckConstraint(_in("origin_type", PARTY_ORIGINS), name="origin_valid"),
        CheckConstraint("principal_cents > 0", name="principal_positive"),
        CheckConstraint(
            "(origin_type IN ('LOAN_GIVEN','ADVANCE','OWED_TO_ME') AND direction = 'RECEIVABLE')"
            " OR (origin_type IN ('LOAN_TAKEN','I_OWE') AND direction = 'PAYABLE')",
            name="origin_direction_consistent",
        ),
        CheckConstraint(
            "(origin_type IN ('LOAN_GIVEN','LOAN_TAKEN','ADVANCE')) = (origin_transaction_id IS NOT NULL)",
            name="cash_origin_consistent",
        ),
        Index("ix_party_balances_person", "person_id"),
        Index("ix_party_balances_due", "due_date"),
    )

    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("persons.id", ondelete="RESTRICT"))
    direction: Mapped[str] = mapped_column(String(12))
    origin_type: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(160))
    principal_cents: Mapped[int] = mapped_column(BigInteger)
    operation_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("financial_accounts.id", ondelete="RESTRICT"))
    origin_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"))
    notes: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(200))

    person: Mapped[Person] = relationship(lazy="joined")
    account: Mapped[FinancialAccount | None] = relationship(lazy="joined")


class PartySettlement(Base, UUIDPk, Timestamps):
    """Acerto (parcial ou integral) de um PartyBalance, sempre com movimento de caixa."""

    __tablename__ = "party_settlements"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        Index("ix_party_settlements_balance", "party_balance_id"),
        Index("ix_party_settlements_transaction", "transaction_id", unique=True),
    )

    party_balance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("party_balances.id", ondelete="RESTRICT"))
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    settled_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reverse_reason: Mapped[str | None] = mapped_column(String(200))

    transaction: Mapped[Transaction] = relationship(lazy="joined")


class PartyAdjustment(Base, UUIDPk, Timestamps):
    """Encargo (juros/multa) ou desconto (inclui perdão) sobre um PartyBalance. Não movimenta caixa."""

    __tablename__ = "party_adjustments"
    __table_args__ = (
        CheckConstraint(_in("kind", PARTY_ADJUSTMENT_KINDS), name="kind_valid"),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        Index("ix_party_adjustments_balance", "party_balance_id"),
    )

    party_balance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("party_balances.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(10))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    applied_on: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(200))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------- Etapa 3 (fechamento) — rateio e alertas ----------

SPLIT_METHODS = ("EQUAL", "FIXED", "PERCENT")


class ExpenseSplit(Base, UUIDPk, Timestamps):
    """Rateio de uma parcela de conta da casa entre contatos (sem login).

    A despesa original continua bruta; cada parte alheia vira um PartyBalance OWED_TO_ME.
    """

    __tablename__ = "expense_splits"
    __table_args__ = (
        CheckConstraint(_in("method", SPLIT_METHODS), name="method_valid"),
        CheckConstraint("total_cents > 0", name="total_positive"),
        CheckConstraint("owner_share_cents >= 0 AND owner_share_cents <= total_cents", name="owner_share_range"),
        Index(
            "uq_expense_splits_active_installment", "bill_installment_id", unique=True,
            postgresql_where=text("cancelled_at IS NULL"),
        ),
    )

    bill_installment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bill_installments.id", ondelete="RESTRICT"))
    method: Mapped[str] = mapped_column(String(10))
    include_owner: Mapped[bool] = mapped_column(default=True)
    total_cents: Mapped[int] = mapped_column(BigInteger)
    owner_share_cents: Mapped[int] = mapped_column(BigInteger)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(200))

    parts: Mapped[list["ExpenseSplitPart"]] = relationship(
        lazy="selectin", order_by="ExpenseSplitPart.created_at", back_populates="split"
    )


class ExpenseSplitPart(Base, UUIDPk, Timestamps):
    __tablename__ = "expense_split_parts"
    __table_args__ = (
        CheckConstraint("share_cents > 0", name="share_positive"),
        CheckConstraint("percent_bp IS NULL OR (percent_bp > 0 AND percent_bp <= 10000)", name="percent_range"),
        UniqueConstraint("split_id", "person_id", name="uq_split_part_person"),
        UniqueConstraint("party_balance_id", name="uq_split_part_balance"),
    )

    split_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expense_splits.id", ondelete="RESTRICT"))
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("persons.id", ondelete="RESTRICT"))
    share_cents: Mapped[int] = mapped_column(BigInteger)
    # Percentual em pontos-base (100% = 10000), só no método PERCENT.
    percent_bp: Mapped[int | None] = mapped_column(Integer)
    party_balance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("party_balances.id", ondelete="RESTRICT"))

    split: Mapped[ExpenseSplit] = relationship(back_populates="parts")
    person: Mapped[Person] = relationship(lazy="joined")


class AlertDismissal(Base):
    """Alerta dispensado. A chave inclui o estágio (ex.: D-3), então um agravamento reaparece."""

    __tablename__ = "alert_dismissals"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------- Etapa 5 — Planejamento: orçamentos e metas ----------

BUDGET_BASES = ("CASH", "COMPETENCE")
GOAL_STATES = ("ACTIVE", "ACHIEVED", "CANCELLED")


class Budget(Base, UUIDPk, Timestamps):
    """Orçamento por categoria e período.

    `category_id` nulo = orçamento geral (todas as categorias de despesa).
    `basis` define o que conta como consumo: caixa (pago no período) ou
    competência (consumo atribuído ao período).
    """

    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint(_in("basis", BUDGET_BASES), name="basis_valid"),
        CheckConstraint("limit_cents > 0", name="limit_positive"),
        CheckConstraint("period_end >= period_start", name="period_valid"),
        UniqueConstraint(
            "category_id", "period_start", "period_end", name="uq_budget_period", postgresql_nulls_not_distinct=True
        ),
        Index("ix_budgets_period", "period_start", "period_end"),
    )

    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    limit_cents: Mapped[int] = mapped_column(BigInteger)
    basis: Mapped[str] = mapped_column(String(12), default="CASH")
    notes: Mapped[str | None] = mapped_column(Text)

    category: Mapped[Category | None] = relationship(lazy="joined")


class Goal(Base, UUIDPk, Timestamps):
    """Meta ou reserva (emergência, viagem etc.). Aportes são rastreados e não viram gasto."""

    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("target_cents > 0", name="target_positive"),
        CheckConstraint(_in("state", GOAL_STATES), name="state_valid"),
        CheckConstraint("state != 'CANCELLED' OR cancelled_at IS NOT NULL", name="cancelled_consistent"),
    )

    title: Mapped[str] = mapped_column(String(80))
    target_cents: Mapped[int] = mapped_column(BigInteger)
    target_date: Mapped[date | None] = mapped_column(Date)
    state: Mapped[str] = mapped_column(String(12), default="ACTIVE")
    notes: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(200))

    allocations: Mapped[list["GoalAllocation"]] = relationship(
        lazy="selectin", order_by="GoalAllocation.allocated_on", back_populates="goal"
    )


class GoalAllocation(Base, UUIDPk, Timestamps):
    """Aporte na meta. Não é receita nem despesa: sai de uma conta para outra."""

    __tablename__ = "goal_allocations"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        Index("ix_goal_allocations_goal", "goal_id"),
    )

    goal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    allocated_on: Mapped[date] = mapped_column(Date)
    # Referência opcional da transferência interna que originou o aporte.
    transfer_reference: Mapped[str | None] = mapped_column(String(120))
    # Transferência real entre contas próprias (aporte com caixa); estornada junto com o aporte.
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reverse_reason: Mapped[str | None] = mapped_column(String(200))

    goal: Mapped[Goal] = relationship(back_populates="allocations")
