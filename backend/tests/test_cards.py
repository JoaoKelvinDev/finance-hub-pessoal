"""Testes para o módulo de cartões."""

import itertools
import uuid
from datetime import date, timedelta

from app.domains.cards import rules
from app.domains.support import today_local

TODAY = today_local()
D = TODAY.isoformat()


def _card(client, name="Nubank", limit=500000, closing=10, due=5, default_payment_account_id=None):
    body = {
        "name": name,
        "limit_cents": limit,
        "closing_day": closing,
        "due_day": due,
        "due_month_offset": 1,
        "purchase_boundary_policy": "EXCLUSIVE",
    }
    if default_payment_account_id:
        body["default_payment_account_id"] = default_payment_account_id
    r = client.post("/api/v1/cards", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _purchase(client, card_id, total=120000, installments=1, purchased_on=None, **extra):
    body = {
        "card_id": card_id,
        "description": "Compra teste",
        "purchased_on": purchased_on or D,
        "total_cents": total,
        "installments_count": installments,
        **extra,
    }
    return client.post("/api/v1/cards/purchases", json=body)


def _pay_statement(client, statement_id, account_id, amount, paid_on=None):
    return client.post(
        f"/api/v1/cards/statements/{statement_id}/payments",
        json={
            "statement_id": statement_id,
            "account_id": account_id,
            "amount_cents": amount,
            "paid_on": paid_on or D,
            "idempotency_key": str(uuid.uuid4()),
        },
    )


def _account(client, name="Conta", opening=450000, opening_date="2026-01-01"):
    r = client.post(
        "/api/v1/accounts",
        json={"name": name, "type": "CHECKING", "opening_balance_cents": opening, "opening_date": opening_date},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------- Regras de ciclos ----------
def test_resolve_cycle_start_exclusive_before_closing():
    """Compra antes do fechamento entra no ciclo que começou no mês anterior."""
    start = rules.resolve_cycle_start(10, date(2026, 11, 5), "EXCLUSIVE")
    assert start == date(2026, 10, 10)


def test_resolve_cycle_start_exclusive_after_closing():
    """Compra após o fechamento entra no ciclo do mês atual."""
    start = rules.resolve_cycle_start(10, date(2026, 11, 15), "EXCLUSIVE")
    assert start == date(2026, 11, 10)


def test_resolve_cycle_start_exclusive_on_closing():
    """Compra no dia do fechamento (EXCLUSIVE) entra no PRÓXIMO ciclo."""
    start = rules.resolve_cycle_start(10, date(2026, 11, 10), "EXCLUSIVE")
    assert start == date(2026, 11, 10)


def test_resolve_cycle_start_inclusive_on_closing():
    """Compra no dia do fechamento (INCLUSIVE) entra no ciclo ATUAL."""
    start = rules.resolve_cycle_start(10, date(2026, 11, 10), "INCLUSIVE")
    assert start == date(2026, 10, 10)


def test_resolve_due_date_offset_1():
    """Vencimento no mês seguinte ao FECHAMENTO: fecha 10/12 → vence 05/01."""
    due = rules.resolve_due_date(date(2026, 12, 10), 5, 1)
    assert due == date(2027, 1, 5)


def test_resolve_due_date_offset_0():
    """Mesmo mês do fechamento: fecha 25/11 → vence 30/11 (exemplo da especificação invertido)."""
    assert rules.resolve_due_date(date(2026, 11, 25), 30, 0) == date(2026, 11, 30)


def test_resolve_due_date_last_day_adjustment():
    """Se dia de vencimento não existe no mês, usa último dia."""
    due = rules.resolve_due_date(date(2026, 1, 10), 31, 1)  # Fevereiro não tem 31
    assert due == date(2026, 2, 28)


def test_fatura_nunca_vence_antes_de_fechar(client):
    """Regressão: o vencimento era calculado a partir do início do ciclo e caía antes do fechamento."""
    card = _card(client, closing=10, due=5)
    _purchase(client, card["id"], total=10000)
    for s in client.get(f"/api/v1/cards/{card['id']}/statements").json():
        assert s["due_date"] > s["cycle_end_exclusive"], s


def test_vencimento_no_mesmo_mes_antes_do_fechamento_recusado(client):
    body = {"name": "X", "limit_cents": 1000, "closing_day": 20, "due_day": 5, "due_month_offset": 0,
            "purchase_boundary_policy": "EXCLUSIVE"}
    r = client.post("/api/v1/cards", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "due_before_closing"
    assert client.post("/api/v1/cards", json={**body, "due_day": 27}).status_code == 201
    card = _card(client)
    r = client.patch(f"/api/v1/cards/{card['id']}", json={"due_month_offset": 0})
    assert r.status_code == 422 and r.json()["error"]["code"] == "due_before_closing"


def test_split_installments_exact():
    """Divisão exata de centavos sem perda."""
    assert rules.split_installments(10000, 3) == [3334, 3333, 3333]
    assert rules.split_installments(10000, 2) == [5000, 5000]
    assert rules.split_installments(10000, 1) == [10000]
    assert sum(rules.split_installments(12345, 7)) == 12345


# ---------- API: Cartões ----------
def test_create_card(client):
    acc = _account(client)
    card = _card(client, default_payment_account_id=acc["id"])
    assert card["name"] == "Nubank"
    assert card["limit_cents"] == 500000
    assert card["closing_day"] == 10
    assert card["due_day"] == 5
    assert card["used_limit_cents"] == 0
    assert card["available_limit_cents"] == 500000


def test_list_cards(client):
    _card(client, "Cartão 1")
    _card(client, "Cartão 2")
    cards = client.get("/api/v1/cards").json()
    assert len(cards) == 2


def test_update_card_limit(client):
    card = _card(client)
    r = client.patch(f"/api/v1/cards/{card['id']}", json={"limit_cents": 800000})
    assert r.status_code == 200
    assert r.json()["limit_cents"] == 800000


def test_card_archived_blocks_purchase(client):
    card = _card(client)
    client.patch(f"/api/v1/cards/{card['id']}", json={"archived": True})
    r = _purchase(client, card["id"], total=10000)
    assert r.status_code == 422 and r.json()["error"]["code"] == "card_archived"


# ---------- API: Compras ----------
def test_create_purchase_avista(client):
    card = _card(client)
    r = _purchase(client, card["id"], total=120000, installments=1)
    assert r.status_code == 201, r.text
    assert r.json()["installments_count"] == 1
    assert r.json()["total_cents"] == 120000


def test_create_purchase_parcelada(client):
    card = _card(client)
    r = _purchase(client, card["id"], total=120000, installments=6)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["installments_count"] == 6
    assert p["total_cents"] == 120000
    # Verifica parcelas criadas
    insts = client.get(f"/api/v1/cards/{card['id']}/upcoming").json()
    assert len(insts) == 6
    assert sum(i["amount_cents"] for i in insts) == 120000


def test_purchase_splits_cents_correctly(client):
    """R$ 100,00 em 3x = 33,34 + 33,33 + 33,33"""
    card = _card(client)
    r = _purchase(client, card["id"], total=10000, installments=3)
    assert r.status_code == 201
    insts = client.get(f"/api/v1/cards/{card['id']}/upcoming").json()
    amounts = sorted([i["amount_cents"] for i in insts])
    assert amounts == [3333, 3333, 3334]


def test_purchase_creates_statement(client):
    card = _card(client)
    _purchase(client, card["id"], total=120000)
    stmts = client.get(f"/api/v1/cards/{card['id']}/statements").json()
    assert len(stmts) == 1
    assert stmts[0]["total_cents"] == 120000
    assert stmts[0]["status"] == "OPEN"


def test_purchase_future_date_rejected(client):
    card = _card(client)
    future = (TODAY + timedelta(days=10)).isoformat()
    r = _purchase(client, card["id"], total=10000, purchased_on=future)
    assert r.status_code == 422 and r.json()["error"]["code"] == "future_purchase"


def test_purchase_invalid_category_kind(client):
    card = _card(client)
    # Cria categoria de receita
    cat = client.post("/api/v1/categories", json={"name": "Salario", "kind": "INCOME"}).json()
    assert cat.get("id"), f"Category creation failed: {cat}"
    r = _purchase(client, card["id"], total=10000, category_id=cat["id"])
    assert r.status_code == 422 and r.json()["error"]["code"] == "category_kind_mismatch"


def test_purchase_idempotency(client):
    card = _card(client)
    key = str(uuid.uuid4())
    r1 = _purchase(client, card["id"], total=50000, idempotency_key=key)
    r2 = _purchase(client, card["id"], total=50000, idempotency_key=key)
    assert r1.status_code == 201 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


# ---------- API: Faturas ----------
def test_list_statements(client):
    card = _card(client)
    _purchase(client, card["id"], total=10000)
    stmts = client.get(f"/api/v1/cards/{card['id']}/statements").json()
    assert len(stmts) >= 1


def test_parcelas_vao_para_faturas_consecutivas(client):
    """Regressão: as N parcelas iam todas para a 1ª fatura (cobrança do total de uma vez)."""
    card = _card(client)
    p = _purchase(client, card["id"], total=60001, installments=3).json()
    stmts = sorted(client.get(f"/api/v1/cards/{card['id']}/statements").json(), key=lambda s: s["due_date"])
    assert len(stmts) == 3
    assert [s["total_cents"] for s in stmts] == [20001, 20000, 20000]
    for prev, nxt in itertools.pairwise(stmts):
        assert nxt["cycle_start_date"] == prev["cycle_end_exclusive"]  # ciclos encadeados, sem buraco
    for n, s in enumerate(stmts, start=1):
        insts = client.get(f"/api/v1/cards/statements/{s['id']}/installments").json()
        assert len(insts) == 1
        assert insts[0]["purchase_id"] == p["id"] and insts[0]["installment_number"] == n

    # Uma 2ª compra no mesmo mês reaproveita as faturas existentes.
    _purchase(client, card["id"], total=10000, installments=2)
    stmts = sorted(client.get(f"/api/v1/cards/{card['id']}/statements").json(), key=lambda s: s["due_date"])
    assert [s["total_cents"] for s in stmts] == [25001, 25000, 20000]


# ---------- API: Pagamento de fatura ----------
def test_pay_statement_full(client):
    acc = _account(client, opening=200000)
    card = _card(client, default_payment_account_id=acc["id"])
    _purchase(client, card["id"], total=120000)

    stmts = client.get(f"/api/v1/cards/{card['id']}/statements").json()
    stmt_id = stmts[0]["id"]

    r = _pay_statement(client, stmt_id, acc["id"], 120000)
    assert r.status_code == 201, r.text

    # Verifica fatura paga
    stmt = client.get(f"/api/v1/cards/statements/{stmt_id}").json()
    assert stmt["status"] == "PAID"
    assert stmt["paid_cents"] == 120000

    # Verifica transação criada na conta
    acc_bal = next(a for a in client.get("/api/v1/accounts").json() if a["id"] == acc["id"])
    assert acc_bal["balance_cents"] == 80000  # 200000 - 120000

    # Dashboard (regime de caixa): o pagamento da fatura é a despesa do cartão, uma vez só.
    dash = client.get("/api/v1/dashboard").json()
    assert dash["kpis"]["expense"]["value_cents"] == 120000


def test_pay_statement_partial(client):
    acc = _account(client, opening=200000)
    card = _card(client, default_payment_account_id=acc["id"])
    _purchase(client, card["id"], total=120000)

    stmts = client.get(f"/api/v1/cards/{card['id']}/statements").json()
    stmt_id = stmts[0]["id"]

    r = _pay_statement(client, stmt_id, acc["id"], 50000)
    assert r.status_code == 201

    stmt = client.get(f"/api/v1/cards/statements/{stmt_id}").json()
    assert stmt["status"] == "PARTIALLY_PAID"
    assert stmt["paid_cents"] == 50000


def test_pay_statement_overpayment_rejected(client):
    acc = _account(client, opening=200000)
    card = _card(client, default_payment_account_id=acc["id"])
    _purchase(client, card["id"], total=120000)

    stmts = client.get(f"/api/v1/cards/{card['id']}/statements").json()
    stmt_id = stmts[0]["id"]

    r = _pay_statement(client, stmt_id, acc["id"], 150000)
    assert r.status_code == 422 and r.json()["error"]["code"] == "overpayment"


def test_pay_statement_idempotency(client):
    acc = _account(client, opening=200000)
    card = _card(client, default_payment_account_id=acc["id"])
    _purchase(client, card["id"], total=10000)

    stmts = client.get(f"/api/v1/cards/{card['id']}/statements").json()
    stmt_id = stmts[0]["id"]
    key = str(uuid.uuid4())

    # Primeira chamada com a chave de idempotência
    r1 = client.post(
        f"/api/v1/cards/statements/{stmt_id}/payments",
        json={
            "statement_id": stmt_id,
            "account_id": acc["id"],
            "amount_cents": 10000,
            "paid_on": D,
            "idempotency_key": key,
        },
    )
    assert r1.status_code == 201

    # Segunda chamada com mesma chave deve retornar 200
    r2 = client.post(
        f"/api/v1/cards/statements/{stmt_id}/payments",
        json={
            "statement_id": stmt_id,
            "account_id": acc["id"],
            "amount_cents": 10000,
            "paid_on": D,
            "idempotency_key": key,
        },
    )
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]

    # Saldo da conta debitado apenas uma vez
    acc_bal = next(a for a in client.get("/api/v1/accounts").json() if a["id"] == acc["id"])
    assert acc_bal["balance_cents"] == 190000


def test_payment_marks_installments_paid(client):
    """Pagamento integral marca as parcelas daquela fatura como PAID (e só elas)."""
    acc = _account(client, opening=200000)
    card = _card(client, default_payment_account_id=acc["id"])
    _purchase(client, card["id"], total=60000, installments=3)

    stmts = sorted(client.get(f"/api/v1/cards/{card['id']}/statements").json(), key=lambda s: s["due_date"])
    stmt_id = stmts[0]["id"]

    r = _pay_statement(client, stmt_id, acc["id"], 20000)
    assert r.status_code == 201, r.text

    insts = client.get(f"/api/v1/cards/statements/{stmt_id}/installments").json()
    assert insts and all(i["status"] == "PAID" for i in insts)
    later = client.get(f"/api/v1/cards/statements/{stmts[1]['id']}/installments").json()
    assert all(i["status"] != "PAID" for i in later)


# ---------- Limite utilizado ----------
def test_used_limit_updates_on_purchase(client):
    card = _card(client, limit=500000)
    assert card["available_limit_cents"] == 500000

    _purchase(client, card["id"], total=120000)

    card_updated = client.get(f"/api/v1/cards/{card['id']}").json()
    assert card_updated["used_limit_cents"] == 120000
    assert card_updated["available_limit_cents"] == 380000


def test_used_limit_updates_on_payment(client):
    acc = _account(client, opening=200000)
    card = _card(client, limit=500000, default_payment_account_id=acc["id"])
    _purchase(client, card["id"], total=120000)

    stmts = client.get(f"/api/v1/cards/{card['id']}/statements").json()
    stmt_id = stmts[0]["id"]
    _pay_statement(client, stmt_id, acc["id"], 120000)

    card_updated = client.get(f"/api/v1/cards/{card['id']}").json()
    # Após pagar a fatura, o limite é liberado (parcelas pagas saem do usado)
    assert card_updated["used_limit_cents"] == 0
    assert card_updated["available_limit_cents"] == 500000


# ---------- Próximas parcelas ----------
def test_upcoming_installments_sorted(client):
    card = _card(client)
    _purchase(client, card["id"], total=30000, installments=3)
    insts = client.get(f"/api/v1/cards/{card['id']}/upcoming").json()
    assert len(insts) == 3
    assert insts[0]["installment_number"] == 1
    assert insts[1]["installment_number"] == 2
    assert insts[2]["installment_number"] == 3


# ---------- Dashboard não duplica despesa ----------
def test_dashboard_cartao_conta_uma_vez_pelo_pagamento_da_fatura(client):
    """Regime de caixa: a compra não é despesa; o pagamento da fatura é, uma única vez."""
    acc = _account(client, opening=500000)
    card = _card(client, default_payment_account_id=acc["id"])
    _purchase(client, card["id"], total=100000)

    # Compra no cartão ainda não saiu do caixa, mas já é compromisso (fatura a vencer).
    dash = client.get("/api/v1/dashboard").json()
    assert dash["kpis"]["expense"]["value_cents"] == 0
    assert dash["kpis"]["due_soon"]["value_cents"] + dash["kpis"]["overdue"]["value_cents"] in (0, 100000)

    stmts = client.get(f"/api/v1/cards/{card['id']}/statements").json()
    _pay_statement(client, stmts[0]["id"], acc["id"], 100000)

    dash = client.get("/api/v1/dashboard").json()
    # Uma única despesa: o pagamento da fatura (não a compra + o pagamento).
    assert dash["kpis"]["expense"]["value_cents"] == 100000
    assert dash["kpis"]["available_balance"]["value_cents"] == 400000
    # Rosca, relatório de fluxo de caixa e KPI contam o mesmo valor.
    assert sum(c["amount_cents"] for c in dash["expenses_by_category"]) == 100000
    flow = client.get("/api/v1/reports/cash-flow", params={"from": dash["period_from"], "to": dash["period_to"]}).json()
    assert flow["expense_cents"] == 100000
    # A evolução do saldo termina no saldo disponível real.
    real = [p for p in dash["balance_series"] if not p["projected"]]
    assert real[-1]["balance_cents"] == 400000