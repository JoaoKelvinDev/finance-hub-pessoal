import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.common import MAX_CENTS, IdemKey

PartyDirection = Literal["RECEIVABLE", "PAYABLE"]
PartyOrigin = Literal["LOAN_GIVEN", "LOAN_TAKEN", "ADVANCE", "OWED_TO_ME", "I_OWE"]
PartyStatus = Literal["OPEN", "PARTIALLY_SETTLED", "SETTLED", "OVERDUE", "CANCELLED"]
AdjustmentKind = Literal["CHARGE", "DISCOUNT"]

# Tipos que movimentam caixa na criação (exigem conta).
CASH_ORIGINS = ("LOAN_GIVEN", "LOAN_TAKEN", "ADVANCE")
DIRECTION_BY_ORIGIN: dict[str, str] = {
    "LOAN_GIVEN": "RECEIVABLE",
    "ADVANCE": "RECEIVABLE",
    "OWED_TO_ME": "RECEIVABLE",
    "LOAN_TAKEN": "PAYABLE",
    "I_OWE": "PAYABLE",
}

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class PartyBalanceCreate(BaseModel):
    person_id: uuid.UUID
    origin_type: PartyOrigin
    description: Description
    principal_cents: int = Field(..., gt=0, le=MAX_CENTS)
    operation_date: date
    due_date: date | None = None
    account_id: uuid.UUID | None = None
    notes: Notes | None = None
    idempotency_key: IdemKey | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.origin_type in CASH_ORIGINS and self.account_id is None:
            raise ValueError("Informe a conta de onde o dinheiro saiu ou entrou.")
        if self.origin_type not in CASH_ORIGINS and self.account_id is not None:
            raise ValueError("Este tipo não movimenta caixa; não informe conta.")
        if self.due_date and self.due_date < self.operation_date:
            raise ValueError("O vencimento não pode ser anterior à data da operação.")
        return self


class SettlementCreate(BaseModel):
    account_id: uuid.UUID
    amount_cents: int = Field(..., gt=0, le=MAX_CENTS)
    settled_on: date
    notes: Notes | None = None
    idempotency_key: IdemKey | None = None


class AdjustmentCreate(BaseModel):
    kind: AdjustmentKind
    amount_cents: int = Field(..., gt=0, le=MAX_CENTS)
    applied_on: date
    reason: Reason
    idempotency_key: IdemKey | None = None


class ReasonIn(BaseModel):
    reason: Reason


class SettlementOut(BaseModel):
    id: uuid.UUID
    party_balance_id: uuid.UUID
    transaction_id: uuid.UUID
    account_id: uuid.UUID
    account_name: str
    amount_cents: int
    settled_on: date
    notes: str | None
    reversed_at: datetime | None
    reverse_reason: str | None
    created_at: datetime


class AdjustmentOut(BaseModel):
    id: uuid.UUID
    kind: AdjustmentKind
    amount_cents: int
    applied_on: date
    reason: str
    created_at: datetime


class PartyBalanceOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    person_name: str
    direction: PartyDirection
    origin_type: PartyOrigin
    description: str
    principal_cents: int
    charges_cents: int
    discounts_cents: int
    settled_cents: int
    open_cents: int
    operation_date: date
    due_date: date | None
    account_id: uuid.UUID | None
    account_name: str | None
    origin_transaction_id: uuid.UUID | None
    status: PartyStatus
    notes: str | None
    cancel_reason: str | None
    created_at: datetime


class PartyBalanceDetail(PartyBalanceOut):
    settlements: list[SettlementOut]
    adjustments: list[AdjustmentOut]


class PartySummary(BaseModel):
    receivable_open_cents: int
    payable_open_cents: int
    receivable_overdue_cents: int
    payable_overdue_cents: int
    open_count: int


class PartyBalancePage(BaseModel):
    items: list[PartyBalanceOut]
    summary: PartySummary


class PersonPosition(BaseModel):
    person_id: uuid.UUID
    person_name: str
    contact: str | None
    archived: bool
    summary: PartySummary
    # Apenas informativo: dívidas opostas NÃO são compensadas automaticamente.
    net_cents: int
    balances: list[PartyBalanceDetail]
