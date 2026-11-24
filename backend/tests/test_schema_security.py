from sqlalchemy import text


def test_rls_habilitado_e_sem_acesso_para_roles_publicas(client):
    from app.core.database import engine

    with engine.connect() as c:
        rows = c.execute(
            text(
                "SELECT relname, relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'r' AND relname <> 'alembic_version'"
            )
        ).all()
        assert rows and all(rls for _, rls in rows), rows

        grants = c.execute(
            text(
                "SELECT table_name, grantee FROM information_schema.role_table_grants "
                "WHERE table_schema='public' AND grantee IN ('anon','authenticated')"
            )
        ).all()
        assert grants == []


def test_constraint_de_sinal_no_banco(client):
    from app.core.database import engine

    with engine.connect() as c:
        acc = c.execute(
            text("INSERT INTO financial_accounts (id,name,type,color,currency,opening_balance_cents,opening_date,version)"
                 " VALUES (gen_random_uuid(),'X','CASH','#000000','BRL',0,'2026-01-01',1) RETURNING id")
        ).scalar()
        try:
            c.execute(
                text("INSERT INTO transactions (id,account_id,amount_cents,kind,status,effective_date,description)"
                     " VALUES (gen_random_uuid(), :a, 100, 'EXPENSE', 'POSTED', '2026-01-02', 'x')"),
                {"a": acc},
            )
            raise AssertionError("despesa positiva deveria violar a constraint")
        except Exception as exc:
            assert "sign_matches_kind" in str(exc)
        finally:
            c.rollback()
