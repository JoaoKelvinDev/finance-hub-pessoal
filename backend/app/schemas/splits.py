import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import MAX_CENTS, IdemKey
from app.schemas.parties import PartyStatus, Reason

SplitMethod = Literal["EQUAL", "FIXED", "PERCENT"]


class SplitParticipantIn(BaseModel):
    person_id: uuid.UUID
    amount_cents: int | None = Field(None, gt=0, le=MAX_CENTS)
    # Percentual em pontos-base: 50% = 5000.
    percent_bp: int | None = Field(None, gt=0, le=10_000)


class SplitCreate(BaseModel):
    method: SplitMethod
    include_owner: bool = True
    participants: list[SplitParticipantIn] = Field(..., min_length=1, max_length=20)
    due_date: date | None = None
    idempotency_key: IdemKey | None = None

    @model_validator(mode="after")
    def _unique(self):
        ids = [p.person_id for p in self.participants]
        if len(ids) != len(set(ids)):
            raise ValueError("Cada pessoa só pode aparecer uma vez no rateio.")
        return self


class SplitCancel(BaseModel):
    reason: Reason


class SplitPartOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    person_name: str
    share_cents: int
    percent_bp: int | None
    party_balance_id: uuid.UUID
    received_cents: int
    open_cents: int
    status: PartyStatus


class SplitOut(BaseModel):
    id: uuid.UUID
    bill_installment_id: uuid.UUID
    bill_name: str
    due_date: date
    method: SplitMethod
    include_owner: bool
    total_cents: int
    owner_share_cents: int
    others_cents: int
    received_cents: int
    # Custo líquido pessoal após reembolsos confirmados (despesa bruta não muda).
    net_cost_cents: int
    cancelled_at: datetime | None
    cancel_reason: str | None
    created_at: datetime
    parts: list[SplitPartOut]
