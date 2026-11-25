"""Backup completo (JSON) e restauração SOMENTE em banco vazio.

- O backup inclui todas as tabelas do modelo, na ordem de dependência (FKs), mais a
  revisão do Alembic. Valores monetários continuam em centavos inteiros.
- A restauração recusa qualquer banco que já tenha dados financeiros: nunca sobrescreve.
  As categorias e configurações semeadas pela migração são substituídas pelas do backup.
- É feita numa única transação: ou entra tudo, ou nada.
"""

import base64
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, LargeBinary, Table, delete, func, insert, select, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import Base

FORMAT = "finance-hub-backup"
FORMAT_VERSION = 1
# Semeadas pela migração: no banco vazio já existem e são substituídas pelo backup.
SEEDED = ("categories", "app_settings")


def _tables() -> list[Table]:
    return list(Base.metadata.sorted_tables)


def _revision(db: Session) -> str | None:
    return db.scalar(text("SELECT version_num FROM alembic_version"))


def _encode(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode()
    return value


def dump(db: Session) -> dict:
    tables: dict[str, list[dict]] = {}
    for t in _tables():
        rows = db.execute(select(t)).mappings().all()
        tables[t.name] = [{k: _encode(v) for k, v in r.items()} for r in rows]
    return {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "alembic_revision": _revision(db),
        "exported_at": datetime.now(UTC).isoformat(),
        "counts": {name: len(rows) for name, rows in tables.items()},
        "tables": tables,
    }


def _decode(table: Table, row: dict) -> dict:
    out = {}
    for col in table.columns:
        if col.name not in row:
            continue
        v = row[col.name]
        if v is None:
            out[col.name] = None
        elif isinstance(col.type, PG_UUID):
            out[col.name] = uuid.UUID(v)
        elif isinstance(col.type, DateTime):
            out[col.name] = datetime.fromisoformat(v)
        elif isinstance(col.type, Date):
            out[col.name] = date.fromisoformat(v)
        elif isinstance(col.type, LargeBinary):
            out[col.name] = base64.b64decode(v)
        else:
            out[col.name] = v
    return out


def _self_ref_order(table: Table, rows: list[dict]) -> list[dict]:
    """Linhas que apontam para a própria tabela (categoria → categoria pai) vêm depois das raízes."""
    self_fks = [fk.parent.name for fk in table.foreign_keys if fk.column.table is table]
    if not self_fks:
        return rows
    col = self_fks[0]
    done: set = set()
    ordered: list[dict] = []
    pending = list(rows)
    while pending:
        progressed = False
        for r in list(pending):
            if r.get(col) is None or r[col] in done:
                ordered.append(r)
                done.add(r.get("id"))
                pending.remove(r)
                progressed = True
        if not progressed:  # referência quebrada: deixa o banco recusar com erro claro
            ordered.extend(pending)
            break
    return ordered


def restore(db: Session, data: dict) -> dict[str, int]:
    """Restaura um backup num banco VAZIO (mesma revisão do Alembic). Não faz commit."""
    if data.get("format") != FORMAT or data.get("format_version") != FORMAT_VERSION:
        raise DomainError("backup_format", "Arquivo não é um backup do Finance Hub (ou versão incompatível).")
    revision = _revision(db)
    if data.get("alembic_revision") != revision:
        raise DomainError(
            "backup_revision",
            f"Backup da revisão {data.get('alembic_revision')}, banco na {revision}. "
            "Aplique as migrações até a mesma revisão antes de restaurar.",
        )

    tables = _tables()
    for t in tables:
        if t.name in SEEDED:
            continue
        if db.scalar(select(func.count()).select_from(t)):
            raise DomainError(
                "database_not_empty",
                f"O banco já tem dados ({t.name}). A restauração só é feita em banco vazio.",
                status_code=409,
            )

    # Remove as sementes (o backup traz as suas, possivelmente editadas).
    for name in SEEDED:
        table = Base.metadata.tables[name]
        if name == "categories":
            # Filhas antes das raízes (FK para a própria tabela).
            db.execute(delete(table).where(table.c.parent_id.is_not(None)))
        db.execute(delete(table))

    counts: dict[str, int] = {}
    payload = data.get("tables", {})
    for t in tables:
        rows = [_decode(t, r) for r in payload.get(t.name, [])]
        rows = _self_ref_order(t, rows)
        if rows:
            # executemany preserva a ordem (raízes antes das filhas).
            db.execute(insert(t), rows)
        counts[t.name] = len(rows)
    db.flush()
    return counts
