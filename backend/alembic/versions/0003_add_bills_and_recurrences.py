"""add_bills_and_recurrences

Revision ID: 0003
Revises: 7f39475ba988
Create Date: 2026-11-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision = '0003'
down_revision = '7f39475ba988'
branch_labels = None
depends_on = None

TABLES = (
    "bills",
    "bill_recurrences",
    "bill_installments",
)

BILL_STATUS = ("ACTIVE", "PAID", "OVERDUE", "CANCELLED", "SKIPPED")
RECURRENCE_FREQUENCY = ("MONTHLY", "BIMONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL", "CUSTOM")
INSTALLMENT_STATUS = ("PENDING", "POSTED", "PAID", "REVERSED", "CANCELLED", "SKIPPED")


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    # ---------- bills ----------
    op.create_table(
        "bills",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),  # water, electricity, internet, rent, etc.
        sa.Column("description", sa.String(200)),
        sa.Column("account_id", pg.UUID(as_uuid=True), sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("default_amount_cents", sa.BigInteger, nullable=False),
        sa.Column("color", sa.String(9), nullable=False, default="#EF4444"),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        *_ts(),
        sa.CheckConstraint("default_amount_cents > 0", name="bill_amount_positive"),
    )
    op.create_index("ix_bills_account", "bills", ["account_id"])
    op.create_index("ix_bills_archived", "bills", ["archived_at"])
    op.create_index("ix_bills_category", "bills", ["category"])

    # ---------- bill_recurrences ----------
    op.create_table(
        "bill_recurrences",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("bill_id", pg.UUID(as_uuid=True), sa.ForeignKey("bills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),  # MONTHLY, BIMONTHLY, etc.
        sa.Column("day_of_month", sa.SmallInteger),  # 1-28 (ou 1-31 com validação no app)
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date),  # opcional, para recorrências que terminam
        sa.Column("custom_months_interval", sa.SmallInteger),  # para CUSTOM: a cada N meses
        sa.Column("auto_post", sa.Boolean, nullable=False, default=True),  # cria installment automaticamente
        sa.Column("status", sa.String(20), nullable=False, default="ACTIVE"),
        *_ts(),
        sa.CheckConstraint("frequency IN ('MONTHLY', 'BIMONTHLY', 'QUARTERLY', 'SEMIANNUAL', 'ANNUAL', 'CUSTOM')", name="recurrence_frequency_valid"),
        sa.CheckConstraint("day_of_month IS NULL OR (day_of_month BETWEEN 1 AND 31)", name="recurrence_day_valid"),
        sa.CheckConstraint("custom_months_interval IS NULL OR custom_months_interval > 0", name="recurrence_custom_interval_positive"),
        sa.CheckConstraint("status IN ('ACTIVE', 'PAUSED', 'ENDED')", name="recurrence_status_valid"),
        sa.CheckConstraint(
            "(frequency = 'CUSTOM' AND custom_months_interval IS NOT NULL) OR (frequency != 'CUSTOM' AND custom_months_interval IS NULL)",
            name="recurrence_custom_consistent",
        ),
    )
    op.create_index("ix_bill_recurrences_bill", "bill_recurrences", ["bill_id"])
    op.create_index("ix_bill_recurrences_status", "bill_recurrences", ["status"])

    # ---------- bill_installments ----------
    op.create_table(
        "bill_installments",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("bill_id", pg.UUID(as_uuid=True), sa.ForeignKey("bills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recurrence_id", pg.UUID(as_uuid=True), sa.ForeignKey("bill_recurrences.id", ondelete="SET NULL")),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="PENDING"),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("reversed_at", sa.DateTime(timezone=True)),
        sa.Column("transaction_id", pg.UUID(as_uuid=True), sa.ForeignKey("transactions.id", ondelete="RESTRICT")),
        sa.Column("notes", sa.Text),
        *_ts(),
        sa.CheckConstraint("status IN ('PENDING', 'POSTED', 'PAID', 'REVERSED', 'CANCELLED', 'SKIPPED')", name="bill_installment_status_valid"),
        sa.CheckConstraint("amount_cents > 0", name="bill_installment_amount_positive"),
    )
    op.create_index("ix_bill_installments_bill_due", "bill_installments", ["bill_id", "due_date"])
    op.create_index("ix_bill_installments_status", "bill_installments", ["status"])
    op.create_index("ix_bill_installments_recurrence", "bill_installments", ["recurrence_id"])
    op.create_index("ix_bill_installments_transaction", "bill_installments", ["transaction_id"])

    # ---------- RLS (defesa em profundidade) ----------
    conn = op.get_bind()
    has_roles = conn.execute(
        sa.text("SELECT count(*) FROM pg_roles WHERE rolname IN ('anon','authenticated')")
    ).scalar()
    for t in TABLES:
        op.execute(f"ALTER TABLE public.{t} ENABLE ROW LEVEL SECURITY")
        if has_roles:
            op.execute(f"REVOKE ALL ON public.{t} FROM anon, authenticated")


def downgrade() -> None:
    for t in reversed(TABLES):
        op.drop_table(t)