"""Apoio aos testes E2E (Playwright). Nunca toca no banco do usuário.

Usa um banco próprio (`finance_hub_e2e`) no mesmo Postgres, com segredo JWT e proprietário de teste.

    uv run python scripts/e2e.py serve [porta]   # recria o banco, aplica migrações e sobe a API
    uv run python scripts/e2e.py reset           # esvazia os dados (mantém categorias-semente)
"""

import os
import sys
from pathlib import Path

ADMIN_URL = os.environ.get("E2E_ADMIN_DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres")
E2E_DB = "finance_hub_e2e"
E2E_URL = ADMIN_URL.rsplit("/", 1)[0] + f"/{E2E_DB}"
# Mesmos valores de frontend/e2e/session.ts.
OWNER = "00000000-0000-4000-8000-0000000000e2"
SECRET = "e2e-secret-with-at-least-32-characters!!"

# Antes de importar o app: variáveis de ambiente têm prioridade sobre o .env.
os.environ.update(
    DATABASE_URL=E2E_URL,
    ALEMBIC_DATABASE_URL=E2E_URL,
    SUPABASE_JWT_SECRET=SECRET,
    OWNER_SUBJECT=OWNER,
    SUPABASE_URL="http://127.0.0.1:1",
)

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, text  # noqa: E402

KEEP = {"categories", "alembic_version"}


def prepare() -> None:
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {E2E_DB} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {E2E_DB}"))
    admin.dispose()

    from alembic.config import Config

    from alembic import command

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")


def reset() -> None:
    from app.models import Base

    names = ", ".join(t.name for t in Base.metadata.sorted_tables if t.name not in KEEP)
    engine = create_engine(E2E_URL)
    with engine.begin() as c:
        c.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
        # Categorias criadas por um teste não vazam para o próximo.
        c.execute(text("DELETE FROM categories WHERE created_at > (SELECT min(created_at) FROM categories) + interval '1 minute'"))
    engine.dispose()


def serve(port: int) -> None:
    import uvicorn

    prepare()
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "reset":
        reset()
    elif cmd == "serve":
        serve(int(sys.argv[2]) if len(sys.argv) > 2 else 8010)
    else:
        sys.exit(f"Comando desconhecido: {cmd}")
