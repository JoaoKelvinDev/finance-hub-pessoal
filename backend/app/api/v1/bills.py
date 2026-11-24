"""API endpoints para contas da casa (bills), recorrências e parcelas."""

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.api.v1.deps import DB, RequestId
from app.domains.bills.service import (
    archive_bill,
    auto_post_all_recurrences,
    cancel_bill_installment,
    count_bill_installments,
    count_bills,
    create_bill,
    create_bill_installment,
    create_installments_from_recurrence,
    create_recurrence,
    get_bill,
    get_bill_installment,
    get_overdue_bill_installments,
    get_recurrence,
    get_upcoming_bill_installments,
    list_bill_installments,
    list_bills,
    list_recurrences,
    pay_bill_installment,
    restore_bill,
    reverse_bill_installment_payment,
    skip_bill_installment,
    update_bill,
    update_bill_installment,
    update_recurrence,
)
from app.schemas.finance import (
    BillCreate,
    BillInstallmentCreate,
    BillInstallmentOut,
    BillInstallmentPage,
    BillInstallmentUpdate,
    BillOut,
    BillUpdate,
    RecurrenceCreate,
    RecurrenceOut,
    RecurrenceUpdate,
)

router = APIRouter(prefix="/bills", tags=["bills"])


# ---------- Bills ----------

@router.post("", response_model=BillOut, status_code=status.HTTP_201_CREATED)
def create_bill_endpoint(
    data: BillCreate,
    db: DB,
    request_id: RequestId,
):
    """Cria uma nova conta da casa."""
    bill = create_bill(db, data, request_id)
    db.commit()
    return BillOut.from_model(bill)


@router.get("", response_model=list[BillOut])
def list_bills_endpoint(
    include_archived: bool = Query(False),
    category: str | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DB = None,
):
    """Lista contas da casa."""
    bills = list_bills(db, include_archived, category, account_id, limit, offset)
    return [BillOut.from_model(b) for b in bills]


@router.get("/count")
def count_bills_endpoint(
    include_archived: bool = Query(False),
    category: str | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    db: DB = None,
):
    """Conta total de contas (para paginação)."""
    total = count_bills(db, include_archived, category, account_id)
    return {"total": total}


# ---------- Recorrências ----------

@router.post("/recurrences", response_model=RecurrenceOut, status_code=status.HTTP_201_CREATED)
def create_recurrence_endpoint(
    data: RecurrenceCreate,
    db: DB,
    request_id: RequestId,
):
    """Cria uma nova recorrência para uma conta."""
    try:
        recurrence = create_recurrence(db, data, request_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return RecurrenceOut.model_validate(recurrence)


@router.get("/recurrences", response_model=list[RecurrenceOut])
def list_recurrences_endpoint(
    bill_id: uuid.UUID | None = Query(None),
    status: Literal["ACTIVE", "PAUSED", "ENDED"] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DB = None,
):
    """Lista recorrências."""
    recurrences = list_recurrences(db, bill_id, status, limit, offset)
    return [RecurrenceOut.model_validate(r) for r in recurrences]


@router.get("/recurrences/{recurrence_id}", response_model=RecurrenceOut)
def get_recurrence_endpoint(
    recurrence_id: uuid.UUID,
    db: DB = None,
):
    """Busca uma recorrência por ID."""
    recurrence = get_recurrence(db, recurrence_id)
    if not recurrence:
        raise HTTPException(status_code=404, detail="Recorrência não encontrada")
    return RecurrenceOut.model_validate(recurrence)


@router.patch("/recurrences/{recurrence_id}", response_model=RecurrenceOut)
def update_recurrence_endpoint(
    recurrence_id: uuid.UUID,
    data: RecurrenceUpdate,
    db: DB = None,
):
    """Atualiza uma recorrência."""
    try:
        recurrence = update_recurrence(db, recurrence_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not recurrence:
        raise HTTPException(status_code=404, detail="Recorrência não encontrada")
    db.commit()
    return RecurrenceOut.model_validate(recurrence)


@router.post("/recurrences/{recurrence_id}/post-installments", response_model=list[BillInstallmentOut])
def post_installments_endpoint(
    recurrence_id: uuid.UUID,
    up_to_date: date | None = Query(None, description="Data limite para gerar parcelas (padrão: hoje)"),
    db: DB = None,
    request_id: RequestId = None,
):
    """Gera parcelas para uma recorrência até a data especificada."""
    recurrence = get_recurrence(db, recurrence_id)
    if not recurrence:
        raise HTTPException(status_code=404, detail="Recorrência não encontrada")

    try:
        installments = create_installments_from_recurrence(db, recurrence, up_to_date, request_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    return [BillInstallmentOut.from_model(i) for i in installments]


# ---------- Parcelas ----------

@router.post("/installments", response_model=BillInstallmentOut, status_code=status.HTTP_201_CREATED)
def create_installment_endpoint(
    data: BillInstallmentCreate,
    db: DB,
    request_id: RequestId,
):
    """Cria uma parcela manual."""
    try:
        installment = create_bill_installment(db, data, request_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return BillInstallmentOut.from_model(installment)


@router.get("/installments", response_model=BillInstallmentPage)
def list_installments_endpoint(
    bill_id: uuid.UUID | None = Query(None),
    recurrence_id: uuid.UUID | None = Query(None),
    status: Literal["PENDING", "POSTED", "PAID", "REVERSED", "CANCELLED", "SKIPPED"] | None = Query(None),
    due_from: date | None = Query(None),
    due_to: date | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DB = None,
):
    """Lista parcelas com filtros e paginação."""
    items = list_bill_installments(db, bill_id, recurrence_id, status, due_from, due_to, limit, offset)
    total = count_bill_installments(db, bill_id, recurrence_id, status, due_from, due_to)
    return BillInstallmentPage(
        items=[BillInstallmentOut.from_model(i) for i in items],
        total=total,
        page=(offset // limit) + 1,
        limit=limit,
    )


@router.get("/installments/upcoming", response_model=list[BillInstallmentOut])
def upcoming_installments_endpoint(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    db: DB = None,
):
    """Busca parcelas próximas do vencimento."""
    installments = get_upcoming_bill_installments(db, days, limit)
    return [BillInstallmentOut.from_model(i) for i in installments]


@router.get("/installments/overdue", response_model=list[BillInstallmentOut])
def overdue_installments_endpoint(
    limit: int = Query(50, ge=1, le=200),
    db: DB = None,
):
    """Busca parcelas vencidas e não pagas."""
    installments = get_overdue_bill_installments(db, limit)
    return [BillInstallmentOut.from_model(i) for i in installments]


@router.get("/installments/{installment_id}", response_model=BillInstallmentOut)
def get_installment_endpoint(
    installment_id: uuid.UUID,
    db: DB = None,
):
    """Busca uma parcela por ID."""
    installment = get_bill_installment(db, installment_id)
    if not installment:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")
    return BillInstallmentOut.from_model(installment)


@router.patch("/installments/{installment_id}", response_model=BillInstallmentOut)
def update_installment_endpoint(
    installment_id: uuid.UUID,
    data: BillInstallmentUpdate,
    db: DB = None,
):
    """Atualiza uma parcela."""
    installment = update_bill_installment(db, installment_id, data)
    if not installment:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")
    db.commit()
    return BillInstallmentOut.from_model(installment)


@router.post("/installments/{installment_id}/pay", response_model=BillInstallmentOut)
def pay_installment_endpoint(
    installment_id: uuid.UUID,
    account_id: uuid.UUID = Query(..., description="Conta de onde sai o pagamento"),
    paid_on: date = Query(..., description="Data do pagamento"),
    amount_cents: int | None = Query(None, gt=0, description="Valor (padrão: valor da parcela)"),
    idempotency_key: str | None = Query(None, max_length=100),
    db: DB = None,
    request_id: RequestId = None,
):
    """Paga uma parcela de conta da casa."""
    try:
        installment, _ = pay_bill_installment(
            db, installment_id, account_id, paid_on, amount_cents, idempotency_key, request_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return BillInstallmentOut.from_model(installment)


@router.post("/installments/{installment_id}/reverse", response_model=BillInstallmentOut)
def reverse_installment_endpoint(
    installment_id: uuid.UUID,
    idempotency_key: str | None = Query(None, max_length=100),
    db: DB = None,
    request_id: RequestId = None,
):
    """Estorna o pagamento de uma parcela."""
    try:
        installment, _ = reverse_bill_installment_payment(db, installment_id, idempotency_key, request_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return BillInstallmentOut.from_model(installment)


@router.post("/installments/{installment_id}/skip", response_model=BillInstallmentOut)
def skip_installment_endpoint(
    installment_id: uuid.UUID,
    idempotency_key: str | None = Query(None, max_length=100),
    db: DB = None,
):
    """Marca uma parcela como SKIPPED (pagamento pulado)."""
    try:
        installment = skip_bill_installment(db, installment_id, idempotency_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return BillInstallmentOut.from_model(installment)


@router.post("/installments/{installment_id}/cancel", response_model=BillInstallmentOut)
def cancel_installment_endpoint(
    installment_id: uuid.UUID,
    idempotency_key: str | None = Query(None, max_length=100),
    db: DB = None,
):
    """Cancela uma parcela."""
    try:
        installment = cancel_bill_installment(db, installment_id, idempotency_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return BillInstallmentOut.from_model(installment)


# ---------- Bills por ID (rotas específicas DEPOIS das rotas /recurrences e /installments) ----------

@router.get("/{bill_id}", response_model=BillOut)
def get_bill_endpoint(
    bill_id: uuid.UUID,
    db: DB = None,
):
    """Busca uma conta por ID."""
    bill = get_bill(db, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    return BillOut.from_model(bill)


@router.patch("/{bill_id}", response_model=BillOut)
def update_bill_endpoint(
    bill_id: uuid.UUID,
    data: BillUpdate,
    db: DB = None,
):
    """Atualiza uma conta."""
    bill = update_bill(db, bill_id, data)
    if not bill:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    db.commit()
    return BillOut.from_model(bill)


@router.post("/{bill_id}/archive", response_model=BillOut)
def archive_bill_endpoint(
    bill_id: uuid.UUID,
    db: DB = None,
):
    """Arquiva uma conta (soft delete)."""
    bill = archive_bill(db, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Conta não encontrada ou já arquivada")
    db.commit()
    return BillOut.from_model(bill)


@router.post("/{bill_id}/restore", response_model=BillOut)
def restore_bill_endpoint(
    bill_id: uuid.UUID,
    db: DB = None,
):
    """Restaura uma conta arquivada."""
    bill = restore_bill(db, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Conta não encontrada ou não está arquivada")
    db.commit()
    return BillOut.from_model(bill)


# ---------- Auto-post global ----------

@router.post("/auto-post", response_model=list[BillInstallmentOut])
def auto_post_endpoint(
    up_to_date: date | None = Query(None, description="Data limite (padrão: hoje)"),
    db: DB = None,
    request_id: RequestId = None,
):
    """Processa todas as recorrências ativas com auto_post=True."""
    installments = auto_post_all_recurrences(db, up_to_date, request_id)
    db.commit()
    return [BillInstallmentOut.from_model(i) for i in installments]