"""schema inicial single-user: settings, contas, categorias, pessoas, transações, idempotência, auditoria

Revision ID: 0001
Revises:
Create Date: 2026-11-24
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = (
    "app_settings",
    "financial_accounts",
    "categories",
    "persons",
    "transactions",
    "idempotency_records",
    "audit_events",
)

# Cores = slots 1–7 da paleta categórica validada (dataviz), na ordem fixa; subcategorias herdam a do pai.
CATEGORIES = {
    "EXPENSE": {
        "Moradia": ("#2A78D6", ["Aluguel", "Condomínio", "Energia", "Água", "Gás", "Internet", "Telefone", "IPTU"]),
        "Alimentação": ("#EB6834", ["Mercado", "Feira", "Delivery"]),
        "Transporte": ("#1BAF7A", ["Combustível", "Manutenção", "Transporte público"]),
        "Educação": ("#EDA100", ["Faculdade", "Cursos", "Material"]),
        "Saúde": ("#E87BA4", ["Consultas", "Medicamentos", "Plano de saúde"]),
        "Assinaturas": ("#008300", ["Streaming", "Software", "Academia"]),
        "Outros": ("#6250D6", ["Lazer", "Pets", "Compras", "Imprevistos"]),
    },
    "INCOME": {
        "Salário": ("#2A78D6", []),
        "Renda extra": ("#EB6834", []),
        "Rendimentos": ("#1BAF7A", []),
        "Outras receitas": ("#EDA100", []),
    },
}


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.SmallInteger, primary_key=True),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("theme", sa.String(10), nullable=False),
        *_ts(),
        sa.CheckConstraint("id = 1", name="singleton"),
    )

    op.create_table(
        "financial_accounts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("institution", sa.String(80)),
        sa.Column("color", sa.String(9), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("opening_balance_cents", sa.BigInteger, nullable=False),
        sa.Column("opening_date", sa.Date, nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False),
        *_ts(),
        sa.CheckConstraint("type IN ('CHECKING', 'SAVINGS', 'CASH', 'DIGITAL_WALLET', 'OTHER')", name="type_valid"),
        sa.CheckConstraint("currency = 'BRL'", name="currency_brl"),
    )

    op.create_table(
        "categories",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_id", pg.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="RESTRICT")),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("color", sa.String(9), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        *_ts(),
        sa.CheckConstraint("kind IN ('INCOME', 'EXPENSE')", name="kind_valid"),
        sa.UniqueConstraint("parent_id", "name", "kind", name="uq_categories_name", postgresql_nulls_not_distinct=True),
    )

    op.create_table(
        "persons",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("contact", sa.String(120)),
        sa.Column("notes", sa.Text),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        *_ts(),
    )

    op.create_table(
        "transactions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id", pg.UUID(as_uuid=True), sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("description", sa.String(160), nullable=False),
        sa.Column("category_id", pg.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="RESTRICT")),
        sa.Column("counterparty_id", pg.UUID(as_uuid=True), sa.ForeignKey("persons.id", ondelete="RESTRICT")),
        sa.Column("transfer_group_id", pg.UUID(as_uuid=True)),
        sa.Column("source_type", sa.String(40)),
        sa.Column("source_id", pg.UUID(as_uuid=True)),
        sa.Column("notes", sa.Text),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(200)),
        *_ts(),
        sa.CheckConstraint(
            "kind IN ('INCOME', 'EXPENSE', 'TRANSFER_IN', 'TRANSFER_OUT', 'ADJUSTMENT')", name="kind_valid"
        ),
        sa.CheckConstraint("status IN ('PLANNED', 'POSTED', 'CANCELLED')", name="status_valid"),
        sa.CheckConstraint("amount_cents <> 0", name="amount_nonzero"),
        sa.CheckConstraint(
            "(kind IN ('INCOME','TRANSFER_IN') AND amount_cents > 0)"
            " OR (kind IN ('EXPENSE','TRANSFER_OUT') AND amount_cents < 0)"
            " OR kind = 'ADJUSTMENT'",
            name="sign_matches_kind",
        ),
        sa.CheckConstraint(
            "(kind IN ('TRANSFER_IN','TRANSFER_OUT')) = (transfer_group_id IS NOT NULL)",
            name="transfer_group_consistent",
        ),
    )
    op.create_index("ix_transactions_account_date", "transactions", ["account_id", "effective_date"])
    op.create_index("ix_transactions_date", "transactions", ["effective_date"])
    op.create_index("ix_transactions_transfer_group", "transactions", ["transfer_group_id"])
    # No máximo uma perna de cada lado por transferência.
    op.create_index(
        "uq_transactions_transfer_leg", "transactions", ["transfer_group_id", "kind"], unique=True,
        postgresql_where=sa.text("transfer_group_id IS NOT NULL"),
    )

    op.create_table(
        "idempotency_records",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("result_id", pg.UUID(as_uuid=True), nullable=False),
        *_ts(),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("before_json", pg.JSONB),
        sa.Column("after_json", pg.JSONB),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("request_id", sa.String(64)),
        sa.Column("actor", sa.String(20), nullable=False),
    )
    op.create_index("ix_audit_entity", "audit_events", ["entity_type", "entity_id"])

    # Defesa em profundidade: dados financeiros nunca acessíveis pelo PostgREST/anon key.
    conn = op.get_bind()
    has_roles = conn.execute(
        sa.text("SELECT count(*) FROM pg_roles WHERE rolname IN ('anon','authenticated')")
    ).scalar()
    for t in TABLES:
        op.execute(f"ALTER TABLE public.{t} ENABLE ROW LEVEL SECURITY")
        if has_roles:
            op.execute(f"REVOKE ALL ON public.{t} FROM anon, authenticated")

    op.execute(
        "INSERT INTO app_settings (id, locale, timezone, currency, theme) "
        "VALUES (1, 'pt-BR', 'America/Fortaleza', 'BRL', 'system')"
    )
    _seed_categories()


def _seed_categories() -> None:
    cats = sa.table(
        "categories",
        sa.column("id", pg.UUID(as_uuid=True)),
        sa.column("parent_id", pg.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("kind", sa.String),
        sa.column("color", sa.String),
    )
    rows = []
    for kind, groups in CATEGORIES.items():
        for name, (color, children) in groups.items():
            pid = uuid.uuid4()
            rows.append({"id": pid, "parent_id": None, "name": name, "kind": kind, "color": color})
            rows += [
                {"id": uuid.uuid4(), "parent_id": pid, "name": c, "kind": kind, "color": color} for c in children
            ]
    op.bulk_insert(cats, rows)


def downgrade() -> None:
    for t in reversed(TABLES):
        op.drop_table(t)
