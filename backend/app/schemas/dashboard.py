import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.finance import AccountOut, TransactionOut


class Kpi(BaseModel):
    value_cents: int
    previous_cents: int | None = None
    change_pct: float | None = None
    formula: str


class MonthPoint(BaseModel):
    month: str  # YYYY-MM
    income_cents: int
    expense_cents: int
    net_cents: int
    partial: bool


class BalancePoint(BaseModel):
    date: date
    balance_cents: int
    projected: bool


class CategorySlice(BaseModel):
    category_id: uuid.UUID | None
    name: str
    color: str
    amount_cents: int
    share_pct: float
    previous_cents: int
    change_pct: float | None


class Health(BaseModel):
    savings_rate_pct: float | None
    overdue_count: int
    overdue_cents: int


class Dashboard(BaseModel):
    period_from: date
    period_to: date
    today: date
    timezone: str
    kpis: dict[str, Kpi]
    free_after_commitments_cents: int
    free_until: date
    monthly: list[MonthPoint]
    balance_series: list[BalancePoint]
    expenses_by_category: list[CategorySlice]
    upcoming: list[TransactionOut]
    recent: list[TransactionOut]
    accounts: list[AccountOut]
    health: Health
