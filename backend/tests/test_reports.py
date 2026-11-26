"""Etapa 5B — relatórios, exportação CSV e backup/restauração."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.core.errors import DomainError
from app.domains.reporting.exports import money
from app.domains.support import today_local

TODAY = today_local()
D = TODAY.isoformat()
MONTH_START = TODAY.replace(day=1)


def _account(client, name="Conta", opening=1_000_000):
    r = client.post(
        "/api/v1/accounts",
        json={"name": name, "type": "CHECKING", "opening_balance_cents": opening, "opening_date": "2026-01-01"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _cat(client, name):
    return next(c for c in client.get("/api/v1/categories").json() if c["name"] == name)


def _tx(client, account_id, kind, amount, category_id=None, date=None, description="Lançamento"):
    body = {"account_id": account_id, "kind": kind, "amount_cents": amount, "effective_date": date or D,
            "description": description}
    if category_id:
        body["category_id"] = category_id
    r = client.post("/api/v1/transactions", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _card(client, account_id, name="Roxinho", bank="Nubank"):
    r = client.post(
        "/api/v1/cards",
        json={"name": name, "bank": bank, "limit_cents": 500_000, "closing_day": 10, "due_day": 5,
              "due_month_offset": 1, "purchase_boundary_policy": "EXCLUSIVE", "default_payment_account_id": account_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _purchase(client, card_id, total, merchant=None, category_id=None, n=1):
    r = client.post(
        "/api/v1/cards/purchases",
        json={"card_id": card_id, "description": "Compra", "merchant": merchant, "purchased_on": D,
              "total_cents": total, "installments_count": n, "category_id": category_id},
    )
    assert r.status_code in (200, 201), r.text


def _params(**extra):
    return {"from": MONTH_START.isoformat(), "to": D, **extra}


# ---------- formato ----------

def test_money_formato_excel_ptbr():
    assert money(123456) == "1234,56"
    assert money(-5) == "-0,05"
    assert money(0) == "0,00"


# ---------- categorias ----------

def test_relatorio_categorias_agrupa_subcategorias_e_bate_com_orcamento(client):
    acc = _account(client)
    mercado, feira = _cat(client, "Mercado"), _cat(client, "Feira")
    _tx(client, acc["id"], "EXPENSE", 30_000, mercado["id"])
    _tx(client, acc["id"], "EXPENSE", 5_000, feira["id"])
    _tx(client, acc["id"], "EXPENSE", 2_000)  # sem categoria
    _tx(client, acc["id"], "INCOME", 99_000)  # receita não entra

    r = client.get("/api/v1/reports/categories", params=_params())
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_cents"] == 37_000
    alimentacao = next(row for row in data["rows"] if row["name"] == "Alimentação")
    assert alimentacao["amount_cents"] == 35_000
    assert {c["name"]: c["amount_cents"] for c in alimentacao["children"]} == {"Mercado": 30_000, "Feira": 5_000}
    assert any(row["name"] == "Sem categoria" and row["amount_cents"] == 2_000 for row in data["rows"])
    # A soma das linhas é exatamente o total exibido.
    assert sum(row["amount_cents"] for row in data["rows"]) == data["total_cents"]

    # Mesma fonte dos orçamentos.
    month_end = (MONTH_START.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    b = client.post(
        "/api/v1/budgets",
        json={"category_id": _cat(client, "Alimentação")["id"], "period_start": MONTH_START.isoformat(),
              "period_end": month_end.isoformat(), "limit_cents": 100_000},
    ).json()
    assert b["spent_cents"] == alimentacao["amount_cents"]


def test_relatorio_categorias_cartao_competencia(client):
    acc = _account(client)
    lazer = _cat(client, "Lazer")
    card = _card(client, acc["id"])
    _purchase(client, card["id"], 8_000, "Cinema", lazer["id"])
    caixa = client.get("/api/v1/reports/categories", params=_params(basis="CASH")).json()
    competencia = client.get("/api/v1/reports/categories", params=_params(basis="COMPETENCE")).json()
    assert caixa["total_cents"] == 0  # fatura ainda não paga
    assert competencia["total_cents"] == 8_000


# ---------- fluxo de caixa ----------

def test_fluxo_de_caixa_ignora_transferencias_e_terceiros(client):
    a1, a2 = _account(client, "A"), _account(client, "B")
    _tx(client, a1["id"], "INCOME", 50_000)
    _tx(client, a1["id"], "EXPENSE", 12_000)
    client.post("/api/v1/transfers", json={"from_account_id": a1["id"], "to_account_id": a2["id"],
                                           "amount_cents": 20_000, "effective_date": D, "description": "Mover"})
    p = client.post("/api/v1/people", json={"display_name": "Ana"}).json()
    client.post("/api/v1/party-balances", json={"person_id": p["id"], "origin_type": "LOAN_GIVEN",
                                                "description": "Empréstimo", "principal_cents": 7_000,
                                                "operation_date": D, "account_id": a1["id"]})
    data = client.get("/api/v1/reports/cash-flow", params=_params()).json()
    assert data["granularity"] == "day"
    assert data["income_cents"] == 50_000
    assert data["expense_cents"] == 12_000
    assert data["net_cents"] == 38_000
    assert sum(pt["net_cents"] for pt in data["points"]) == data["net_cents"]

    longo = client.get("/api/v1/reports/cash-flow",
                       params={"from": (TODAY - timedelta(days=200)).isoformat(), "to": D}).json()
    assert longo["granularity"] == "month"


# ---------- cartões ----------

def test_relatorio_cartoes(client):
    acc = _account(client)
    card = _card(client, acc["id"])
    _purchase(client, card["id"], 4_490, "Netflix")
    _purchase(client, card["id"], 60_000, "Loja", n=3)
    data = client.get("/api/v1/reports/cards", params=_params()).json()
    row = data["cards"][0]
    assert row["purchases_cents"] == 64_490 and row["purchases_count"] == 2
    assert row["open_cents"] == 64_490
    # Parcelas em faturas que vencem depois de hoje.
    assert row["future_cents"] > 0
    assert row["top_merchants"][0]["name"] == "Loja"
    assert {m["name"] for m in row["top_merchants"]} == {"Loja", "Netflix"}


# ---------- terceiros ----------

def test_aging_de_recebiveis(client):
    p = client.post("/api/v1/people", json={"display_name": "Bia"}).json()

    def owed(amount, days_late, due=True):
        body = {"person_id": p["id"], "origin_type": "OWED_TO_ME", "description": "x", "principal_cents": amount,
                "operation_date": (TODAY - timedelta(days=200)).isoformat()}
        if due:
            body["due_date"] = (TODAY - timedelta(days=days_late)).isoformat()
        assert client.post("/api/v1/party-balances", json=body).status_code == 201

    owed(1_000, 10)
    owed(2_000, 45)
    owed(3_000, 75)
    owed(4_000, 120)
    owed(5_000, -5)
    owed(6_000, 0, due=False)
    client.post("/api/v1/party-balances", json={"person_id": p["id"], "origin_type": "I_OWE", "description": "y",
                                                "principal_cents": 700, "operation_date": D})

    data = client.get("/api/v1/reports/counterparties").json()
    aging = data["receivable_aging"]
    assert aging == {"current_cents": 5_000, "d0_30_cents": 1_000, "d31_60_cents": 2_000, "d61_90_cents": 3_000,
                     "d90_plus_cents": 4_000, "no_due_cents": 6_000}
    assert data["receivable_cents"] == 21_000
    assert data["payable_cents"] == 700


# ---------- exportação ----------

def test_exportacao_csv_para_excel_e_auditada(client):
    acc = _account(client)
    _tx(client, acc["id"], "EXPENSE", 123_456, _cat(client, "Mercado")["id"], description="Compra do mês; atacado")
    r = client.get("/api/v1/exports/transactions.csv", params=_params())
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    raw = r.content
    assert raw.startswith("﻿".encode())
    body = raw.decode("utf-8-sig")
    lines = body.strip().split("\r\n")
    assert lines[0].startswith("Data;Descrição;Tipo")
    assert '"Compra do mês; atacado"' in lines[1]  # ";" dentro do texto fica entre aspas
    assert lines[1].endswith("-1234,56")

    for kind in ("card-purchases", "party-balances", "categories", "cash-flow", "cards", "counterparties"):
        assert client.get(f"/api/v1/exports/{kind}.csv", params=_params()).status_code == 200, kind
    assert client.get("/api/v1/exports/inexistente.csv").status_code == 422

    cats = client.get("/api/v1/exports/categories.csv", params=_params()).content.decode("utf-8-sig")
    assert cats.strip().split("\r\n")[-1] == "Total;;1234,56;0,00;100"


def test_rotulo_de_periodo():
    from app.domains.reporting.exports import period_label

    assert period_label("2026-11") == "nov/2026"
    assert period_label("2026-01-05") == "05/01/2026"
    assert period_label("Total") == "Total"


def _audits(fmt):
    from app.core.database import SessionLocal
    from app.models import AuditEvent

    with SessionLocal() as db:
        return [a.after_json for a in db.query(AuditEvent).filter_by(entity_type="export", operation=fmt)]


def test_exportacao_xlsx_com_numeros_e_datas(client):
    import io
    from decimal import Decimal

    from openpyxl import load_workbook

    acc = _account(client)
    mercado = _cat(client, "Mercado")["id"]
    _tx(client, acc["id"], "EXPENSE", 123_456, mercado, description="Atacadão")
    _tx(client, acc["id"], "EXPENSE", 10_001, mercado, description="Feira")
    _tx(client, acc["id"], "INCOME", 500_000, description="Salário")

    r = client.get("/api/v1/exports/transactions.xlsx", params=_params())
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert r.headers["content-disposition"].endswith('.xlsx"')
    ws = load_workbook(io.BytesIO(r.content)).active
    assert ws.title == "Lançamentos"
    assert ws["A1"].value == "Lançamentos"
    assert ws["A4"].value == "Data" and ws["H4"].value == "Valor (R$)"
    values = sorted(Decimal(str(ws.cell(row=i, column=8).value)) for i in range(5, 8))
    assert values == [Decimal("-1234.56"), Decimal("-100.01"), Decimal("5000.00")]
    assert ws["A5"].value.date() == TODAY  # data de verdade, não texto
    assert ws["A5"].number_format == "DD/MM/YYYY"
    assert "R$" in ws["H5"].number_format
    assert ws.freeze_panes == "A5"

    # Total da planilha = total do relatório (mesma fonte).
    report = client.get("/api/v1/reports/categories", params=_params()).json()
    ws = load_workbook(io.BytesIO(client.get("/api/v1/exports/categories.xlsx", params=_params()).content)).active
    last = ws.max_row
    assert ws.cell(row=last, column=1).value == "Total"
    assert Decimal(str(ws.cell(row=last, column=3).value)) * 100 == report["total_cents"] == 133_457

    assert any(a["kind"] == "transactions" and a["format"] == "xlsx" and a["rows"] == 3 for a in _audits("xlsx"))


def test_exportacao_pdf_paginada(client):
    import io

    from pypdf import PdfReader

    acc = _account(client)
    for i in range(70):
        _tx(client, acc["id"], "EXPENSE", 123_456 + i, description=f"Compra {i:02d} — café & pão <teste>")

    r = client.get("/api/v1/exports/transactions.pdf", params=_params())
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    pdf = PdfReader(io.BytesIO(r.content))
    pages = len(pdf.pages)
    assert pages >= 2
    first = pdf.pages[0].extract_text()
    assert "Lançamentos" in first
    assert "-R$ 1.234,56" in first
    assert "café & pão <teste>" in first  # texto do usuário escapado corretamente
    assert f"Página 1 de {pages}" in first
    assert f"Página {pages} de {pages}" in pdf.pages[-1].extract_text()

    cash = PdfReader(io.BytesIO(client.get("/api/v1/exports/cash-flow.pdf", params=_params()).content))
    assert "Total" in "".join(p.extract_text() for p in cash.pages)
    assert any(a["format"] == "pdf" and a["rows"] == 70 for a in _audits("pdf"))


def test_todos_os_tipos_em_todos_os_formatos(client):
    # Banco vazio: tabelas sem linhas também precisam gerar arquivo válido.
    for fmt in ("csv", "xlsx", "pdf"):
        for kind in ("transactions", "card-purchases", "party-balances", "categories", "cash-flow", "cards",
                     "counterparties"):
            r = client.get(f"/api/v1/exports/{kind}.{fmt}", params=_params())
            assert r.status_code == 200, (kind, fmt, r.text)
    assert client.get("/api/v1/exports/transactions.docx").status_code == 422
    bad = {"from": D, "to": (TODAY - timedelta(days=1)).isoformat()}
    assert client.get("/api/v1/exports/transactions.pdf", params=bad).status_code == 422
    assert client.get("/api/v1/exports/bundle.xlsx", params=bad).status_code == 422


def test_pacote_completo_xlsx(client):
    import io

    from openpyxl import load_workbook

    acc = _account(client)
    _tx(client, acc["id"], "EXPENSE", 5_000, _cat(client, "Mercado")["id"])
    card = _card(client, acc["id"])
    _purchase(client, card["id"], 30_000, "iFood", n=2)

    r = client.get("/api/v1/exports/bundle.xlsx", params=_params())
    assert r.status_code == 200, r.text
    assert "finance-hub-completo-" in r.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Lançamentos", "Compras no cartão", "Categorias", "Fluxo de caixa", "Cartões",
                             "Terceiros - atrasos", "Terceiros - valores"]
    assert wb["Compras no cartão"]["C5"].value == "iFood"
    audit = next(a for a in _audits("xlsx") if a["kind"] == "bundle")
    assert len(audit["sheets"]) == 7


# ---------- backup ----------

def test_backup_e_restauracao_em_banco_vazio(client):
    from app.core.database import SessionLocal, engine
    from app.domains.backup import restore
    from app.models import Base

    acc = _account(client, "Principal", 200_000)
    _tx(client, acc["id"], "EXPENSE", 15_000, _cat(client, "Mercado")["id"])
    card = _card(client, acc["id"])
    _purchase(client, card["id"], 30_000, "iFood", n=2)
    p = client.post("/api/v1/people", json={"display_name": "Caio"}).json()
    client.post("/api/v1/party-balances", json={"person_id": p["id"], "origin_type": "LOAN_GIVEN",
                                                "description": "Empréstimo", "principal_cents": 5_000,
                                                "operation_date": D, "account_id": acc["id"]})
    client.post("/api/v1/goals", json={"title": "Reserva", "target_cents": 100_000})
    custom = client.post("/api/v1/categories", json={"name": "Pets extra", "kind": "EXPENSE"}).json()

    before_accounts = client.get("/api/v1/accounts").json()
    r = client.get("/api/v1/backup")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["format"] == "finance-hub-backup"
    assert data["counts"]["transactions"] >= 2

    # Banco com dados: restauração recusada.
    with SessionLocal() as db, pytest.raises(DomainError) as exc:
        restore(db, data)
    assert exc.value.code == "database_not_empty"

    # Esvazia tudo que não é semente da migração e restaura.
    names = ", ".join(t.name for t in Base.metadata.sorted_tables if t.name not in ("categories", "app_settings"))
    with engine.begin() as c:
        c.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    assert client.get("/api/v1/accounts").json() == []

    with SessionLocal() as db:
        counts = restore(db, data)
        db.commit()
    assert counts["transactions"] == data["counts"]["transactions"]

    after_accounts = client.get("/api/v1/accounts").json()
    assert [(a["id"], a["balance_cents"]) for a in after_accounts] == [
        (a["id"], a["balance_cents"]) for a in before_accounts
    ]
    assert any(c["id"] == custom["id"] for c in client.get("/api/v1/categories").json())
    assert client.get("/api/v1/party-balances").json()["summary"]["receivable_open_cents"] == 5_000
    assert len(client.get("/api/v1/goals").json()) == 1


def test_restauracao_recusa_revisao_diferente(client):
    from app.core.database import SessionLocal
    from app.domains.backup import restore

    data = client.get("/api/v1/backup").json()
    data["alembic_revision"] = "9999"
    with SessionLocal() as db, pytest.raises(DomainError) as exc:
        restore(db, data)
    assert exc.value.code == "backup_revision"


def test_relatorios_exigem_proprietario(anon_client):
    for path in ("/api/v1/reports/categories", "/api/v1/reports/cash-flow", "/api/v1/reports/cards",
                 "/api/v1/reports/counterparties", "/api/v1/exports/transactions.csv",
                 "/api/v1/exports/transactions.xlsx", "/api/v1/exports/cards.pdf", "/api/v1/exports/bundle.xlsx",
                 "/api/v1/backup"):
        assert anon_client.get(path).status_code == 401, path


def test_periodo_invalido(client):
    r = client.get("/api/v1/reports/cash-flow", params={"from": D, "to": (TODAY - timedelta(days=1)).isoformat()})
    assert r.status_code == 422
    assert client.get("/api/v1/reports/categories", params=_params(basis="X")).status_code == 422
    assert str(uuid.uuid4())  # sanidade do import
