"""Relatórios, exportação CSV e backup."""

import json
import uuid
from datetime import date

from fastapi import APIRouter, Path, Query, Response

from app.api.v1.deps import DB, RequestId
from app.core.errors import DomainError
from app.domains import backup
from app.domains.reporting import exports, reports
from app.domains.support import audit, today_local
from app.schemas.reports import CardReport, CashFlowReport, CategoryReport, CounterpartyReport

router = APIRouter(tags=["Relatórios"])

BASIS = ("CASH", "COMPETENCE")


def _period(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = today_local()
    return date_from or today.replace(day=1), date_to or today


def _basis(basis: str) -> str:
    if basis not in BASIS:
        raise DomainError("basis_invalid", "Use CASH (caixa) ou COMPETENCE (competência).")
    return basis


@router.get("/reports/categories", response_model=CategoryReport)
def categories(
    db: DB,
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    basis: str = Query("CASH"),
):
    """Gastos por categoria (com subcategorias) e comparação com o período anterior de mesmo tamanho."""
    start, end = _period(date_from, date_to)
    return reports.category_report(db, start, end, _basis(basis))


@router.get("/reports/cash-flow", response_model=CashFlowReport)
def cash_flow(db: DB, date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to")):
    """Receitas e despesas efetivadas por dia (até 62 dias) ou por mês."""
    start, end = _period(date_from, date_to)
    return reports.cash_flow_report(db, start, end)


@router.get("/reports/cards", response_model=CardReport)
def cards(db: DB, date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to")):
    """Por cartão: compras e pagamentos no período, dívida em aberto e parcelas futuras."""
    start, end = _period(date_from, date_to)
    return reports.card_report(db, start, end)


@router.get("/reports/counterparties", response_model=CounterpartyReport)
def counterparties(
    db: DB, date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to")
):
    """Posição por pessoa e aging dos valores a receber (0–30, 31–60, 61–90, 90+ dias de atraso)."""
    start, end = _period(date_from, date_to)
    return reports.counterparty_report(db, start, end)


@router.get("/exports/{kind}.csv")
def export_csv(
    db: DB,
    rid: RequestId,
    kind: exports.ExportKind = Path(...),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    basis: str = Query("CASH"),
):
    """CSV para Excel pt-BR (";", vírgula decimal, UTF-8 com BOM). A exportação fica na auditoria."""
    start, end = _period(date_from, date_to)
    name, content, _rows = exports.export_csv(db, kind, start, end, _basis(basis), rid)
    db.commit()
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )


@router.get("/backup", tags=["Backup"])
def download_backup(db: DB, rid: RequestId):
    """Backup completo em JSON (todas as tabelas). Restauração só pela linha de comando, em banco vazio."""
    data = backup.dump(db)
    audit(db, "backup", uuid.uuid4(), "download", None, {"counts": data["counts"]}, rid)
    db.commit()
    stamp = data["exported_at"][:19].replace(":", "").replace("-", "")
    return Response(
        json.dumps(data, ensure_ascii=False).encode("utf-8"),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="finance-hub-backup-{stamp}.json"',
            "Cache-Control": "no-store",
        },
    )
