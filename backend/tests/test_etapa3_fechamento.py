"""Etapa 3 (fechamento): estimado × real, rateio da casa (Fluxo D) e alertas in-app."""

import uuid
from datetime import timedelta

import pytest

from app.core.errors import DomainError
from app.domains.splits.rules import compute_shares
from app.domains.support import today_local

TODAY = today_local()
D = TODAY.isoformat()


def _account(client, opening=1_000_000):
    r = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "CHECKING", "opening_balance_cents": opening, "opening_date": "2026-01-01"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _bill(client, account_id, name="Luz", amount=24_000, variable=False):
    r = client.post(
        "/api/v1/bills",
        json={"name": name, "category": "ELECTRICITY", "account_id": account_id,
              "default_amount_cents": amount, "variable_amount": variable},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _installment(client, bill_id, due=None, amount=24_000, is_estimate=False):
    r = client.post(
        "/api/v1/bills/installments",
        json={"bill_id": bill_id, "due_date": (due or TODAY).isoformat(), "amount_cents": amount,
              "is_estimate": is_estimate},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _pay(client, inst_id, account_id, amount=None, key=None):
    params = {"account_id": account_id, "paid_on": D}
    if amount:
        params["amount_cents"] = amount
    if key:
        params["idempotency_key"] = key
    return client.post(f"/api/v1/bills/installments/{inst_id}/pay", params=params)


def _person(client, name):
    r = client.post("/api/v1/people", json={"display_name": name})
    assert r.status_code == 201, r.text
    return r.json()


def _balance_of(client, account_id):
    return next(a for a in client.get("/api/v1/accounts").json() if a["id"] == account_id)["balance_cents"]


# ---------- Regras puras do rateio ----------

def test_rateio_partes_iguais_fecha_centavos():
    owner, shares = compute_shares(10_000, "EQUAL", True, [None, None], [None, None])
    assert owner + sum(shares) == 10_000
    assert (owner, shares) == (3_334, [3_333, 3_333])


def test_rateio_percentual_sem_dono_maior_resto():
    owner, shares = compute_shares(10_001, "PERCENT", False, [None] * 3, [3_334, 3_333, 3_333])
    assert owner == 0
    assert sum(shares) == 10_001


def test_rateio_fixo_excede_total():
    with pytest.raises(DomainError):
        compute_shares(10_000, "FIXED", True, [6_000, 5_000], [None, None])


# ---------- Estimado × real ----------

def test_recorrencia_de_conta_variavel_gera_estimativa_e_confirma(client):
    acc = _account(client)
    bill = _bill(client, acc["id"], variable=True, amount=20_000)
    start = TODAY.replace(day=1)
    rec = client.post(
        "/api/v1/bills/recurrences",
        json={"bill_id": bill["id"], "frequency": "MONTHLY", "day_of_month": 1, "start_date": start.isoformat(),
              "auto_post": False},
    ).json()
    created = client.post(f"/api/v1/bills/recurrences/{rec['id']}/post-installments").json()
    inst = created[0]
    assert inst["is_estimate"] is True
    assert inst["estimated_amount_cents"] == 20_000

    r = client.post(f"/api/v1/bills/installments/{inst['id']}/confirm-amount", json={"amount_cents": 23_750})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["is_estimate"] is False
    assert d["amount_cents"] == 23_750
    assert d["estimated_amount_cents"] == 20_000

    again = client.post(f"/api/v1/bills/installments/{inst['id']}/confirm-amount", json={"amount_cents": 1})
    assert again.status_code == 409


def test_pagar_estimativa_com_outro_valor_confirma(client):
    acc = _account(client)
    bill = _bill(client, acc["id"], variable=True)
    inst = _installment(client, bill["id"], amount=20_000, is_estimate=True)
    r = _pay(client, inst["id"], acc["id"], amount=21_500)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "PAID" and d["amount_cents"] == 21_500 and d["is_estimate"] is False
    assert d["estimated_amount_cents"] == 20_000
    assert _balance_of(client, acc["id"]) == 1_000_000 - 21_500


def test_valor_fixo_continua_exigindo_valor_exato(client):
    acc = _account(client)
    bill = _bill(client, acc["id"])
    inst = _installment(client, bill["id"], amount=10_000)
    assert _pay(client, inst["id"], acc["id"], amount=9_000).status_code == 400


def test_pagamento_idempotente_sem_sobrescrever_observacoes(client):
    acc = _account(client)
    bill = _bill(client, acc["id"])
    r = client.post(
        "/api/v1/bills/installments",
        json={"bill_id": bill["id"], "due_date": D, "amount_cents": 5_000, "notes": "boleto no e-mail"},
    )
    inst = r.json()
    key = str(uuid.uuid4())
    first = _pay(client, inst["id"], acc["id"], key=key)
    second = _pay(client, inst["id"], acc["id"], key=key)
    assert first.status_code == second.status_code == 200
    assert first.json()["transaction_id"] == second.json()["transaction_id"]
    assert second.json()["notes"] == "boleto no e-mail"
    assert _balance_of(client, acc["id"]) == 1_000_000 - 5_000


def test_pagamento_recusa_conta_arquivada(client):
    acc = _account(client)
    bill = _bill(client, acc["id"])
    inst = _installment(client, bill["id"], amount=5_000)
    client.patch(f"/api/v1/accounts/{acc['id']}", json={"archived": True})
    r = _pay(client, inst["id"], acc["id"])
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "account_archived"


# ---------- Rateio (Fluxo D) ----------

def test_fluxo_d_rateio_repasse_parcial_e_quitacao(client):
    acc = _account(client)
    bill = _bill(client, acc["id"], amount=24_000)
    inst = _installment(client, bill["id"], amount=24_000)
    assert _pay(client, inst["id"], acc["id"]).status_code == 200
    ana, bia = _person(client, "Ana"), _person(client, "Bia")

    r = client.post(
        f"/api/v1/bills/installments/{inst['id']}/split",
        json={"method": "EQUAL", "include_owner": True,
              "participants": [{"person_id": ana["id"]}, {"person_id": bia["id"]}]},
    )
    assert r.status_code == 201, r.text
    split = r.json()
    assert split["owner_share_cents"] == 8_000
    assert [p["share_cents"] for p in split["parts"]] == [8_000, 8_000]
    assert split["net_cost_cents"] == 24_000

    # Uma única despesa: o rateio não cria despesas nem receitas.
    k = client.get("/api/v1/dashboard").json()["kpis"]
    assert k["expense"]["value_cents"] == 24_000
    assert k["income"]["value_cents"] == 0
    assert k["receivables"]["value_cents"] == 16_000

    ana_balance = split["parts"][0]["party_balance_id"]
    r = client.post(
        f"/api/v1/party-balances/{ana_balance}/settlements",
        json={"account_id": acc["id"], "amount_cents": 5_000, "settled_on": D},
    )
    assert r.status_code == 201, r.text
    client.post(
        f"/api/v1/party-balances/{ana_balance}/settlements",
        json={"account_id": acc["id"], "amount_cents": 3_000, "settled_on": D},
    )

    s = client.get(f"/api/v1/bills/installments/{inst['id']}/split").json()
    assert s["received_cents"] == 8_000
    assert s["net_cost_cents"] == 16_000
    assert s["parts"][0]["status"] == "SETTLED"
    assert s["parts"][1]["open_cents"] == 8_000
    assert _balance_of(client, acc["id"]) == 1_000_000 - 24_000 + 8_000
    # Repasse não é receita.
    assert client.get("/api/v1/dashboard").json()["kpis"]["income"]["value_cents"] == 0

    inst_out = client.get(f"/api/v1/bills/installments/{inst['id']}").json()
    assert inst_out["split_id"] == split["id"]


def test_rateio_exige_valor_confirmado_e_unico(client):
    acc = _account(client)
    bill = _bill(client, acc["id"], variable=True)
    ana = _person(client, "Ana")
    estimate = _installment(client, bill["id"], is_estimate=True)
    body = {"method": "EQUAL", "participants": [{"person_id": ana["id"]}]}
    r = client.post(f"/api/v1/bills/installments/{estimate['id']}/split", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "installment_estimate"

    inst = _installment(client, bill["id"], amount=10_000)
    assert client.post(f"/api/v1/bills/installments/{inst['id']}/split", json=body).status_code == 201
    dup = client.post(f"/api/v1/bills/installments/{inst['id']}/split", json=body)
    assert dup.status_code == 409


def test_desfazer_rateio_bloqueado_com_repasse_e_trava_cancelamento_direto(client):
    acc = _account(client)
    bill = _bill(client, acc["id"])
    inst = _installment(client, bill["id"], amount=10_000)
    ana = _person(client, "Ana")
    split = client.post(
        f"/api/v1/bills/installments/{inst['id']}/split",
        json={"method": "FIXED", "include_owner": True, "participants": [{"person_id": ana["id"], "amount_cents": 4_000}]},
    ).json()
    balance_id = split["parts"][0]["party_balance_id"]

    # O recebível do rateio não pode ser cancelado pela tela de terceiros.
    r = client.post(f"/api/v1/party-balances/{balance_id}/cancel", json={"reason": "teste"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "managed_by_split"
    assert client.get(f"/api/v1/party-balances/{balance_id}").json()["from_split"] is True

    # Parcela com rateio não pode ser cancelada.
    r = client.post(f"/api/v1/bills/installments/{inst['id']}/cancel")
    assert r.status_code == 409 and r.json()["error"]["code"] == "has_split"

    client.post(
        f"/api/v1/party-balances/{balance_id}/settlements",
        json={"account_id": acc["id"], "amount_cents": 1_000, "settled_on": D},
    )
    blocked = client.post(f"/api/v1/bills/splits/{split['id']}/cancel", json={"reason": "errei"})
    assert blocked.status_code == 409

    sid = client.get(f"/api/v1/party-balances/{balance_id}").json()["settlements"][0]["id"]
    client.post(f"/api/v1/party-balances/settlements/{sid}/reverse", json={"reason": "desfazer"})
    ok = client.post(f"/api/v1/bills/splits/{split['id']}/cancel", json={"reason": "errei"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["cancelled_at"] is not None
    assert client.get("/api/v1/dashboard").json()["kpis"]["receivables"]["value_cents"] == 0
    # Depois de desfeito, é possível ratear de novo.
    again = client.post(
        f"/api/v1/bills/installments/{inst['id']}/split",
        json={"method": "EQUAL", "participants": [{"person_id": ana["id"]}]},
    )
    assert again.status_code == 201


# ---------- Alertas ----------

def test_alertas_vencimentos_estagios_e_dispensa(client):
    acc = _account(client)
    bill = _bill(client, acc["id"], variable=True)
    _installment(client, bill["id"], due=TODAY - timedelta(days=2), amount=7_000)
    _installment(client, bill["id"], due=TODAY + timedelta(days=3), amount=9_000, is_estimate=True)
    _installment(client, bill["id"], due=TODAY + timedelta(days=20), amount=1_000)

    data = client.get("/api/v1/alerts").json()
    kinds = sorted(a["kind"] for a in data["items"])
    assert kinds == ["DUE_SOON", "ESTIMATE_PENDING", "OVERDUE"]
    overdue = next(a for a in data["items"] if a["kind"] == "OVERDUE")
    assert overdue["severity"] == "danger" and overdue["key"].endswith(":overdue")
    assert data["counts"]["danger"] == 1

    r = client.post("/api/v1/alerts/dismiss", json={"key": overdue["key"]})
    assert r.status_code == 200
    assert all(a["key"] != overdue["key"] for a in r.json()["items"])
    assert r.json()["counts"]["total"] == 2


def test_alerta_recebivel_vencido_e_cartao(client):
    acc = _account(client)
    p = _person(client, "Ana")
    client.post(
        "/api/v1/party-balances",
        json={"person_id": p["id"], "origin_type": "OWED_TO_ME", "description": "Ingresso", "principal_cents": 5_000,
              "operation_date": (TODAY - timedelta(days=10)).isoformat(),
              "due_date": (TODAY - timedelta(days=1)).isoformat()},
    )
    card = client.post(
        "/api/v1/cards",
        json={"name": "Nubank", "limit_cents": 100_000, "closing_day": 10, "due_day": 5, "due_month_offset": 1,
              "purchase_boundary_policy": "EXCLUSIVE", "default_payment_account_id": acc["id"]},
    ).json()
    client.post(
        "/api/v1/cards/purchases",
        json={"card_id": card["id"], "description": "TV", "purchased_on": D, "total_cents": 85_000,
              "installments_count": 1},
    )
    items = client.get("/api/v1/alerts").json()["items"]
    kinds = {a["kind"] for a in items}
    assert "RECEIVABLE_OVERDUE" in kinds
    card_alert = next(a for a in items if a["kind"] == "CARD_UTILIZATION")
    assert "85%" in card_alert["title"]

    # Limite configurável: acima de 90% o alerta some.
    assert client.patch("/api/v1/settings", json={"alert_card_utilization_pct": 90}).status_code == 200
    assert all(a["kind"] != "CARD_UTILIZATION" for a in client.get("/api/v1/alerts").json()["items"])


def test_alertas_exigem_proprietario(anon_client):
    assert anon_client.get("/api/v1/alerts").status_code == 401
