import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

# Na Vercel cada instância da função é efêmera e a conexão passa pelo pooler do Supabase
# (modo transação, porta 6543): sem pool próprio e sem prepared statements, que o pooler
# em modo transação não suporta. Localmente/testes, pool normal.
_SERVERLESS = bool(os.environ.get("VERCEL"))

engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=not _SERVERLESS,
    **({"poolclass": NullPool, "connect_args": {"prepare_threshold": None}} if _SERVERLESS else {}),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
