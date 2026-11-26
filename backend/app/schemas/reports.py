import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel

ReportBasis = Literal["CASH", "COMPETENCE"]


class CategoryRow(BaseModel):
    category_id: uuid.UUID | None
    name: str
    color: str
    amount_cents: int
    previous_cents: int
    share_pct: float
    # None quando o período anterior é zero (variação indefinida).
    change_pct: float | None
    children: list["CategoryRow"] = []


CategoryRow.model_rebuild()


class CategoryReport(BaseModel):
    date_from: dt.date
    date_to: dt.date
    previous_from: dt.date
    previous_to: dt.date
    basis: ReportBasis
    total_cents: int
    previous_total_cents: int
    rows: list[CategoryRow]


class CashFlowPoint(BaseModel):
    # YYYY-MM (mensal) ou YYYY-MM-DD (diário)
    period: str
    income_cents: int
    expense_cents: int
    net_cents: int


class CashFlowReport(BaseModel):
    date_from: dt.date
    date_to: dt.date
    granularity: Literal["day", "month"]
    income_cents: int
    expense_cents: int
    net_cents: int
    points: list[CashFlowPoint]


class MerchantRow(BaseModel):
    name: str
    amount_cents: int
    count: int


class CardReportRow(BaseModel):
    card_id: uuid.UUID
    name: str
    bank: str | None
    color: str
    limit_cents: int
    purchases_cents: int
    purchases_count: int
    paid_cents: int
    open_cents: int
    future_cents: int
    top_merchants: list[MerchantRow]


class CardReport(BaseModel):
    date_from: dt.date
    date_to: dt.date
    purchases_cents: int
    paid_cents: int
    open_cents: int
    future_cents: int
    cards: list[CardReportRow]


class AgingBuckets(BaseModel):
    """Valores vencidos e em aberto por dias de atraso (o que não venceu fica em `current`)."""

    current_cents: int
    d0_30_cents: int
    d31_60_cents: int
    d61_90_cents: int
    d90_plus_cents: int
    no_due_cents: int


class CounterpartyRow(BaseModel):
    person_id: uuid.UUID
    name: str
    receivable_cents: int
    payable_cents: int
    receivable_aging: AgingBuckets
    settled_in_period_cents: int


class CounterpartyReport(BaseModel):
    today: dt.date
    receivable_cents: int
    payable_cents: int
    receivable_aging: AgingBuckets
    people: list[CounterpartyRow]
