import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel

CalendarSource = Literal[
    "CARD_STATEMENT", "BILL_INSTALLMENT", "RECURRENCE_FORECAST", "PLANNED_TRANSACTION", "PARTY_BALANCE"
]
CalendarStatus = Literal["PENDING", "OVERDUE", "PARTIAL", "PAID", "FORECAST", "SKIPPED", "REVERSED"]


class CalendarEvent(BaseModel):
    key: str
    source: CalendarSource
    source_id: uuid.UUID
    # Entidade para navegação: cartão (fatura), conta da casa (parcela/previsão), conta financeira
    # (lançamento) ou pessoa (valor com terceiro).
    ref_id: uuid.UUID
    date: date
    title: str
    subtitle: str | None = None
    direction: Literal["IN", "OUT"]
    amount_cents: int
    open_cents: int
    status: CalendarStatus
    color: str


class CalendarDay(BaseModel):
    date: date
    out_cents: int
    in_cents: int
    count: int


class CalendarSummary(BaseModel):
    to_pay_cents: int
    to_receive_cents: int
    paid_cents: int
    overdue_cents: int
    overdue_count: int
    event_count: int


class CalendarResponse(BaseModel):
    date_from: date
    date_to: date
    today: date
    summary: CalendarSummary
    days: list[CalendarDay]
    events: list[CalendarEvent]
