"""Etapa 5 — Planejamento: orçamentos e metas

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

TABLES = ("budgets", "goals", "goal_allocations")


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("category_id", pg.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="RESTRICT")),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("limit_cents", sa.BigInteger, nullable=False),
        sa.Column("basis", sa.String(12), nullable=False, server_default="CASH"),
        sa.Column("notes", sa.Text),
        *_ts(),
        sa.CheckConstraint("basis IN ('CASH', 'COMPETENCE')", name="ck_budgets_basis_valid"),
        sa.CheckConstraint("limit_cents > 0", name="ck_budgets_limit_positive"),
        sa.CheckConstraint("period_end >= period_start", name="ck_budgets_period_valid"),
        sa.UniqueConstraint(
            "category_id", "period_start", "period_end", name="uq_budget_period", postgresql_nulls_not_distinct=True
        ),
    )
    op.create_index("ix_budgets_period", "budgets", ["period_start", "period_end"])

    op.create_table(
        "goals",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("target_cents", sa.BigInteger, nullable=False),
        sa.Column("target_date", sa.Date),
        sa.Column("state", sa.String(12), nullable=False, server_default="ACTIVE"),
        sa.Column("notes", sa.Text),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(200)),
        *_ts(),
        sa.CheckConstraint("target_cents > 0", name="ck_goals_target_positive"),
        sa.CheckConstraint("state IN ('ACTIVE', 'ACHIEVED', 'CANCELLED')", name="ck_goals_state_valid"),
        sa.CheckConstraint("state != 'CANCELLED' OR cancelled_at IS NOT NULL", name="ck_goals_cancelled_consistent"),
    )

    op.create_table(
        "goal_allocations",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("goal_id", pg.UUID(as_uuid=True), sa.ForeignKey("goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("allocated_on", sa.Date, nullable=False),
        sa.Column("transfer_reference", sa.String(120)),
        sa.Column("transfer_group_id", pg.UUID(as_uuid=True)),
        sa.Column("notes", sa.Text),
        sa.Column("reversed_at", sa.DateTime(timezone=True)),
        sa.Column("reverse_reason", sa.String(200)),
        *_ts(),
        sa.CheckConstraint("amount_cents > 0", name="ck_goal_allocations_amount_positive"),
    )
    op.create_index("ix_goal_allocations_goal", "goal_allocations", ["goal_id"])

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
