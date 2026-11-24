"""Testes para contas da casa (bills), recorrências e parcelas."""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


# ---------- Helpers ----------

def _account(client, name="Conta", opening=1000000, opening_date=None):
    if opening_date is None:
        opening_date = date.today().isoformat()
    r = client.post(
        "/api/v1/accounts",
        json={"name": name, "type": "CHECKING", "opening_balance_cents": opening, "opening_date": opening_date},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _bill(client, account_id, name="Internet", category="INTERNET", amount=15000, color="#EF4444"):
    r = client.post(
        "/api/v1/bills",
        json={
            "name": name,
            "category": category,
            "account_id": account_id,
            "default_amount_cents": amount,
            "color": color,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _recurrence(client, bill_id, frequency="MONTHLY", day=10, start=None, auto_post=True):
    if start is None:
        start = date.today().replace(day=1).isoformat()
    r = client.post(
        "/api/v1/bills/recurrences",
        json={
            "bill_id": bill_id,
            "frequency": frequency,
            "day_of_month": day,
            "start_date": start,
            "auto_post": auto_post,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _installment(client, bill_id, due, amount=10000, recurrence_id=None, notes=None):
    body = {"bill_id": bill_id, "due_date": due.isoformat(), "amount_cents": amount}
    if recurrence_id:
        body["recurrence_id"] = recurrence_id
    if notes:
        body["notes"] = notes
    r = client.post("/api/v1/bills/installments", json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ---------- Tests: Bills CRUD ----------

def test_create_bill(client):
    """Criação de conta da casa."""
    acc = _account(client)
    r = client.post(
        "/api/v1/bills",
        json={
            "name": "Água",
            "category": "WATER",
            "account_id": acc["id"],
            "default_amount_cents": 8000,
            "color": "#3B82F6",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Água"
    assert data["category"] == "WATER"
    assert data["default_amount_cents"] == 8000
    assert data["color"] == "#3B82F6"
    assert data["account_id"] == acc["id"]
    assert data["archived_at"] is None


def test_create_bill_invalid_category(client):
    """Categoria inválida deve retornar 422."""
    acc = _account(client)
    r = client.post(
        "/api/v1/bills",
        json={
            "name": "Teste",
            "category": "INVALID",
            "account_id": acc["id"],
            "default_amount_cents": 1000,
        },
    )
    assert r.status_code == 422


def test_list_bills(client):
    """Lista contas da casa."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    r = client.get("/api/v1/bills")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert any(bill["id"] == b["id"] for bill in data)


def test_get_bill(client):
    """Busca conta por ID."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    r = client.get(f"/api/v1/bills/{b['id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == b["id"]
    assert data["name"] == b["name"]


def test_update_bill(client):
    """Atualiza conta."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    r = client.patch(
        f"/api/v1/bills/{b['id']}",
        json={"name": "Internet Fibra", "default_amount_cents": 18000},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Internet Fibra"
    assert data["default_amount_cents"] == 18000


def test_archive_bill(client):
    """Arquiva conta (soft delete)."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    r = client.post(f"/api/v1/bills/{b['id']}/archive")
    assert r.status_code == 200
    data = r.json()
    assert data["archived_at"] is not None

    # Não aparece na lista padrão
    r2 = client.get("/api/v1/bills")
    assert not any(bill["id"] == b["id"] for bill in r2.json())

    # Aparece com include_archived
    r3 = client.get("/api/v1/bills?include_archived=true")
    assert any(bill["id"] == b["id"] for bill in r3.json())


def test_restore_bill(client):
    """Restaura conta arquivada."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    client.post(f"/api/v1/bills/{b['id']}/archive")
    r = client.post(f"/api/v1/bills/{b['id']}/restore")
    assert r.status_code == 200
    data = r.json()
    assert data["archived_at"] is None


# ---------- Tests: Recorrências ----------

def test_create_recurrence(client):
    """Cria recorrência mensal."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    r = client.post(
        "/api/v1/bills/recurrences",
        json={
            "bill_id": b["id"],
            "frequency": "MONTHLY",
            "day_of_month": 15,
            "start_date": date.today().isoformat(),
            "auto_post": True,
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["bill_id"] == b["id"]
    assert data["frequency"] == "MONTHLY"
    assert data["day_of_month"] == 15
    assert data["status"] == "ACTIVE"
    assert data["auto_post"] is True


def test_create_recurrence_custom_requires_interval(client):
    """Frequência CUSTOM exige custom_months_interval."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    r = client.post(
        "/api/v1/bills/recurrences",
        json={
            "bill_id": b["id"],
            "frequency": "CUSTOM",
            "day_of_month": 1,
            "start_date": date.today().isoformat(),
        },
    )
    assert r.status_code == 400
    assert "CUSTOM" in r.json()["error"]["message"]


def test_create_recurrence_invalid_day(client):
    """day_of_month inválido."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    r = client.post(
        "/api/v1/bills/recurrences",
        json={
            "bill_id": b["id"],
            "frequency": "MONTHLY",
            "day_of_month": 32,
            "start_date": date.today().isoformat(),
        },
    )
    assert r.status_code == 422  # Pydantic validation error


def test_list_recurrences(client):
    """Lista recorrências."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    rec = _recurrence(client, b["id"])
    resp = client.get("/api/v1/bills/recurrences")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(item["id"] == rec["id"] for item in data)


def test_update_recurrence(client):
    """Atualiza recorrência."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    rec = _recurrence(client, b["id"])
    r = client.patch(
        f"/api/v1/bills/recurrences/{rec['id']}",
        json={"day_of_month": 20, "auto_post": False},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["day_of_month"] == 20
    assert data["auto_post"] is False


def test_update_recurrence_frequency_change(client):
    """Mudança de frequência com validação."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    rec = _recurrence(client, b["id"])

    # Muda para CUSTOM sem interval -> erro
    r = client.patch(
        f"/api/v1/bills/recurrences/{rec['id']}",
        json={"frequency": "CUSTOM"},
    )
    assert r.status_code == 400

    # Muda para CUSTOM com interval -> ok
    r = client.patch(
        f"/api/v1/bills/recurrences/{rec['id']}",
        json={"frequency": "CUSTOM", "custom_months_interval": 3},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["frequency"] == "CUSTOM"
    assert data["custom_months_interval"] == 3


# ---------- Tests: Parcelas (Installments) ----------

def test_create_manual_installment(client):
    """Cria parcela manual."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    due = date.today() + timedelta(days=10)
    r = client.post(
        "/api/v1/bills/installments",
        json={
            "bill_id": b["id"],
            "due_date": due.isoformat(),
            "amount_cents": 12000,
            "notes": "Parcela única",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["bill_id"] == b["id"]
    assert data["due_date"] == due.isoformat()
    assert data["amount_cents"] == 12000
    assert data["status"] == "PENDING"
    assert data["recurrence_id"] is None


def test_list_installments(client):
    """Lista parcelas."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    due = date.today() + timedelta(days=5)
    inst = _installment(client, b["id"], due, 5000)
    print(f"DEBUG installment created: {inst}")
    r = client.get("/api/v1/bills/installments")
    print(f"DEBUG list_installments: {r.status_code}, {r.json()}")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


def test_upcoming_installments(client):
    """Parcelas próximas do vencimento."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    due = date.today() + timedelta(days=3)
    _installment(client, b["id"], due, 5000)
    r = client.get("/api/v1/bills/installments/upcoming?days=7")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert all(i["status"] in ("PENDING", "POSTED") for i in data)


def test_overdue_installments(client):
    """Parcelas vencidas."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    due = date.today() - timedelta(days=5)
    _installment(client, b["id"], due, 5000)
    r = client.get("/api/v1/bills/installments/overdue")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert all(i["status"] in ("PENDING", "POSTED") for i in data)


def test_pay_installment(client):
    """Paga uma parcela."""
    acc = _account(client, opening=50000)
    b = _bill(client, acc["id"])
    due = date.today() + timedelta(days=1)
    inst = _installment(client, b["id"], due, 10000)

    r = client.post(
        f"/api/v1/bills/installments/{inst['id']}/pay",
        params={
            "account_id": acc["id"],
            "paid_on": date.today().isoformat(),
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "PAID"
    assert data["paid_at"] is not None
    assert data["transaction_id"] is not None


def test_pay_installment_idempotency(client):
    """Idempotência no pagamento de parcela."""
    acc = _account(client, opening=50000)
    b = _bill(client, acc["id"])
    due = date.today() + timedelta(days=1)
    inst = _installment(client, b["id"], due, 10000)
    idem_key = "pay-bill-123"

    # Primeira chamada
    r1 = client.post(
        f"/api/v1/bills/installments/{inst['id']}/pay",
        params={
            "account_id": acc["id"],
            "paid_on": date.today().isoformat(),
            "idempotency_key": idem_key,
        },
    )
    assert r1.status_code == 200

    # Segunda chamada com mesma chave -> mesmo resultado
    r2 = client.post(
        f"/api/v1/bills/installments/{inst['id']}/pay",
        params={
            "account_id": acc["id"],
            "paid_on": date.today().isoformat(),
            "idempotency_key": idem_key,
        },
    )
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    assert r1.json()["transaction_id"] == r2.json()["transaction_id"]


def test_reverse_installment_payment(client):
    """Estorna pagamento de parcela."""
    acc = _account(client, opening=50000)
    b = _bill(client, acc["id"])
    due = date.today() + timedelta(days=1)
    inst = _installment(client, b["id"], due, 10000)

    # Paga
    client.post(
        f"/api/v1/bills/installments/{inst['id']}/pay",
        params={"account_id": acc["id"], "paid_on": date.today().isoformat()},
    )

    # Estorna
    r = client.post(
        f"/api/v1/bills/installments/{inst['id']}/reverse",
        params={"idempotency_key": "reverse-123"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "REVERSED"
    assert data["reversed_at"] is not None


def test_skip_installment(client):
    """Marca parcela como SKIPPED."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    due = date.today() + timedelta(days=1)
    inst = _installment(client, b["id"], due, 10000)

    r = client.post(
        f"/api/v1/bills/installments/{inst['id']}/skip",
        params={"idempotency_key": "skip-123"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "SKIPPED"


def test_cancel_installment(client):
    """Cancela parcela."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    due = date.today() + timedelta(days=1)
    inst = _installment(client, b["id"], due, 10000)

    r = client.post(
        f"/api/v1/bills/installments/{inst['id']}/cancel",
        params={"idempotency_key": "cancel-123"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "CANCELLED"


def test_cannot_cancel_paid_installment(client):
    """Não pode cancelar parcela paga."""
    acc = _account(client, opening=50000)
    b = _bill(client, acc["id"])
    due = date.today() + timedelta(days=1)
    inst = _installment(client, b["id"], due, 10000)

    client.post(
        f"/api/v1/bills/installments/{inst['id']}/pay",
        params={"account_id": acc["id"], "paid_on": date.today().isoformat()},
    )

    r = client.post(f"/api/v1/bills/installments/{inst['id']}/cancel")
    assert r.status_code == 400


# ---------- Tests: Auto-post de recorrências ----------

def test_post_installments_from_recurrence(client):
    """Gera parcelas a partir de recorrência."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    rec = _recurrence(client, b["id"])
    up_to = date.today() + timedelta(days=60)
    r = client.post(
        f"/api/v1/bills/recurrences/{rec['id']}/post-installments",
        params={"up_to_date": up_to.isoformat()},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert all(i["recurrence_id"] == rec["id"] for i in data)
    assert all(i["status"] == "PENDING" for i in data)


def test_auto_post_global(client):
    """Auto-post global processa todas as recorrências ativas."""
    acc = _account(client)
    b = _bill(client, acc["id"])
    _recurrence(client, b["id"])
    r = client.post(
        "/api/v1/bills/auto-post",
        params={"up_to_date": (date.today() + timedelta(days=60)).isoformat()},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1


# ---------- Tests: Regras de negócio (unit tests sem DB) ----------

def test_recurrence_generates_correct_dates():
    """Verifica geração de datas corretas para recorrência mensal."""
    from app.domains.bills.rules import generate_installment_dates

    start = date(2025, 1, 10)
    dates = generate_installment_dates(
        start_date=start,
        frequency="MONTHLY",
        day_of_month=10,
        end_date=date(2025, 4, 10),
    )
    assert dates == [
        date(2025, 1, 10),
        date(2025, 2, 10),
        date(2025, 3, 10),
        date(2025, 4, 10),
    ]


def test_recurrence_bimonthly():
    """Recorrência bimestral."""
    from app.domains.bills.rules import generate_installment_dates

    start = date(2025, 1, 15)
    dates = generate_installment_dates(
        start_date=start,
        frequency="BIMONTHLY",
        day_of_month=15,
        end_date=date(2025, 7, 15),
    )
    assert dates == [
        date(2025, 1, 15),
        date(2025, 3, 15),
        date(2025, 5, 15),
        date(2025, 7, 15),
    ]


def test_recurrence_quarterly():
    """Recorrência trimestral."""
    from app.domains.bills.rules import generate_installment_dates

    start = date(2025, 1, 20)
    dates = generate_installment_dates(
        start_date=start,
        frequency="QUARTERLY",
        day_of_month=20,
        end_date=date(2025, 10, 20),
    )
    assert dates == [
        date(2025, 1, 20),
        date(2025, 4, 20),
        date(2025, 7, 20),
        date(2025, 10, 20),
    ]


def test_recurrence_day_adjustment():
    """Ajuste de dia quando mês não tem o dia (ex: 31 em abril)."""
    from app.domains.bills.rules import generate_installment_dates

    start = date(2025, 1, 31)
    dates = generate_installment_dates(
        start_date=start,
        frequency="MONTHLY",
        day_of_month=31,
        end_date=date(2025, 5, 31),
    )
    # Janeiro 31, Fevereiro 28, Março 31, Abril 30, Maio 31
    assert dates == [
        date(2025, 1, 31),
        date(2025, 2, 28),
        date(2025, 3, 31),
        date(2025, 4, 30),
        date(2025, 5, 31),
    ]


def test_calculate_installment_amounts():
    """Divisão exata de centavos entre parcelas."""
    from app.domains.bills.rules import calculate_installment_amounts

    # 10000 centavos / 3 = 3334, 3333, 3333
    amounts = calculate_installment_amounts(10000, 3)
    assert amounts == [3334, 3333, 3333]
    assert sum(amounts) == 10000

    # 15000 centavos / 4 = 3750, 3750, 3750, 3750
    amounts = calculate_installment_amounts(15000, 4)
    assert amounts == [3750, 3750, 3750, 3750]

    # 1 centavo / 1 = 1
    amounts = calculate_installment_amounts(1, 1)
    assert amounts == [1]


def test_is_recurrence_active():
    """Verifica status ativo de recorrência."""
    from app.domains.bills.rules import is_recurrence_active

    today = date.today()

    # Ativa, dentro do período
    assert is_recurrence_active("ACTIVE", today, today - timedelta(days=10), today + timedelta(days=10))

    # Pausada
    assert not is_recurrence_active("PAUSED", today, today - timedelta(days=10), today + timedelta(days=10))

    # Encerrada
    assert not is_recurrence_active("ENDED", today, today - timedelta(days=10), today + timedelta(days=10))

    # Ainda não começou
    assert not is_recurrence_active("ACTIVE", today, today + timedelta(days=5), None)

    # Já terminou
    assert not is_recurrence_active("ACTIVE", today, None, today - timedelta(days=5))


# ---------- Tests: Autenticação ----------

def test_bills_require_auth(client):
    """Todas as rotas de bills exigem autenticação."""
    # O client do conftest já tem auth, testamos com anon_client
    from tests.conftest import make_token
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as anon:
        endpoints = [
            ("GET", "/api/v1/bills"),
            ("POST", "/api/v1/bills"),
            ("GET", "/api/v1/bills/recurrences"),
            ("POST", "/api/v1/bills/recurrences"),
            ("GET", "/api/v1/bills/installments"),
            ("POST", "/api/v1/bills/installments"),
            ("GET", "/api/v1/bills/installments/upcoming"),
            ("GET", "/api/v1/bills/installments/overdue"),
            ("POST", "/api/v1/bills/auto-post"),
        ]
        for method, url in endpoints:
            r = anon.request(method, url)
            assert r.status_code == 401, f"{method} {url} should require auth"