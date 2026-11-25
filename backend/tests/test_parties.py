"""Testes de Valores com terceiros (Etapa 4)."""

import uuid
from datetime import timedelta

from app.domains.support import today_local

TODAY = today_local()
D = TODAY.isoformat()
BASE = "/api/v1/party-balances"


def _account(client, opening=100_000):
    r = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "CHECKING", "opening_balance_cents": opening, "opening_date": "2026-01-01"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _person(client, name="Ana"):
    r = client.post("/api/v1/people", json={"display_name": name})
    assert r.status_code == 201, r.text
    return r.json()


def _balance(client, person_id, origin="LOAN_GIVEN", amount=30_000, account_id=None, **extra):
    body = {
        "person_id": person_id,
        "origin_type": origin,
        "description": "Empréstimo teste",
        "principal_cents": amount,
        "operation_date": D,
        **extra,
    }
    if account_id:
        body["account_id"] = account_id
    return client.post(BASE, json=body)


def _settle(client, balance_id, account_id, amount, key=None):
    body = {"account_id": account_id, "amount_cents": amount, "settled_on": D}
    if key:
        body["idempotency_key"] = key
    return client.post(f"{BASE}/{balance_id}/settlements", json=body)


def _account_balance(client, account_id):
    return next(a for a in client.get("/api/v1/accounts").json() if a["id"] == account_id)["balance_cents"]


def _kpis(client):
    return client.get("/api/v1/dashboard").json()["kpis"]


# ---------- Aceite: sem distorcer receita/despesa ----------

def test_emprestimo_concedido_reduz_caixa_sem_virar_despesa(client):
    acc = _account(client)
    p = _person(client)
    r = _balance(client, p["id"], "LOAN_GIVEN", 30_000, acc["id"])
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["direction"] == "RECEIVABLE"
    assert b["open_cents"] == 30_000
    assert b["status"] == "OPEN"
    assert _account_balance(client, acc["id"]) == 70_000

    k = _kpis(client)
    assert k["expense"]["value_cents"] == 0
    assert k["income"]["value_cents"] == 0
    assert k["receivables"]["value_cents"] == 30_000

    tx = client.get(f"/api/v1/transactions/{b['origin_transaction_id']}").json()
    assert tx["kind"] == "LOAN_OUT" and tx["amount_cents"] == -30_000
    assert tx["counterparty_id"] == p["id"]


def test_emprestimo_tomado_aumenta_caixa_sem_virar_receita(client):
    acc = _account(client)
    p = _person(client)
    b = _balance(client, p["id"], "LOAN_TAKEN", 50_000, acc["id"]).json()
    assert b["direction"] == "PAYABLE"
    assert _account_balance(client, acc["id"]) == 150_000
    k = _kpis(client)
    assert k["income"]["value_cents"] == 0
    assert k["payables"]["value_cents"] == 50_000


def test_divida_sem_caixa_nao_movimenta_conta(client):
    acc = _account(client)
    p = _person(client)
    r = _balance(client, p["id"], "I_OWE", 12_000)
    assert r.status_code == 201, r.text
    assert r.json()["origin_transaction_id"] is None
    assert _account_balance(client, acc["id"]) == 100_000


def test_tipo_com_caixa_exige_conta_e_sem_caixa_recusa_conta(client):
    acc = _account(client)
    p = _person(client)
    assert _balance(client, p["id"], "LOAN_GIVEN", 1000).status_code == 422
    assert _balance(client, p["id"], "OWED_TO_ME", 1000, acc["id"]).status_code == 422


# ---------- Acertos ----------

def test_acerto_parcial_e_quitacao(client):
    acc = _account(client)
    p = _person(client)
    b = _balance(client, p["id"], "LOAN_GIVEN", 30_000, acc["id"]).json()

    r = _settle(client, b["id"], acc["id"], 10_000)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["open_cents"] == 20_000
    assert d["settled_cents"] == 10_000
    assert d["status"] == "PARTIALLY_SETTLED"
    assert _account_balance(client, acc["id"]) == 80_000
    # Recebimento do principal não vira receita.
    assert _kpis(client)["income"]["value_cents"] == 0

    d = _settle(client, b["id"], acc["id"], 20_000).json()
    assert d["status"] == "SETTLED" and d["open_cents"] == 0
    assert _account_balance(client, acc["id"]) == 100_000


def test_acerto_acima_do_saldo_recusado(client):
    acc = _account(client)
    p = _person(client)
    b = _balance(client, p["id"], "LOAN_GIVEN", 30_000, acc["id"]).json()
    r = _settle(client, b["id"], acc["id"], 30_001)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "amount_exceeds_open"


def test_acerto_idempotente(client):
    acc = _account(client)
    p = _person(client)
    b = _balance(client, p["id"], "LOAN_GIVEN", 30_000, acc["id"]).json()
    key = str(uuid.uuid4())
    assert _settle(client, b["id"], acc["id"], 5_000, key).status_code == 201
    again = _settle(client, b["id"], acc["id"], 5_000, key)
    assert again.status_code == 200
    assert again.json()["settled_cents"] == 5_000
    assert len(again.json()["settlements"]) == 1
    assert _settle(client, b["id"], acc["id"], 6_000, key).status_code == 409


def test_pagar_divida_gera_saida(client):
    acc = _account(client)
    p = _person(client)
    b = _balance(client, p["id"], "LOAN_TAKEN", 40_000, acc["id"]).json()
    d = _settle(client, b["id"], acc["id"], 15_000).json()
    assert d["open_cents"] == 25_000
    assert _account_balance(client, acc["id"]) == 140_000 - 15_000
    tx_id = d["settlements"][0]["transaction_id"]
    assert client.get(f"/api/v1/transactions/{tx_id}").json()["kind"] == "SETTLEMENT_OUT"


def test_estorno_de_acerto(client):
    acc = _account(client)
    p = _person(client)
    b = _balance(client, p["id"], "LOAN_GIVEN", 30_000, acc["id"]).json()
    d = _settle(client, b["id"], acc["id"], 10_000).json()
    sid = d["settlements"][0]["id"]

    r = client.post(f"{BASE}/settlements/{sid}/reverse", json={"reason": "lançado errado"})
    assert r.status_code == 200, r.text
    assert r.json()["open_cents"] == 30_000
    assert r.json()["status"] == "OPEN"
    assert _account_balance(client, acc["id"]) == 70_000
    assert client.post(f"{BASE}/settlements/{sid}/reverse", json={"reason": "de novo"}).status_code == 409


def test_lancamento_de_terceiro_nao_cancela_pela_tela_de_lancamentos(client):
    acc = _account(client)
    p = _person(client)
    b = _balance(client, p["id"], "LOAN_GIVEN", 30_000, acc["id"]).json()
    r = client.post(f"/api/v1/transactions/{b['origin_transaction_id']}/cancel", json={"reason": "teste"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "managed_by_parties"


# ---------- Ajustes e cancelamento ----------

def test_juros_e_perdao(client):
    acc = _account(client)
    p = _person(client)
    b = _balance(client, p["id"], "LOAN_GIVEN", 30_000, acc["id"]).json()

    r = client.post(
        f"{BASE}/{b['id']}/adjustments",
        json={"kind": "CHARGE", "amount_cents": 3_000, "applied_on": D, "reason": "juros combinados"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["open_cents"] == 33_000

    too_much = client.post(
        f"{BASE}/{b['id']}/adjustments",
        json={"kind": "DISCOUNT", "amount_cents": 33_001, "applied_on": D, "reason": "perdão"},
    )
    assert too_much.status_code == 422

    d = client.post(
        f"{BASE}/{b['id']}/adjustments",
        json={"kind": "DISCOUNT", "amount_cents": 33_000, "applied_on": D, "reason": "perdão da dívida"},
    ).json()
    assert d["open_cents"] == 0 and d["status"] == "SETTLED"
    # Ajustes não movimentam caixa.
    assert _account_balance(client, acc["id"]) == 70_000


def test_cancelar_registro(client):
    acc = _account(client)
    p = _person(client)
    b = _balance(client, p["id"], "LOAN_GIVEN", 30_000, acc["id"]).json()
    _settle(client, b["id"], acc["id"], 1_000)

    blocked = client.post(f"{BASE}/{b['id']}/cancel", json={"reason": "duplicado"})
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "has_settlements"

    sid = client.get(f"{BASE}/{b['id']}").json()["settlements"][0]["id"]
    client.post(f"{BASE}/settlements/{sid}/reverse", json={"reason": "desfazer"})
    r = client.post(f"{BASE}/{b['id']}/cancel", json={"reason": "duplicado"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CANCELLED"
    assert _account_balance(client, acc["id"]) == 100_000
    assert _kpis(client)["receivables"]["value_cents"] == 0
    assert client.get(BASE).json()["items"] == []


# ---------- Situação, calendário e posição por pessoa ----------

def test_vencido_aparece_no_resumo_e_no_calendario(client):
    p = _person(client)
    due = TODAY - timedelta(days=2)
    r = _balance(
        client, p["id"], "OWED_TO_ME", 8_000,
        operation_date=(TODAY - timedelta(days=10)).isoformat(), due_date=due.isoformat(),
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "OVERDUE"

    page = client.get(BASE).json()
    assert page["summary"]["receivable_overdue_cents"] == 8_000

    cal = client.get("/api/v1/calendar", params={"from": (due - timedelta(days=1)).isoformat(), "to": D}).json()
    ev = next(e for e in cal["events"] if e["source"] == "PARTY_BALANCE")
    assert ev["direction"] == "IN" and ev["status"] == "OVERDUE" and ev["open_cents"] == 8_000
    assert ev["ref_id"] == p["id"]


def test_posicao_por_pessoa_nao_compensa_dividas(client):
    acc = _account(client)
    p = _person(client, "Bruno")
    _balance(client, p["id"], "LOAN_GIVEN", 30_000, acc["id"])
    _balance(client, p["id"], "I_OWE", 10_000)
    other = _person(client, "Carla")
    _balance(client, other["id"], "OWED_TO_ME", 99_000)

    pos = client.get(f"/api/v1/people/{p['id']}/position").json()
    assert pos["summary"]["receivable_open_cents"] == 30_000
    assert pos["summary"]["payable_open_cents"] == 10_000
    assert pos["net_cents"] == 20_000
    assert len(pos["balances"]) == 2
    # Nada foi compensado: os dois registros continuam em aberto.
    assert all(b["status"] == "OPEN" for b in pos["balances"])


def test_pessoa_arquivada_nao_recebe_registro(client):
    p = _person(client)
    client.patch(f"/api/v1/people/{p['id']}", json={"archived": True})
    r = _balance(client, p["id"], "OWED_TO_ME", 1_000)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "person_archived"


def test_terceiros_exige_proprietario(anon_client):
    assert anon_client.get(BASE).status_code == 401
    assert anon_client.post(BASE, json={}).status_code == 401
