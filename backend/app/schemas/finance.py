import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.common import MAX_CENTS, ORM, Color, IdemKey, Name

AccountType = Literal["CHECKING", "SAVINGS", "CASH", "DIGITAL_WALLET", "OTHER"]
TxKind = Literal["INCOME", "EXPENSE", "TRANSFER_IN", "TRANSFER_OUT", "ADJUSTMENT"]
TxStatus = Literal["PLANNED", "POSTED", "CANCELLED"]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


# ---------- Contas ----------
class AccountCreate(BaseModel):
    name: Name
    type: AccountType
    institution: Name | None = None
    color: Color = "#3B82F6"
    opening_balance_cents: int = Field(0, ge=-MAX_CENTS, le=MAX_CENTS)
    opening_date: date
    notes: Notes | None = None


class AccountUpdate(BaseModel):
    name: Name | None = None
    institution: Name | None = None
    color: Color | None = None
    notes: Notes | None = None
    archived: bool | None = None


class AccountOut(ORM):
    id: uuid.UUID
    name: str
    type: AccountType
    institution: str | None
    color: str
    currency: str
    opening_balance_cents: int
    opening_date: date
    notes: str | None
    archived_at: datetime | None
    balance_cents: int = 0
    planned_balance_cents: int = 0


# ---------- Categorias ----------
class CategoryCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    kind: Literal["INCOME", "EXPENSE"]
    parent_id: uuid.UUID | None = None
    color: Color = "#64748B"


class CategoryOut(ORM):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    kind: str
    color: str
    archived_at: datetime | None


# ---------- Pessoas (contatos, não usuários) ----------
class PersonCreate(BaseModel):
    display_name: Name
    contact: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    notes: Notes | None = None


class PersonUpdate(BaseModel):
    display_name: Name | None = None
    contact: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    notes: Notes | None = None
    archived: bool | None = None


class PersonOut(ORM):
    id: uuid.UUID
    display_name: str
    contact: str | None
    notes: str | None
    archived_at: datetime | None


# ---------- Lançamentos ----------
class TransactionCreate(BaseModel):
    account_id: uuid.UUID
    kind: Literal["INCOME", "EXPENSE", "ADJUSTMENT"]
    amount_cents: int = Field(..., ge=-MAX_CENTS, le=MAX_CENTS, description="Positivo para receita/despesa; assinado para ajuste")
    status: Literal["PLANNED", "POSTED"] = "POSTED"
    effective_date: date
    description: Description
    category_id: uuid.UUID | None = None
    counterparty_id: uuid.UUID | None = None
    notes: Notes | None = None
    idempotency_key: IdemKey | None = None


class TransactionCancel(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]


class TransactionPost(BaseModel):
    effective_date: date | None = None


class Ref(ORM):
    id: uuid.UUID
    name: str | None = None


class TransactionOut(ORM):
    id: uuid.UUID
    account_id: uuid.UUID
    account_name: str
    amount_cents: int
    kind: TxKind
    status: TxStatus
    effective_date: date
    description: str
    category_id: uuid.UUID | None
    category_name: str | None
    category_color: str | None
    counterparty_id: uuid.UUID | None
    counterparty_name: str | None
    transfer_group_id: uuid.UUID | None
    notes: str | None
    cancel_reason: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, t) -> "TransactionOut":
        return cls(
            id=t.id,
            account_id=t.account_id,
            account_name=t.account.name,
            amount_cents=t.amount_cents,
            kind=t.kind,
            status=t.status,
            effective_date=t.effective_date,
            description=t.description,
            category_id=t.category_id,
            category_name=t.category.name if t.category else None,
            category_color=t.category.color if t.category else None,
            counterparty_id=t.counterparty_id,
            counterparty_name=t.counterparty.display_name if t.counterparty else None,
            transfer_group_id=t.transfer_group_id,
            notes=t.notes,
            cancel_reason=t.cancel_reason,
            created_at=t.created_at,
        )


class TransactionTotals(BaseModel):
    income_cents: int
    expense_cents: int
    net_cents: int
    count: int


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    totals: TransactionTotals
    total: int
    page: int
    limit: int


# ---------- Transferências ----------
class TransferCreate(BaseModel):
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount_cents: int = Field(..., gt=0, le=MAX_CENTS)
    effective_date: date
    description: Description = "Transferência entre contas"
    idempotency_key: IdemKey | None = None

    @model_validator(mode="after")
    def _distinct(self):
        if self.from_account_id == self.to_account_id:
            raise ValueError("Origem e destino devem ser contas diferentes.")
        return self


class TransferOut(BaseModel):
    transfer_group_id: uuid.UUID
    out_leg: TransactionOut
    in_leg: TransactionOut


class LedgerOut(BaseModel):
    account: AccountOut
    items: list[TransactionOut]
    total: int
    page: int
    limit: int


# ---------- Configurações ----------
class SettingsOut(ORM):
    locale: str
    timezone: str
    currency: str
    theme: str


class SettingsUpdate(BaseModel):
    theme: Literal["light", "dark", "system"] | None = None
    timezone: Annotated[str, StringConstraints(max_length=64)] | None = None
