import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

AlertKind = Literal["DUE_SOON", "DUE_TODAY", "OVERDUE", "RECEIVABLE_OVERDUE", "CARD_UTILIZATION", "ESTIMATE_PENDING"]
AlertSeverity = Literal["info", "warning", "danger"]


class Alert(BaseModel):
    # Inclui o estágio (ex.: D-3): ao agravar, a chave muda e o alerta reaparece mesmo se dispensado.
    key: str
    kind: AlertKind
    severity: AlertSeverity
    title: str
    message: str
    date: dt.date | None = None
    amount_cents: int | None = None
    source: str
    source_id: uuid.UUID
    # Caminho da tela no frontend para agir sobre o item.
    link: str


class AlertCounts(BaseModel):
    total: int
    danger: int
    warning: int
    info: int


class AlertList(BaseModel):
    items: list[Alert]
    counts: AlertCounts


class AlertDismissIn(BaseModel):
    key: Annotated[str, StringConstraints(min_length=3, max_length=200)]
