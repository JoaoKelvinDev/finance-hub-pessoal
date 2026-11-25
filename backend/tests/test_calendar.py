"""Testes do calendário financeiro unificado."""

import uuid
from datetime import date, timedelta

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


def _bill(client, account_id, name="Internet", amount=12000):
    r = client.post(
        "/api/v1/bills",
        json={"name": name, "category": "INTERNET", "account_id": account_id, "default_amount_cents": amount},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _recurrence(client, bill_id, start, day):
    r = client.post(
        "/api/v1/bills/recurrences",
        json={"bill_id": bill_id, "frequency": "MONTHLY", "day_of_month": day, "start_date": start.isoformat(),
              "auto_post": False},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _installment(client, bill_id, due, amount=12000, recurrence_id=None):
    body = {"bill_id": bill_id, "due_date": due.isoformat(), "amount_cents": amount}
    if recurrence_id:
        body["recurrence_id"] = recurrence_id
    r = client.post("/api/v1/bills/installments", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _card_with_purchase(client, account_id, total=90000):
    r = client.post(
        "/api/v1/cards",
        json={"name": "Nubank", "limit_cents": 500000, "closing_day": 10, "due_day": 5, "due_month_offset": 1,
              "purchase_boundary_policy": "EXCLUSIVE", "default_payment_account_id": account_id},
    )
    assert r.status_code == 201, r.text
    card = r.json()
    r = client.post(
        "/api/v1/cards/purchases",
        json={"card_id": card["id"], "description": "Mercado", "purchased_on": D, "total_cents": total,
              "installments_count": 1},
    )
    assert r.status_code in (200, 201), r.text
    stmt = client.get(f"/api/v1/cards/{card['id']}/statements").json()[0]
    return card, stmt


def _calendar(client, start: date, end: date):
    r = client.get("/api/v1/calendar", params={"from": start.isoformat(), "to": end.isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


# ---------- Consolidação ----------

def test_calendar_consolida_quatro_origens(client):
    acc = _account(client)
    bill = _bill(client, acc["id"])
    _installment(client, bill["id"], TODAY + timedelta(days=3))
    other = _bill(client, acc["id"], name="Streaming", amount=5000)
    _recurrence(client, other["id"], TODAY + timedelta(days=1), (TODAY + timedelta(days=1)).day)
    _card_with_purchase(client, acc["id"])
    r = client.post(
        "/api/v1/transactions",
        json={"account_id": acc["id"], "kind": "INCOME", "amount_cents": 300000, "status": "PLANNED",
              "effective_date": (TODAY + timedelta(days=5)).isoformat(), "description": "Salário"},
    )
    assert r.status_code == 201, r.text

    start = TODAY
    data = _calendar(client, start, start + timedelta(days=45))
    sources = {e["source"] for e in data["events"]}
    assert sources == {"CARD_STATEMENT", "BILL_INSTALLMENT", "RECURRENCE_FORECAST", "PLANNED_TRANSACTION"}
    assert len({e["key"] for e in data["events"]}) == len(data["events"])
    assert data["summary"]["to_receive_cents"] == 300000
    income = next(e for e in data["events"] if e["source"] == "PLANNED_TRANSACTION")
    assert income["direction"] == "IN" and income["amount_cents"] == 300000


def test_previsao_some_quando_parcela_ja_existe(client):
    acc = _account(client)
    bill = _bill(client, acc["id"])
    due = TODAY + timedelta(days=2)
    rec = _recurrence(client, bill["id"], due, due.day)

    start, end = TODAY, TODAY + timedelta(days=20)
    before = [e for e in _calendar(client, start, end)["events"] if e["date"] == due.isoformat()]
    assert [e["source"] for e in before] == ["RECURRENCE_FORECAST"]

    _installment(client, bill["id"], due, amount=13000, recurrence_id=rec["id"])
    after = [e for e in _calendar(client, start, end)["events"] if e["date"] == due.isoformat()]
    assert [e["source"] for e in after] == ["BILL_INSTALLMENT"]
    assert after[0]["amount_cents"] == 13000


def test_previsao_ajusta_dia_31_em_mes_curto(client):
    acc = _account(client)
    bill = _bill(client, acc["id"])
    _recurrence(client, bill["id"], date(2027, 1, 31), 31)
    data = _calendar(client, date(2027, 2, 1), date(2027, 2, 28))
    assert [e["date"] for e in data["events"]] == ["2027-02-28"]
    assert data["events"][0]["status"] == "FORECAST"


def test_fatura_desconta_pagamento_parcial(client):
    acc = _account(client)
    card, stmt = _card_with_purchase(client, acc["id"], total=90000)
    r = client.post(
        f"/api/v1/cards/statements/{stmt['id']}/payments",
        json={"statement_id": stmt["id"], "account_id": acc["id"], "amount_cents": 30000, "paid_on": D,
              "idempotency_key": str(uuid.uuid4())},
    )
    assert r.status_code == 201, r.text

    due = date.fromisoformat(stmt["due_date"])
    data = _calendar(client, due - timedelta(days=1), due + timedelta(days=1))
    ev = next(e for e in data["events"] if e["source"] == "CARD_STATEMENT")
    assert ev["amount_cents"] == 90000
    assert ev["open_cents"] == 60000
    assert ev["status"] == "PARTIAL"
    assert ev["ref_id"] == card["id"]
    # O pagamento (transação POSTED) não vira evento próprio.
    assert all(e["source"] != "PLANNED_TRANSACTION" for e in data["events"])
    assert data["summary"]["to_pay_cents"] == 60000
    assert data["summary"]["paid_cents"] == 30000


def test_parcela_paga_vencida_e_cancelada(client):
    acc = _account(client)
    bill = _bill(client, acc["id"])
    late = _installment(client, bill["id"], TODAY - timedelta(days=3), amount=7000)
    paid = _installment(client, bill["id"], TODAY + timedelta(days=1), amount=8000)
    cancelled = _installment(client, bill["id"], TODAY + timedelta(days=2), amount=9000)

    r = client.post(
        f"/api/v1/bills/installments/{paid['id']}/pay", params={"account_id": acc["id"], "paid_on": D}
    )
    assert r.status_code == 200, r.text
    assert client.post(f"/api/v1/bills/installments/{cancelled['id']}/cancel").status_code == 200

    data = _calendar(client, TODAY - timedelta(days=10), TODAY + timedelta(days=10))
    by_id = {e["source_id"]: e for e in data["events"] if e["source"] == "BILL_INSTALLMENT"}
    assert cancelled["id"] not in by_id
    assert by_id[late["id"]]["status"] == "OVERDUE"
    assert by_id[paid["id"]]["status"] == "PAID" and by_id[paid["id"]]["open_cents"] == 0
    assert data["summary"]["overdue_cents"] == 7000
    assert data["summary"]["overdue_count"] == 1
    assert data["summary"]["paid_cents"] == 8000
    # Pagamento da parcela não aparece duplicado como lançamento.
    assert {e["source"] for e in data["events"]} == {"BILL_INSTALLMENT"}


def test_totais_por_dia(client):
    acc = _account(client)
    bill = _bill(client, acc["id"])
    day = TODAY + timedelta(days=4)
    _installment(client, bill["id"], day, amount=1000)
    _installment(client, bill["id"], day, amount=2500)
    data = _calendar(client, TODAY, TODAY + timedelta(days=10))
    d = next(x for x in data["days"] if x["date"] == day.isoformat())
    assert d == {"date": day.isoformat(), "out_cents": 3500, "in_cents": 0, "count": 2}


# ---------- Validação ----------

def test_intervalo_invertido_recusado(client):
    r = client.get("/api/v1/calendar", params={"from": "2026-12-10", "to": "2026-12-01"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_range"


def test_intervalo_grande_recusado(client):
    r = client.get("/api/v1/calendar", params={"from": "2026-01-01", "to": "2026-06-30"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "range_too_large"


def test_calendario_exige_proprietario(anon_client):
    r = anon_client.get("/api/v1/calendar", params={"from": "2026-12-01", "to": "2026-12-31"})
    assert r.status_code == 401
