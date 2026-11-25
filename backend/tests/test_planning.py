"""Etapa 5 — Planejamento: orçamentos, metas e projeção."""

import uuid
from datetime import timedelta

from app.domains.planning import rules
from app.domains.support import today_local

TODAY = today_local()
D = TODAY.isoformat()
MONTH_START = TODAY.replace(day=1)


def _month_end(d):
    nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return nxt - timedelta(days=1)


MONTH_END = _month_end(TODAY)


def _account(client, name="Conta", opening=1_000_000, type_="CHECKING"):
    r = client.post(
        "/api/v1/accounts",
        json={"name": name, "type": type_, "opening_balance_cents": opening, "opening_date": "2026-01-01"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _cat(client, name):
    return next(c for c in client.get("/api/v1/categories").json() if c["name"] == name and c["kind"] == "EXPENSE")


def _expense(client, account_id, amount, category_id=None, status="POSTED", date=None):
    body = {"account_id": account_id, "kind": "EXPENSE", "amount_cents": amount, "status": status,
            "effective_date": date or D, "description": "Despesa"}
    if category_id:
        body["category_id"] = category_id
    r = client.post("/api/v1/transactions", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _budget(client, limit, category_id=None, basis="CASH", start=MONTH_START, end=MONTH_END):
    r = client.post(
        "/api/v1/budgets",
        json={"category_id": category_id, "period_start": start.isoformat(), "period_end": end.isoformat(),
              "limit_cents": limit, "basis": basis},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _balances(client):
    return {a["id"]: a["balance_cents"] for a in client.get("/api/v1/accounts").json()}


# ---------- Regras puras ----------

def test_status_do_orcamento_80_e_100():
    assert rules.budget_status(7_999, 10_000) == "OK"
    assert rules.budget_status(8_000, 10_000) == "WARNING"
    assert rules.budget_status(10_000, 10_000) == "OVER"


# ---------- Orçamentos ----------

def test_orcamento_por_categoria_inclui_subcategorias(client):
    acc = _account(client)
    alimentacao = _cat(client, "Alimentação")
    mercado = _cat(client, "Mercado")
    transporte = _cat(client, "Combustível")
    _expense(client, acc["id"], 30_000, mercado["id"])
    _expense(client, acc["id"], 9_000, transporte["id"])  # fora do escopo

    b = _budget(client, 50_000, alimentacao["id"])
    assert b["spent_cents"] == 30_000
    assert b["status"] == "OK"
    assert b["remaining_cents"] == 20_000


def test_transferencia_nao_conta_no_orcamento_geral(client):
    a1 = _account(client, "A")
    a2 = _account(client, "B")
    r = client.post(
        "/api/v1/transfers",
        json={"from_account_id": a1["id"], "to_account_id": a2["id"], "amount_cents": 40_000,
              "effective_date": D, "description": "Reserva"},
    )
    assert r.status_code == 201, r.text
    _expense(client, a1["id"], 5_000)
    b = _budget(client, 10_000)
    assert b["spent_cents"] == 5_000


def test_orcamento_comprometido_e_alerta_80(client):
    acc = _account(client)
    moradia = _cat(client, "Moradia")
    bill = client.post(
        "/api/v1/bills",
        json={"name": "Energia", "category": "ELECTRICITY", "account_id": acc["id"], "default_amount_cents": 9_000},
    ).json()
    due = min(TODAY + timedelta(days=1), MONTH_END)
    client.post("/api/v1/bills/installments", json={"bill_id": bill["id"], "due_date": due.isoformat(),
                                                    "amount_cents": 9_000})
    b = _budget(client, 10_000, moradia["id"])
    # A conta ainda não foi paga: entra como comprometido na base caixa.
    assert b["spent_cents"] == 0
    assert b["committed_cents"] == 9_000
    assert b["status"] == "WARNING"

    alerts = client.get("/api/v1/alerts").json()["items"]
    budget_alert = next(a for a in alerts if a["kind"] == "BUDGET")
    assert budget_alert["severity"] == "warning"
    assert "90%" in budget_alert["title"]


def test_orcamento_cartao_caixa_vs_competencia(client):
    acc = _account(client)
    lazer = _cat(client, "Lazer")
    card = client.post(
        "/api/v1/cards",
        json={"name": "Nubank", "limit_cents": 500_000, "closing_day": 10, "due_day": 5, "due_month_offset": 1,
              "purchase_boundary_policy": "EXCLUSIVE", "default_payment_account_id": acc["id"]},
    ).json()
    client.post(
        "/api/v1/cards/purchases",
        json={"card_id": card["id"], "description": "Cinema", "purchased_on": D, "total_cents": 6_000,
              "installments_count": 1, "category_id": lazer["id"]},
    )
    competencia = _budget(client, 10_000, lazer["id"], basis="COMPETENCE")
    assert competencia["spent_cents"] == 6_000

    # Caixa: a compra só vira consumo quando a fatura é paga.
    stmt = client.get(f"/api/v1/cards/{card['id']}/statements").json()[0]
    client.delete(f"/api/v1/budgets/{competencia['id']}")
    caixa = _budget(client, 10_000, lazer["id"], basis="CASH", start=MONTH_START, end=MONTH_END)
    assert caixa["spent_cents"] == 0
    r = client.post(
        f"/api/v1/cards/statements/{stmt['id']}/payments",
        json={"statement_id": stmt["id"], "account_id": acc["id"], "amount_cents": 3_000, "paid_on": D,
              "idempotency_key": str(uuid.uuid4())},
    )
    assert r.status_code == 201, r.text
    caixa = next(b for b in client.get("/api/v1/budgets").json() if b["id"] == caixa["id"])
    # Metade da fatura paga -> metade da compra atribuída (centavos inteiros).
    assert caixa["spent_cents"] == 3_000


def test_orcamento_duplicado_recusado(client):
    _budget(client, 10_000)
    r = client.post(
        "/api/v1/budgets",
        json={"category_id": None, "period_start": MONTH_START.isoformat(), "period_end": MONTH_END.isoformat(),
              "limit_cents": 5_000},
    )
    assert r.status_code == 409


def test_orcamento_categoria_de_receita_recusada(client):
    salario = next(c for c in client.get("/api/v1/categories").json() if c["kind"] == "INCOME")
    r = client.post(
        "/api/v1/budgets",
        json={"category_id": salario["id"], "period_start": MONTH_START.isoformat(),
              "period_end": MONTH_END.isoformat(), "limit_cents": 5_000},
    )
    assert r.status_code == 422


def test_copiar_orcamentos_para_o_proximo_mes(client):
    lazer = _cat(client, "Lazer")
    _budget(client, 10_000)
    _budget(client, 4_000, lazer["id"])
    src = MONTH_START.strftime("%Y-%m")
    nxt = (MONTH_END + timedelta(days=1)).strftime("%Y-%m")
    r = client.post("/api/v1/budgets/copy", json={"from_month": src, "to_month": nxt})
    assert r.status_code == 200, r.text
    assert r.json() == {"created": 2, "skipped": 0}
    again = client.post("/api/v1/budgets/copy", json={"from_month": src, "to_month": nxt}).json()
    assert again == {"created": 0, "skipped": 2}
    assert len(client.get("/api/v1/budgets").json()) == 4


# ---------- Metas ----------

def test_aporte_com_transferencia_nao_e_despesa_e_estorno(client):
    corrente = _account(client, "Corrente", 100_000)
    reserva = _account(client, "Reserva", 0, "SAVINGS")
    goal = client.post("/api/v1/goals", json={"title": "Viagem", "target_cents": 50_000}).json()

    r = client.post(
        f"/api/v1/goals/{goal['id']}/contributions",
        json={"from_account_id": corrente["id"], "to_account_id": reserva["id"], "amount_cents": 20_000,
              "effective_date": D},
    )
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["allocated_cents"] == 20_000 and g["progress_pct"] == 40.0
    bal = _balances(client)
    assert bal[corrente["id"]] == 80_000 and bal[reserva["id"]] == 20_000
    assert client.get("/api/v1/dashboard").json()["kpis"]["expense"]["value_cents"] == 0

    alloc_id = g["allocations"][0]["id"]
    r = client.post(f"/api/v1/goals/{goal['id']}/allocations/{alloc_id}/reverse", json={"reason": "errei a conta"})
    assert r.status_code == 200, r.text
    assert r.json()["allocated_cents"] == 0
    bal = _balances(client)
    assert bal[corrente["id"]] == 100_000 and bal[reserva["id"]] == 0
    again = client.post(f"/api/v1/goals/{goal['id']}/allocations/{alloc_id}/reverse", json={"reason": "de novo"})
    assert again.status_code == 409


def test_meta_atingida_e_volta_a_ativa_apos_estorno(client):
    goal = client.post("/api/v1/goals", json={"title": "Reserva", "target_cents": 10_000}).json()
    r = client.post(f"/api/v1/goals/{goal['id']}/allocations", json={"amount_cents": 10_000, "allocated_on": D})
    g = r.json()
    assert g["state"] == "ACHIEVED"
    g = client.post(
        f"/api/v1/goals/{goal['id']}/allocations/{g['allocations'][0]['id']}/reverse", json={"reason": "corrigir"}
    ).json()
    assert g["state"] == "ACTIVE"


def test_aporte_idempotente_e_meta_cancelada(client):
    goal = client.post("/api/v1/goals", json={"title": "Carro", "target_cents": 100_000}).json()
    key = str(uuid.uuid4())
    body = {"amount_cents": 5_000, "allocated_on": D, "idempotency_key": key}
    client.post(f"/api/v1/goals/{goal['id']}/allocations", json=body)
    g = client.post(f"/api/v1/goals/{goal['id']}/allocations", json=body).json()
    assert g["allocated_cents"] == 5_000

    client.post(f"/api/v1/goals/{goal['id']}/cancel", json={"reason": "desisti"})
    r = client.post(f"/api/v1/goals/{goal['id']}/allocations", json={"amount_cents": 1_000, "allocated_on": D})
    assert r.status_code == 409


# ---------- Projeção ----------

def test_projecao_cenarios_e_sem_dupla_contagem_do_cartao(client):
    acc = _account(client, opening=100_000)
    _expense(client, acc["id"], 10_000, status="PLANNED", date=(TODAY + timedelta(days=5)).isoformat())
    card = client.post(
        "/api/v1/cards",
        json={"name": "Nubank", "limit_cents": 500_000, "closing_day": 10, "due_day": 5, "due_month_offset": 1,
              "purchase_boundary_policy": "EXCLUSIVE", "default_payment_account_id": acc["id"]},
    ).json()
    client.post(
        "/api/v1/cards/purchases",
        json={"card_id": card["id"], "description": "Notebook", "purchased_on": D, "total_cents": 60_000,
              "installments_count": 2},
    )
    p = client.post(
        "/api/v1/people", json={"display_name": "Ana"}
    ).json()
    client.post(
        "/api/v1/party-balances",
        json={"person_id": p["id"], "origin_type": "OWED_TO_ME", "description": "Ingresso",
              "principal_cents": 7_000, "operation_date": D, "due_date": (TODAY + timedelta(days=3)).isoformat()},
    )

    r = client.get("/api/v1/projection", params={"days": 90})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["start_balance_cents"] == 100_000
    assert len(data["points"]) == 91
    # Duas parcelas de R$ 300 em duas faturas: cada uma entra uma única vez.
    assert data["conservative"]["outflow_cents"] == 10_000 + 60_000
    assert data["conservative"]["inflow_cents"] == 0
    assert data["base"]["inflow_cents"] == 7_000
    assert data["conservative"]["end_cents"] == 30_000
    assert data["base"]["end_cents"] == 37_000
    assert data["conservative"]["lowest_cents"] == 30_000


def test_projecao_rejeita_horizonte_invalido(client):
    assert client.get("/api/v1/projection", params={"days": 45}).status_code == 422


def test_planejamento_exige_proprietario(anon_client):
    for path in ("/api/v1/budgets", "/api/v1/goals", "/api/v1/projection"):
        assert anon_client.get(path).status_code == 401
