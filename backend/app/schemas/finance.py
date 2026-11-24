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

CardType = Literal["CREDIT", "DEBIT", "PREPAID"]
CardBrand = Literal["VISA", "MASTERCARD", "ELO", "AMEX", "HIPERCARD", "OTHER"]
StatementStatus = Literal["OPEN", "CLOSED", "PARTIALLY_PAID", "PAID", "OVERDUE", "CANCELLED"]
PurchaseStatus = Literal["ACTIVE", "REVERSED", "CANCELLED"]
InstallmentStatus = Literal["PENDING", "POSTED", "PAID", "REVERSED", "CANCELLED"]
PurchaseBoundaryPolicy = Literal["INCLUSIVE", "EXCLUSIVE"]


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


# ---------- Cartões ----------
class CardCreate(BaseModel):
    name: Name
    bank: Name | None = None
    nickname: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None = None
    last_four: Annotated[str, StringConstraints(pattern=r"^[0-9]{4}$")] | None = None
    brand: CardBrand | None = None
    type: CardType = "CREDIT"
    limit_cents: int = Field(..., gt=0, le=MAX_CENTS)
    closing_day: int = Field(..., ge=1, le=28)
    due_day: int = Field(..., ge=1, le=28)
    due_month_offset: Literal[0, 1] = 1
    purchase_boundary_policy: PurchaseBoundaryPolicy = "EXCLUSIVE"
    default_payment_account_id: uuid.UUID | None = None
    color: Color = "#3B82F6"


class CardUpdate(BaseModel):
    name: Name | None = None
    bank: Name | None = None
    nickname: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None = None
    last_four: Annotated[str, StringConstraints(pattern=r"^[0-9]{4}$")] | None = None
    brand: CardBrand | None = None
    limit_cents: int | None = Field(None, gt=0, le=MAX_CENTS)
    closing_day: int | None = Field(None, ge=1, le=28)
    due_day: int | None = Field(None, ge=1, le=28)
    due_month_offset: Literal[0, 1] | None = None
    purchase_boundary_policy: PurchaseBoundaryPolicy | None = None
    default_payment_account_id: uuid.UUID | None = None
    color: Color | None = None
    archived: bool | None = None


class CardOut(ORM):
    id: uuid.UUID
    name: str
    bank: str | None
    nickname: str | None
    last_four: str | None
    brand: str | None
    type: CardType
    limit_cents: int
    closing_day: int
    due_day: int
    due_month_offset: int
    purchase_boundary_policy: PurchaseBoundaryPolicy
    default_payment_account_id: uuid.UUID | None
    color: str
    archived_at: datetime | None
    used_limit_cents: int = 0
    available_limit_cents: int = 0


# ---------- Faturas ----------
class StatementOut(ORM):
    id: uuid.UUID
    card_id: uuid.UUID
    cycle_start_date: date
    cycle_end_exclusive: date
    due_date: date
    status: StatementStatus
    total_cents: int = 0
    paid_cents: int = 0
    closed_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None


# ---------- Compras ----------
class PurchaseCreate(BaseModel):
    card_id: uuid.UUID
    description: Description
    merchant: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    purchased_on: date
    total_cents: int = Field(..., gt=0, le=MAX_CENTS)
    installments_count: int = Field(1, ge=1, le=99)
    category_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    notes: Notes | None = None
    idempotency_key: IdemKey | None = None


class PurchaseOut(ORM):
    id: uuid.UUID
    card_id: uuid.UUID
    purchased_on: date
    description: str
    merchant: str | None
    total_cents: int
    installments_count: int
    category_id: uuid.UUID | None
    category_name: str | None
    category_color: str | None
    person_id: uuid.UUID | None
    person_name: str | None
    status: PurchaseStatus
    notes: str | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, p) -> "PurchaseOut":
        return cls(
            id=p.id,
            card_id=p.card_id,
            purchased_on=p.purchased_on,
            description=p.description,
            merchant=p.merchant,
            total_cents=p.total_cents,
            installments_count=p.installments_count,
            category_id=p.category_id,
            category_name=p.category.name if p.category else None,
            category_color=p.category.color if p.category else None,
            person_id=p.person_id,
            person_name=p.person.display_name if p.person else None,
            status=p.status,
            notes=p.notes,
            cancelled_at=p.cancelled_at,
            cancel_reason=p.cancel_reason,
            created_at=p.created_at,
        )


# ---------- Parcelas ----------
class InstallmentOut(ORM):
    id: uuid.UUID
    purchase_id: uuid.UUID
    statement_id: uuid.UUID
    installment_number: int
    amount_cents: int
    status: InstallmentStatus
    paid_at: datetime | None
    reversed_at: datetime | None
    created_at: datetime


# ---------- Pagamentos de fatura ----------
class StatementPaymentCreate(BaseModel):
    statement_id: uuid.UUID
    account_id: uuid.UUID
    amount_cents: int = Field(..., gt=0, le=MAX_CENTS)
    paid_on: date
    idempotency_key: IdemKey


class StatementPaymentOut(ORM):
    id: uuid.UUID
    statement_id: uuid.UUID
    transaction_id: uuid.UUID
    amount_cents: int
    paid_on: date
    created_at: datetime


# ---------- Contas da casa (bills) ----------
BillCategory = Literal["WATER", "ELECTRICITY", "GAS", "INTERNET", "PHONE", "RENT", "CONDOMINIUM", "INSURANCE", "SUBSCRIPTION", "OTHER"]
RecurrenceFrequency = Literal["MONTHLY", "BIMONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL", "CUSTOM"]
RecurrenceStatus = Literal["ACTIVE", "PAUSED", "ENDED"]
BillInstallmentStatus = Literal["PENDING", "POSTED", "PAID", "REVERSED", "CANCELLED", "SKIPPED"]


class BillCreate(BaseModel):
    name: Name
    category: BillCategory
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    account_id: uuid.UUID
    default_amount_cents: int = Field(..., gt=0, le=MAX_CENTS)
    color: Color = "#EF4444"


class BillUpdate(BaseModel):
    name: Name | None = None
    category: BillCategory | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    default_amount_cents: int | None = Field(None, gt=0, le=MAX_CENTS)
    color: Color | None = None
    archived: bool | None = None


class BillOut(ORM):
    id: uuid.UUID
    name: str
    category: str
    description: str | None
    account_id: uuid.UUID
    account_name: str | None = None
    default_amount_cents: int
    color: str
    archived_at: datetime | None
    created_at: datetime

    @classmethod
    def from_model(cls, b) -> "BillOut":
        return cls(
            id=b.id,
            name=b.name,
            category=b.category,
            description=b.description,
            account_id=b.account_id,
            account_name=b.account.name if b.account else None,
            default_amount_cents=b.default_amount_cents,
            color=b.color,
            archived_at=b.archived_at,
            created_at=b.created_at,
        )


class RecurrenceCreate(BaseModel):
    bill_id: uuid.UUID
    frequency: RecurrenceFrequency
    day_of_month: int | None = Field(None, ge=1, le=31)
    start_date: date
    end_date: date | None = None
    custom_months_interval: int | None = Field(None, gt=0)
    auto_post: bool = True


class RecurrenceUpdate(BaseModel):
    frequency: RecurrenceFrequency | None = None
    day_of_month: int | None = Field(None, ge=1, le=31)
    end_date: date | None = None
    custom_months_interval: int | None = Field(None, gt=0)
    auto_post: bool | None = None
    status: RecurrenceStatus | None = None


class RecurrenceOut(ORM):
    id: uuid.UUID
    bill_id: uuid.UUID
    frequency: str
    day_of_month: int | None
    start_date: date
    end_date: date | None
    custom_months_interval: int | None
    auto_post: bool
    status: RecurrenceStatus
    created_at: datetime


class BillInstallmentCreate(BaseModel):
    bill_id: uuid.UUID
    recurrence_id: uuid.UUID | None = None
    due_date: date
    amount_cents: int = Field(..., gt=0, le=MAX_CENTS)
    notes: Notes | None = None
    idempotency_key: IdemKey | None = None


class BillInstallmentUpdate(BaseModel):
    amount_cents: int | None = Field(None, gt=0, le=MAX_CENTS)
    due_date: date | None = None
    status: BillInstallmentStatus | None = None
    notes: Notes | None = None


class BillInstallmentOut(ORM):
    id: uuid.UUID
    bill_id: uuid.UUID
    bill_name: str | None = None
    recurrence_id: uuid.UUID | None
    due_date: date
    amount_cents: int
    status: BillInstallmentStatus
    paid_at: datetime | None
    reversed_at: datetime | None
    transaction_id: uuid.UUID | None
    notes: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, i) -> "BillInstallmentOut":
        return cls(
            id=i.id,
            bill_id=i.bill_id,
            bill_name=i.bill.name if i.bill else None,
            recurrence_id=i.recurrence_id,
            due_date=i.due_date,
            amount_cents=i.amount_cents,
            status=i.status,
            paid_at=i.paid_at,
            reversed_at=i.reversed_at,
            transaction_id=i.transaction_id,
            notes=i.notes,
            created_at=i.created_at,
        )


class BillInstallmentPage(BaseModel):
    items: list[BillInstallmentOut]
    total: int
    page: int
    limit: int
