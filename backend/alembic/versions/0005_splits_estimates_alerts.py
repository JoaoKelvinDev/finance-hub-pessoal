"""Etapa 3 (fechamento) — estimado × real, rateio da casa e alertas in-app

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TABLES = ("expense_splits", "expense_split_parts", "alert_dismissals")


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    # ---------- estimado × real ----------
    op.add_column("bills", sa.Column("variable_amount", sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column(
        "bill_installments", sa.Column("is_estimate", sa.Boolean, nullable=False, server_default=sa.false())
    )
    op.add_column("bill_installments", sa.Column("estimated_amount_cents", sa.BigInteger))
    op.create_check_constraint(
        "ck_bill_installments_estimated_positive",
        "bill_installments",
        "estimated_amount_cents IS NULL OR estimated_amount_cents > 0",
    )

    # ---------- configuração de alertas ----------
    op.add_column(
        "app_settings",
        sa.Column("alert_card_utilization_pct", sa.SmallInteger, nullable=False, server_default="80"),
    )
    op.create_check_constraint(
        "ck_app_settings_alert_card_pct_range", "app_settings", "alert_card_utilization_pct BETWEEN 1 AND 100"
    )

    # ---------- rateio ----------
    op.create_table(
        "expense_splits",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bill_installment_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("bill_installments.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("include_owner", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("total_cents", sa.BigInteger, nullable=False),
        sa.Column("owner_share_cents", sa.BigInteger, nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(200)),
        *_ts(),
        sa.CheckConstraint("method IN ('EQUAL', 'FIXED', 'PERCENT')", name="ck_expense_splits_method_valid"),
        sa.CheckConstraint("total_cents > 0", name="ck_expense_splits_total_positive"),
        sa.CheckConstraint(
            "owner_share_cents >= 0 AND owner_share_cents <= total_cents", name="ck_expense_splits_owner_share_range"
        ),
    )
    op.create_index(
        "uq_expense_splits_active_installment", "expense_splits", ["bill_installment_id"],
        unique=True, postgresql_where=sa.text("cancelled_at IS NULL"),
    )

    op.create_table(
        "expense_split_parts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("split_id", pg.UUID(as_uuid=True), sa.ForeignKey("expense_splits.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("person_id", pg.UUID(as_uuid=True), sa.ForeignKey("persons.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("share_cents", sa.BigInteger, nullable=False),
        sa.Column("percent_bp", sa.Integer),
        sa.Column(
            "party_balance_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("party_balances.id", ondelete="RESTRICT"), nullable=False,
        ),
        *_ts(),
        sa.CheckConstraint("share_cents > 0", name="ck_expense_split_parts_share_positive"),
        sa.CheckConstraint(
            "percent_bp IS NULL OR (percent_bp > 0 AND percent_bp <= 10000)", name="ck_expense_split_parts_percent_range"
        ),
        sa.UniqueConstraint("split_id", "person_id", name="uq_split_part_person"),
        sa.UniqueConstraint("party_balance_id", name="uq_split_part_balance"),
    )

    # ---------- alertas dispensados ----------
    op.create_table(
        "alert_dismissals",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

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
    op.drop_constraint("ck_app_settings_alert_card_pct_range", "app_settings", type_="check")
    op.drop_column("app_settings", "alert_card_utilization_pct")
    op.drop_constraint("ck_bill_installments_estimated_positive", "bill_installments", type_="check")
    op.drop_column("bill_installments", "estimated_amount_cents")
    op.drop_column("bill_installments", "is_estimate")
    op.drop_column("bills", "variable_amount")
