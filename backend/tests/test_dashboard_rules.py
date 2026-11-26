"""Dashboard alinhado às fontes únicas: calendário (compromissos), projeção e relatórios."""

from datetime import timedelta

from app.domains.support import today_local

TODAY = today_local()
D = TODAY.isoformat()


def _account(client, opening=100_000):
    r = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "CHECKING", "opening_balance_cents": opening, "opening_date": "2026-01-01"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_compromissos_incluem_contas_da_casa_e_terceiros(client):
    acc = _account(client)
    bill = client.post(
        "/api/v1/bills",
        json={"name": "Aluguel", "category": "RENT", "account_id": acc["id"], "default_amount_cents": 40_000},
    ).json()
    client.post("/api/v1/bills/installments", json={"bill_id": bill["id"], "amount_cents": 40_000,
                                                    "due_date": (TODAY + timedelta(days=3)).isoformat()})
    client.post("/api/v1/bills/installments", json={"bill_id": bill["id"], "amount_cents": 5_000,
                                                    "due_date": (TODAY - timedelta(days=2)).isoformat()})
    p = client.post("/api/v1/people", json={"display_name": "Ana"}).json()
    client.post("/api/v1/party-balances", json={
        "person_id": p["id"], "origin_type": "I_OWE", "description": "Show", "principal_cents": 7_000,
        "operation_date": D, "due_date": (TODAY + timedelta(days=5)).isoformat()})
    # Recebível não reduz o que posso gastar (e não é contado como certo).
    client.post("/api/v1/party-balances", json={
        "person_id": p["id"], "origin_type": "OWED_TO_ME", "description": "Ingresso", "principal_cents": 9_000,
        "operation_date": D, "due_date": (TODAY + timedelta(days=4)).isoformat()})

    dash = client.get("/api/v1/dashboard").json()
    k = dash["kpis"]
    assert k["due_soon"]["value_cents"] == 40_000 + 7_000
    assert k["overdue"]["value_cents"] == 5_000
    assert dash["health"]["overdue_count"] == 1
    # Sem receita prevista: o horizonte é de 30 dias e todos os compromissos saem do saldo livre.
    assert dash["free_after_commitments_cents"] == 100_000 - 40_000 - 5_000 - 7_000

    # "Disponível projetado" é o mesmo número do cenário base da Projeção.
    proj = client.get("/api/v1/projection", params={"days": 30}).json()
    assert k["projected"]["value_cents"] == proj["base"]["end_cents"]


def test_saldo_livre_vai_ate_o_proximo_recebimento(client):
    acc = _account(client)
    client.post("/api/v1/transactions", json={
        "account_id": acc["id"], "kind": "INCOME", "amount_cents": 300_000, "status": "PLANNED",
        "effective_date": (TODAY + timedelta(days=6)).isoformat(), "description": "Salário"})
    for days, amount in ((2, 10_000), (10, 20_000)):
        client.post("/api/v1/transactions", json={
            "account_id": acc["id"], "kind": "EXPENSE", "amount_cents": amount, "status": "PLANNED",
            "effective_date": (TODAY + timedelta(days=days)).isoformat(), "description": "Conta"})
    dash = client.get("/api/v1/dashboard").json()
    assert dash["free_until"] == (TODAY + timedelta(days=6)).isoformat()
    # Só a despesa antes do salário reduz o saldo livre até lá.
    assert dash["free_after_commitments_cents"] == 100_000 - 10_000
