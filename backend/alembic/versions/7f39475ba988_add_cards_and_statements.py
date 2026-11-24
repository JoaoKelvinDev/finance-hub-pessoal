"""add_cards_and_statements

Revision ID: 7f39475ba988
Revises: 0001
Create Date: 2026-11-24 15:45:41.316565
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision = '7f39475ba988'
down_revision = '0001'
branch_labels = None
depends_on = None

TABLES = (
    "credit_cards",
    "card_statements",
    "card_purchases",
    "card_installments",
    "statement_payments",
)

CARD_TYPES = ("CREDIT", "DEBIT", "PREPAID")
CARD_BRANDS = ("VISA", "MASTERCARD", "ELO", "AMEX", "HIPERCARD", "OTHER")
STATEMENT_STATUS = ("OPEN", "CLOSED", "PARTIALLY_PAID", "PAID", "OVERDUE", "CANCELLED")
PURCHASE_STATUS = ("ACTIVE", "REVERSED", "CANCELLED")
INSTALLMENT_STATUS = ("PENDING", "POSTED", "PAID", "REVERSED", "CANCELLED")
PURCHASE_BOUNDARY_POLICY = ("INCLUSIVE", "EXCLUSIVE")  # compra no dia do fechamento entra no ciclo atual ou próximo


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    # ---------- credit_cards ----------
    op.create_table(
        "credit_cards",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("bank", sa.String(80)),
        sa.Column("nickname", sa.String(30)),
        sa.Column("last_four", sa.String(4)),
        sa.Column("brand", sa.String(20)),
        sa.Column("type", sa.String(20), nullable=False, default="CREDIT"),
        sa.Column("limit_cents", sa.BigInteger, nullable=False),
        sa.Column("closing_day", sa.SmallInteger, nullable=False),
        sa.Column("due_day", sa.SmallInteger, nullable=False),
        sa.Column("due_month_offset", sa.SmallInteger, nullable=False, default=1),
        sa.Column("purchase_boundary_policy", sa.String(20), nullable=False, default="EXCLUSIVE"),
        sa.Column("default_payment_account_id", pg.UUID(as_uuid=True), sa.ForeignKey("financial_accounts.id", ondelete="SET NULL")),
        sa.Column("color", sa.String(9), nullable=False, default="#3B82F6"),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        *_ts(),
        sa.CheckConstraint("type IN ('CREDIT', 'DEBIT', 'PREPAID')", name="card_type_valid"),
        sa.CheckConstraint("brand IS NULL OR brand IN ('VISA', 'MASTERCARD', 'ELO', 'AMEX', 'HIPERCARD', 'OTHER')", name="card_brand_valid"),
        sa.CheckConstraint("closing_day BETWEEN 1 AND 28", name="closing_day_valid"),
        sa.CheckConstraint("due_day BETWEEN 1 AND 28", name="due_day_valid"),
        sa.CheckConstraint("due_month_offset IN (0, 1)", name="due_month_offset_valid"),
        sa.CheckConstraint("purchase_boundary_policy IN ('INCLUSIVE', 'EXCLUSIVE')", name="purchase_boundary_valid"),
        sa.CheckConstraint("limit_cents > 0", name="limit_positive"),
        sa.CheckConstraint("last_four IS NULL OR last_four ~ '^[0-9]{4}$'", name="last_four_format"),
    )
    op.create_index("ix_credit_cards_archived", "credit_cards", ["archived_at"])

    # ---------- card_statements ----------
    op.create_table(
        "card_statements",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("card_id", pg.UUID(as_uuid=True), sa.ForeignKey("credit_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cycle_start_date", sa.Date, nullable=False),
        sa.Column("cycle_end_exclusive", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="OPEN"),
        sa.Column("paid_cents", sa.BigInteger, nullable=False, default=0),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(200)),
        *_ts(),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED', 'PARTIALLY_PAID', 'PAID', 'OVERDUE', 'CANCELLED')", name="statement_status_valid"),
        sa.CheckConstraint("paid_cents >= 0", name="paid_cents_nonneg"),
        sa.CheckConstraint("cycle_end_exclusive > cycle_start_date", name="cycle_dates_order"),
        sa.UniqueConstraint("card_id", "cycle_start_date", name="uq_card_statement_cycle"),
    )
    op.create_index("ix_card_statements_card_due", "card_statements", ["card_id", "due_date"])
    op.create_index("ix_card_statements_status", "card_statements", ["status"])

    # ---------- card_purchases ----------
    op.create_table(
        "card_purchases",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("card_id", pg.UUID(as_uuid=True), sa.ForeignKey("credit_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purchased_on", sa.Date, nullable=False),
        sa.Column("description", sa.String(160), nullable=False),
        sa.Column("merchant", sa.String(120)),
        sa.Column("total_cents", sa.BigInteger, nullable=False),
        sa.Column("installments_count", sa.SmallInteger, nullable=False, default=1),
        sa.Column("category_id", pg.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="RESTRICT")),
        sa.Column("person_id", pg.UUID(as_uuid=True), sa.ForeignKey("persons.id", ondelete="RESTRICT")),
        sa.Column("status", sa.String(20), nullable=False, default="ACTIVE"),
        sa.Column("notes", sa.Text),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(200)),
        *_ts(),
        sa.CheckConstraint("status IN ('ACTIVE', 'REVERSED', 'CANCELLED')", name="purchase_status_valid"),
        sa.CheckConstraint("installments_count BETWEEN 1 AND 99", name="installments_range"),
        sa.CheckConstraint("total_cents > 0", name="purchase_total_positive"),
    )
    op.create_index("ix_card_purchases_card_date", "card_purchases", ["card_id", "purchased_on"])
    op.create_index("ix_card_purchases_category", "card_purchases", ["category_id"])
    op.create_index("ix_card_purchases_person", "card_purchases", ["person_id"])

    # ---------- card_installments ----------
    op.create_table(
        "card_installments",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("purchase_id", pg.UUID(as_uuid=True), sa.ForeignKey("card_purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("statement_id", pg.UUID(as_uuid=True), sa.ForeignKey("card_statements.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("installment_number", sa.SmallInteger, nullable=False),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="PENDING"),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("reversed_at", sa.DateTime(timezone=True)),
        *_ts(),
        sa.CheckConstraint("status IN ('PENDING', 'POSTED', 'PAID', 'REVERSED', 'CANCELLED')", name="installment_status_valid"),
        sa.CheckConstraint("installment_number > 0", name="installment_number_positive"),
        sa.CheckConstraint("amount_cents > 0", name="installment_amount_positive"),
        sa.UniqueConstraint("purchase_id", "installment_number", name="uq_installment_number"),
    )
    op.create_index("ix_card_installments_statement", "card_installments", ["statement_id"])
    op.create_index("ix_card_installments_status", "card_installments", ["status"])

    # ---------- statement_payments ----------
    op.create_table(
        "statement_payments",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("statement_id", pg.UUID(as_uuid=True), sa.ForeignKey("card_statements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_id", pg.UUID(as_uuid=True), sa.ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("paid_on", sa.Date, nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        *_ts(),
        sa.CheckConstraint("amount_cents > 0", name="payment_amount_positive"),
        sa.UniqueConstraint("statement_id", "idempotency_key", name="uq_statement_payment_idem"),
    )
    op.create_index("ix_statement_payments_statement", "statement_payments", ["statement_id"])
    op.create_index("ix_statement_payments_transaction", "statement_payments", ["transaction_id"])

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