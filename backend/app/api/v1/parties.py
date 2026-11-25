"""Valores com terceiros (contatos sem login): empréstimos, adiantamentos, dívidas e acertos."""

import uuid
from typing import Literal

from fastapi import APIRouter, Query, Response, status

from app.api.v1.deps import DB, RequestId
from app.core.errors import NotFound
from app.domains.parties import service
from app.models import PartyAdjustment, PartySettlement, Person
from app.schemas.parties import (
    AdjustmentCreate,
    PartyBalanceCreate,
    PartyBalanceDetail,
    PartyBalancePage,
    PersonPosition,
    ReasonIn,
    SettlementCreate,
)

router = APIRouter(tags=["Terceiros"])


@router.get("/party-balances", response_model=PartyBalancePage)
def list_party_balances(
    db: DB,
    person_id: uuid.UUID | None = None,
    direction: Literal["RECEIVABLE", "PAYABLE"] | None = None,
    include_cancelled: bool = Query(False),
):
    items = service.list_balances(db, person_id, direction, include_cancelled)
    return PartyBalancePage(items=items, summary=service.summarize(items))


@router.post("/party-balances", response_model=PartyBalanceDetail, status_code=status.HTTP_201_CREATED)
def create_party_balance(data: PartyBalanceCreate, db: DB, rid: RequestId, response: Response):
    balance_id, created = service.create_balance(db, data, rid)
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return service.balance_detail(db, balance_id)


@router.get("/party-balances/{balance_id}", response_model=PartyBalanceDetail)
def get_party_balance(balance_id: uuid.UUID, db: DB):
    return service.balance_detail(db, balance_id)


@router.post(
    "/party-balances/{balance_id}/settlements", response_model=PartyBalanceDetail, status_code=status.HTTP_201_CREATED
)
def settle_party_balance(balance_id: uuid.UUID, data: SettlementCreate, db: DB, rid: RequestId, response: Response):
    settlement_id, created = service.settle(db, balance_id, data, rid)
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    s = db.get(PartySettlement, settlement_id)
    return service.balance_detail(db, s.party_balance_id)


@router.post("/party-balances/settlements/{settlement_id}/reverse", response_model=PartyBalanceDetail)
def reverse_party_settlement(settlement_id: uuid.UUID, data: ReasonIn, db: DB, rid: RequestId):
    s = service.reverse_settlement(db, settlement_id, data.reason, rid)
    db.commit()
    return service.balance_detail(db, s.party_balance_id)


@router.post(
    "/party-balances/{balance_id}/adjustments", response_model=PartyBalanceDetail, status_code=status.HTTP_201_CREATED
)
def adjust_party_balance(balance_id: uuid.UUID, data: AdjustmentCreate, db: DB, rid: RequestId, response: Response):
    adjustment_id, created = service.adjust(db, balance_id, data, rid)
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    a = db.get(PartyAdjustment, adjustment_id)
    return service.balance_detail(db, a.party_balance_id)


@router.post("/party-balances/{balance_id}/cancel", response_model=PartyBalanceDetail)
def cancel_party_balance(balance_id: uuid.UUID, data: ReasonIn, db: DB, rid: RequestId):
    service.cancel_balance(db, balance_id, data.reason, rid)
    db.commit()
    return service.balance_detail(db, balance_id)


@router.get("/people/{person_id}/position", response_model=PersonPosition, tags=["Pessoas"])
def person_position(person_id: uuid.UUID, db: DB):
    person = db.get(Person, person_id)
    if person is None:
        raise NotFound("Pessoa")
    details = service.person_details(db, person_id)
    summary = service.summarize(details)
    return PersonPosition(
        person_id=person.id,
        person_name=person.display_name,
        contact=person.contact,
        archived=person.archived_at is not None,
        summary=summary,
        net_cents=summary.receivable_open_cents - summary.payable_open_cents,
        balances=details,
    )
