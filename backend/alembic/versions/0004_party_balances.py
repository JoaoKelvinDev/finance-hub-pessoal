"""Etapa 4 — valores com terceiros (party_balances, settlements, adjustments) e novos kinds

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

TABLES = ("party_balances", "party_settlements", "party_adjustments")

OLD_KINDS = ("INCOME", "EXPENSE", "TRANSFER_IN", "TRANSFER_OUT", "ADJUSTMENT")
NEW_KINDS = OLD_KINDS + ("LOAN_OUT", "LOAN_IN", "SETTLEMENT_IN", "SETTLEMENT_OUT")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


def _sign(pos: tuple[str, ...], neg: tuple[str, ...]) -> str:
    return (
        f"({_in('kind', pos)} AND amount_cents > 0)"
        f" OR ({_in('kind', neg)} AND amount_cents < 0)"
        " OR kind = 'ADJUSTMENT'"
    )


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _replace_tx_checks(kinds, pos, neg) -> None:
    op.execute("ALTER TABLE transactions DROP CONSTRAINT ck_transactions_kind_valid")
    op.execute("ALTER TABLE transactions DROP CONSTRAINT ck_transactions_sign_matches_kind")
    op.execute(f"ALTER TABLE transactions ADD CONSTRAINT ck_transactions_kind_valid CHECK ({_in('kind', kinds)})")
    op.execute(f"ALTER TABLE transactions ADD CONSTRAINT ck_transactions_sign_matches_kind CHECK ({_sign(pos, neg)})")


def upgrade() -> None:
    _replace_tx_checks(
        NEW_KINDS,
        ("INCOME", "TRANSFER_IN", "LOAN_IN", "SETTLEMENT_IN"),
        ("EXPENSE", "TRANSFER_OUT", "LOAN_OUT", "SETTLEMENT_OUT"),
    )

    op.create_table(
        "party_balances",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("person_id", pg.UUID(as_uuid=True), sa.ForeignKey("persons.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("direction", sa.String(12), nullable=False),
        sa.Column("origin_type", sa.String(20), nullable=False),
        sa.Column("description", sa.String(160), nullable=False),
        sa.Column("principal_cents", sa.BigInteger, nullable=False),
        sa.Column("operation_date", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date),
        sa.Column("account_id", pg.UUID(as_uuid=True), sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT")),
        sa.Column("origin_transaction_id", pg.UUID(as_uuid=True), sa.ForeignKey("transactions.id", ondelete="RESTRICT")),
        sa.Column("notes", sa.Text),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(200)),
        *_ts(),
        sa.CheckConstraint("direction IN ('RECEIVABLE', 'PAYABLE')", name="ck_party_balances_direction_valid"),
        sa.CheckConstraint(
            "origin_type IN ('LOAN_GIVEN', 'LOAN_TAKEN', 'ADVANCE', 'OWED_TO_ME', 'I_OWE')",
            name="ck_party_balances_origin_valid",
        ),
        sa.CheckConstraint("principal_cents > 0", name="ck_party_balances_principal_positive"),
        sa.CheckConstraint(
            "(origin_type IN ('LOAN_GIVEN','ADVANCE','OWED_TO_ME') AND direction = 'RECEIVABLE')"
            " OR (origin_type IN ('LOAN_TAKEN','I_OWE') AND direction = 'PAYABLE')",
            name="ck_party_balances_origin_direction_consistent",
        ),
        sa.CheckConstraint(
            "(origin_type IN ('LOAN_GIVEN','LOAN_TAKEN','ADVANCE')) = (origin_transaction_id IS NOT NULL)",
            name="ck_party_balances_cash_origin_consistent",
        ),
    )
    op.create_index("ix_party_balances_person", "party_balances", ["person_id"])
    op.create_index("ix_party_balances_due", "party_balances", ["due_date"])

    op.create_table(
        "party_settlements",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "party_balance_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("party_balances.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("transaction_id", pg.UUID(as_uuid=True), sa.ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("settled_on", sa.Date, nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("reversed_at", sa.DateTime(timezone=True)),
        sa.Column("reverse_reason", sa.String(200)),
        *_ts(),
        sa.CheckConstraint("amount_cents > 0", name="ck_party_settlements_amount_positive"),
    )
    op.create_index("ix_party_settlements_balance", "party_settlements", ["party_balance_id"])
    op.create_index("ix_party_settlements_transaction", "party_settlements", ["transaction_id"], unique=True)

    op.create_table(
        "party_adjustments",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "party_balance_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("party_balances.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("applied_on", sa.Date, nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("reversed_at", sa.DateTime(timezone=True)),
        *_ts(),
        sa.CheckConstraint("kind IN ('CHARGE', 'DISCOUNT')", name="ck_party_adjustments_kind_valid"),
        sa.CheckConstraint("amount_cents > 0", name="ck_party_adjustments_amount_positive"),
    )
    op.create_index("ix_party_adjustments_balance", "party_adjustments", ["party_balance_id"])

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
    # Falha de propósito se ainda houver lançamentos com os kinds novos (não apagamos histórico).
    _replace_tx_checks(OLD_KINDS, ("INCOME", "TRANSFER_IN"), ("EXPENSE", "TRANSFER_OUT"))
