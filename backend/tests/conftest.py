import os
import time
import uuid

# Ambiente de teste isolado: banco próprio e segredo de teste. Definido antes de importar o app.
ADMIN_URL = os.environ.get("TEST_ADMIN_DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres")
TEST_DB = "finance_hub_test"
TEST_URL = ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB}"
OWNER = str(uuid.UUID("00000000-0000-4000-8000-000000000001"))
SECRET = "test-secret-with-at-least-32-characters!!"

os.environ.update(
    DATABASE_URL=TEST_URL,
    SUPABASE_JWT_SECRET=SECRET,
    OWNER_SUBJECT=OWNER,
    SUPABASE_URL="http://127.0.0.1:1",
)

import jwt
import pytest
from sqlalchemy import create_engine, text


def make_token(sub: str = OWNER, exp_delta: int = 600, aud: str = "authenticated", secret: str = SECRET) -> str:
    now = int(time.time())
    return jwt.encode({"sub": sub, "aud": aud, "exp": now + exp_delta, "iat": now}, secret, algorithm="HS256")


def _db_available() -> bool:
    try:
        with create_engine(ADMIN_URL).connect():
            return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def database():
    if not _db_available():
        pytest.skip("Postgres do Supabase local indisponível (rode `supabase start`).")
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {TEST_DB}"))
        # Roles do Supabase existem no cluster; o REVOKE da migration precisa delas.
    from alembic.config import Config

    from alembic import command

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    os.environ["ALEMBIC_DATABASE_URL"] = TEST_URL
    command.upgrade(cfg, "head")
    yield
    admin.dispose()


@pytest.fixture
def client(database):
    from fastapi.testclient import TestClient

    from app.core.database import engine
    from app.main import app

    with engine.begin() as c:
        c.execute(
            text(
                "TRUNCATE transactions, idempotency_records, audit_events, financial_accounts, persons, app_settings,"
                " budgets, goals, alert_dismissals"
                " RESTART IDENTITY CASCADE"
            )
        )
    with TestClient(app) as tc:
        tc.headers["Authorization"] = f"Bearer {make_token()}"
        yield tc


@pytest.fixture
def anon_client(database):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as tc:
        yield tc
