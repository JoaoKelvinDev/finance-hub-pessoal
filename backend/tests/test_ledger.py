import threading
import uuid
from datetime import date, timedelta

from app.domains.support import today_local

TODAY = today_local()
D = TODAY.isoformat()


def _account(client, name="Corrente", opening=450000, opening_date="2026-01-01"):
    r = client.post(
        "/api/v1/accounts",
        json={"name": name, "type": "CHECKING", "opening_balance_cents": opening, "opening_date": opening_date},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _tx(client, account_id, kind, amount, **extra):
    body = {"account_id": account_id, "kind": kind, "amount_cents": amount, "effective_date": D,
            "description": f"{kind} teste", **extra}
    return client.post("/api/v1/transactions", json=body)


def _balance(client, account_id):
    return next(a for a in client.get("/api/v1/accounts").json() if a["id"] == account_id)["balance_cents"]


def test_receita_e_despesa_atualizam_saldo(client):
    acc = _account(client)
    assert _tx(client, acc["id"], "INCOME", 100000).status_code == 201
    assert _tx(client, acc["id"], "EXPENSE", 25050).status_code == 201
    assert _balance(client, acc["id"]) == 450000 + 100000 - 25050


def test_previsto_nao_altera_saldo_atual(client):
    acc = _account(client)
    future = (TODAY + timedelta(days=10)).isoformat()
    r = _tx(client, acc["id"], "EXPENSE", 12000, status="PLANNED", effective_date=future)
    assert r.status_code == 201
    acc_now = next(a for a in client.get("/api/v1/accounts").json() if a["id"] == acc["id"])
    assert acc_now["balance_cents"] == 450000
    assert acc_now["planned_balance_cents"] == 450000 - 12000


def test_efetivado_futuro_e_recusado(client):
    acc = _account(client)
    r = _tx(client, acc["id"], "EXPENSE", 100, effective_date=(TODAY + timedelta(days=1)).isoformat())
    assert r.status_code == 422 and r.json()["error"]["code"] == "future_posted"


def test_transferencia_preserva_soma_e_nao_e_receita_nem_despesa(client):
    a, b = _account(client, "A"), _account(client, "B", opening=15000)
    total_before = _balance(client, a["id"]) + _balance(client, b["id"])
    r = client.post(
        "/api/v1/transfers",
        json={"from_account_id": a["id"], "to_account_id": b["id"], "amount_cents": 50000, "effective_date": D},
    )
    assert r.status_code == 201, r.text
    assert _balance(client, a["id"]) == 400000
    assert _balance(client, b["id"]) == 65000
    assert _balance(client, a["id"]) + _balance(client, b["id"]) == total_before

    k = client.get("/api/v1/dashboard").json()["kpis"]
    assert k["income"]["value_cents"] == 0 and k["expense"]["value_cents"] == 0
    totals = client.get("/api/v1/transactions").json()["totals"]
    assert totals["income_cents"] == 0 and totals["expense_cents"] == 0


def test_transferencia_para_mesma_conta_e_invalida(client):
    a = _account(client)
    r = client.post(
        "/api/v1/transfers",
        json={"from_account_id": a["id"], "to_account_id": a["id"], "amount_cents": 1, "effective_date": D},
    )
    assert r.status_code == 422


def test_cancelar_transferencia_cancela_as_duas_pernas(client):
    a, b = _account(client, "A"), _account(client, "B", opening=0)
    t = client.post(
        "/api/v1/transfers",
        json={"from_account_id": a["id"], "to_account_id": b["id"], "amount_cents": 1000, "effective_date": D},
    ).json()
    r = client.post(f"/api/v1/transactions/{t['in_leg']['id']}/cancel", json={"reason": "lançado errado"})
    assert r.status_code == 200
    assert _balance(client, a["id"]) == 450000 and _balance(client, b["id"]) == 0


def test_idempotencia_mesmo_payload_um_unico_evento(client):
    acc = _account(client)
    key = str(uuid.uuid4())
    r1 = _tx(client, acc["id"], "EXPENSE", 5000, idempotency_key=key)
    r2 = _tx(client, acc["id"], "EXPENSE", 5000, idempotency_key=key)
    assert r1.status_code == 201 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    assert _balance(client, acc["id"]) == 445000


def test_idempotencia_payload_diferente_retorna_409(client):
    acc = _account(client)
    key = str(uuid.uuid4())
    _tx(client, acc["id"], "EXPENSE", 5000, idempotency_key=key)
    r = _tx(client, acc["id"], "EXPENSE", 9999, idempotency_key=key)
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_conflict"


def test_idempotencia_concorrente_na_transferencia(client):
    a, b = _account(client, "A"), _account(client, "B", opening=0)
    key = str(uuid.uuid4())
    body = {"from_account_id": a["id"], "to_account_id": b["id"], "amount_cents": 700, "effective_date": D,
            "idempotency_key": key}
    results = []

    def go():
        results.append(client.post("/api/v1/transfers", json=body).json()["transfer_group_id"])

    threads = [threading.Thread(target=go) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(set(results)) == 1
    assert _balance(client, b["id"]) == 700


def test_conta_arquivada_nao_recebe_lancamento(client):
    acc = _account(client)
    client.patch(f"/api/v1/accounts/{acc['id']}", json={"archived": True})
    r = _tx(client, acc["id"], "INCOME", 100)
    assert r.status_code == 422 and r.json()["error"]["code"] == "account_archived"


def test_lancamento_antes_do_saldo_inicial_e_recusado(client):
    acc = _account(client, opening_date=D)
    r = _tx(client, acc["id"], "INCOME", 100, effective_date=(TODAY - timedelta(days=1)).isoformat())
    assert r.status_code == 422 and r.json()["error"]["code"] == "before_opening"


def test_categoria_de_tipo_errado_e_recusada(client):
    acc = _account(client)
    salario = next(c for c in client.get("/api/v1/categories").json() if c["kind"] == "INCOME")
    r = _tx(client, acc["id"], "EXPENSE", 100, category_id=salario["id"])
    assert r.status_code == 422 and r.json()["error"]["code"] == "category_kind_mismatch"


def test_efetivar_previsto(client):
    acc = _account(client)
    tx = _tx(client, acc["id"], "EXPENSE", 3000, status="PLANNED").json()
    r = client.post(f"/api/v1/transactions/{tx['id']}/post", json={})
    assert r.status_code == 200 and r.json()["status"] == "POSTED"
    assert _balance(client, acc["id"]) == 447000


def test_dashboard_kpis_e_auditoria(client):
    acc = _account(client)
    _tx(client, acc["id"], "INCOME", 500000)
    _tx(client, acc["id"], "EXPENSE", 120000)
    overdue_date = max(date.fromisoformat("2026-01-01"), TODAY - timedelta(days=3)).isoformat()
    _tx(client, acc["id"], "EXPENSE", 8000, status="PLANNED", effective_date=overdue_date)
    dash = client.get("/api/v1/dashboard").json()
    k = dash["kpis"]
    assert k["available_balance"]["value_cents"] == 450000 + 500000 - 120000
    assert k["income"]["value_cents"] == 500000
    assert k["expense"]["value_cents"] == 120000
    assert k["net"]["value_cents"] == 380000
    assert dash["health"]["savings_rate_pct"] == 76.0
    if overdue_date < D:
        assert k["overdue"]["value_cents"] == 8000
    assert sum(s["amount_cents"] for s in dash["expenses_by_category"]) == 120000

    from sqlalchemy import func, select

    from app.core.database import SessionLocal
    from app.models import AuditEvent

    with SessionLocal() as s:
        assert s.scalar(select(func.count()).select_from(AuditEvent)) >= 4
