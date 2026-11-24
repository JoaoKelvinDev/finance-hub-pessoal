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
