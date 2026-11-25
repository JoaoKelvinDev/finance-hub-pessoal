import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import func, select

from app.api.v1.deps import DB, RequestId
from app.core.errors import NotFound
from app.domains.cards import service
from app.models import CardInstallment, CardPurchase, CardStatement, CreditCard, StatementPayment
from app.schemas.finance import (
    CardCreate,
    CardOut,
    CardUpdate,
    InstallmentOut,
    PurchaseCreate,
    PurchaseOut,
    StatementOut,
    StatementPaymentCreate,
    StatementPaymentOut,
)

router = APIRouter(prefix="/cards", tags=["Cartões"])

CARD_FIELDS = (
    "name", "bank", "nickname", "last_four", "brand", "type", "limit_cents",
    "closing_day", "due_day", "due_month_offset", "purchase_boundary_policy",
    "default_payment_account_id", "color", "archived_at",
)


def _card_out(card: CreditCard, used: int, available: int) -> CardOut:
    return CardOut.model_validate(card).model_copy(
        update={"used_limit_cents": used, "available_limit_cents": available}
    )


def _get_card(db: DB, card_id: uuid.UUID) -> CreditCard:
    card = db.get(CreditCard, card_id)
    if card is None:
        raise NotFound("Cartão")
    return card


@router.get("", response_model=list[CardOut])
def list_cards(db: DB, include_archived: bool = False):
    cards = service.list_cards(db, include_archived)
    out = []
    for c in cards:
        _, used, available = service.get_card_with_limits(db, c.id)
        out.append(_card_out(c, used, available))
    return out


@router.post("", response_model=CardOut, status_code=status.HTTP_201_CREATED)
def create_card(data: CardCreate, db: DB, rid: RequestId):
    card = service.create_card(db, data, rid)
    db.commit()
    _, used, available = service.get_card_with_limits(db, card.id)
    return _card_out(card, used, available)


@router.patch("/{card_id}", response_model=CardOut)
def update_card(card_id: uuid.UUID, data: CardUpdate, db: DB, rid: RequestId):
    card = service.update_card(db, card_id, data, rid)
    db.commit()
    _, used, available = service.get_card_with_limits(db, card.id)
    return _card_out(card, used, available)


@router.get("/{card_id}", response_model=CardOut)
def get_card(card_id: uuid.UUID, db: DB):
    card, used, available = service.get_card_with_limits(db, card_id)
    return _card_out(card, used, available)


# ---------- Faturas ----------
@router.get("/{card_id}/statements", response_model=list[StatementOut])
def list_statements(
    card_id: uuid.UUID,
    db: DB,
    status: Literal["OPEN", "CLOSED", "PARTIALLY_PAID", "PAID", "OVERDUE", "CANCELLED"] | None = None,
):
    _get_card(db, card_id)
    stmts = service.list_statements(db, card_id, status)
    out = []
    for s in stmts:
        total = db.scalar(
            select(func.coalesce(func.sum(CardInstallment.amount_cents), 0))
            .where(
                CardInstallment.statement_id == s.id,
                CardInstallment.status.notin_(("REVERSED", "CANCELLED")),
            )
        ) or 0
        out.append(StatementOut.model_validate(s).model_copy(update={"total_cents": int(total)}))
    return out


@router.get("/statements/{statement_id}", response_model=StatementOut)
def get_statement(statement_id: uuid.UUID, db: DB):
    stmt = service.get_statement_detail(db, statement_id)
    total = db.scalar(
        select(func.coalesce(func.sum(CardInstallment.amount_cents), 0))
        .where(
            CardInstallment.statement_id == stmt.id,
            CardInstallment.status.notin_(("REVERSED", "CANCELLED")),
        )
    ) or 0
    return StatementOut.model_validate(stmt).model_copy(update={"total_cents": int(total)})


@router.get("/statements/{statement_id}/installments", response_model=list[InstallmentOut])
def list_statement_installments(statement_id: uuid.UUID, db: DB):
    _get_statement = db.get(CardStatement, statement_id)
    if _get_statement is None:
        raise NotFound("Fatura")
    insts = db.scalars(
        select(CardInstallment)
        .where(CardInstallment.statement_id == statement_id)
        .order_by(CardInstallment.installment_number)
    ).all()
    return [InstallmentOut.model_validate(i) for i in insts]


# ---------- Compras ----------
@router.post("/purchases", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
def create_purchase(data: PurchaseCreate, db: DB, rid: RequestId, response: Response):
    purchase_id, created = service.create_purchase(db, data, rid)
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    purchase = _get_purchase(db, purchase_id)
    return PurchaseOut.from_model(purchase)


@router.get("/{card_id}/purchases", response_model=list[PurchaseOut])
def list_purchases(
    card_id: uuid.UUID,
    db: DB,
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    status: Literal["ACTIVE", "REVERSED", "CANCELLED"] | None = None,
):
    _get_card(db, card_id)
    purchases = service.list_purchases(db, card_id, date_from, date_to, status)
    return [PurchaseOut.from_model(p) for p in purchases]


def _get_purchase(db: DB, purchase_id: uuid.UUID) -> CardPurchase:
    p = db.get(CardPurchase, purchase_id)
    if p is None:
        raise NotFound("Compra")
    return p


# ---------- Pagamentos de fatura ----------
@router.post("/statements/{statement_id}/payments", response_model=StatementPaymentOut, status_code=status.HTTP_201_CREATED)
def pay_statement(statement_id: uuid.UUID, data: StatementPaymentCreate, db: DB, rid: RequestId, response: Response):
    if data.statement_id != statement_id:
        raise NotFound("Fatura")
    payment_id, created = service.pay_statement(db, data, rid)
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    payment = db.get(StatementPayment, payment_id)
    return StatementPaymentOut.model_validate(payment)


# ---------- Próximas parcelas ----------
@router.get("/{card_id}/upcoming", response_model=list[InstallmentOut])
def upcoming_installments(card_id: uuid.UUID, db: DB, limit: int = Query(20, ge=1, le=100)):
    _get_card(db, card_id)
    insts = service.get_upcoming_installments(db, card_id, limit)
    return [InstallmentOut.model_validate(i) for i in insts]