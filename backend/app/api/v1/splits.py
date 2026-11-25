"""Estimado × real e rateio de parcelas de contas da casa."""

import uuid

from fastapi import APIRouter, Response, status

from app.api.v1.deps import DB, RequestId
from app.domains.bills.service import confirm_installment_amount
from app.domains.splits import service
from app.models import ExpenseSplit
from app.schemas.finance import BillInstallmentOut, ConfirmAmountIn
from app.schemas.splits import SplitCancel, SplitCreate, SplitOut

router = APIRouter(prefix="/bills", tags=["Contas da casa"])


@router.post("/installments/{installment_id}/confirm-amount", response_model=BillInstallmentOut)
def confirm_amount(installment_id: uuid.UUID, data: ConfirmAmountIn, db: DB, rid: RequestId):
    """Substitui a estimativa pelo valor real (o estimado fica no histórico)."""
    inst = confirm_installment_amount(db, installment_id, data.amount_cents, rid)
    db.commit()
    return BillInstallmentOut.from_model(inst)


@router.post("/installments/{installment_id}/split", response_model=SplitOut, status_code=status.HTTP_201_CREATED)
def create_split(installment_id: uuid.UUID, data: SplitCreate, db: DB, rid: RequestId, response: Response):
    split_id, created = service.create_split(db, installment_id, data, rid)
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return service.split_out(db, db.get(ExpenseSplit, split_id))


@router.get("/installments/{installment_id}/split", response_model=SplitOut)
def get_split(installment_id: uuid.UUID, db: DB):
    return service.split_out(db, service.active_split_for(db, installment_id))


@router.post("/splits/{split_id}/cancel", response_model=SplitOut)
def cancel_split(split_id: uuid.UUID, data: SplitCancel, db: DB, rid: RequestId):
    split = service.cancel_split(db, split_id, data.reason, rid)
    db.commit()
    return service.split_out(db, split)
