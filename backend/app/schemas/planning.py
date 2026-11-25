"""Contratos de planejamento: orçamentos por categoria/período e metas com aportes."""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import MAX_CENTS, IdemKey, Name

BudgetBasis = Literal["CASH", "COMPETENCE"]
BudgetStatus = Literal["OK", "WARNING", "OVER"]
GoalState = Literal["ACTIVE", "ACHIEVED", "CANCELLED"]


class BudgetCreate(BaseModel):
    category_id: uuid.UUID | None = None
    period_start: dt.date
    period_end: dt.date
    limit_cents: int = Field(..., gt=0, le=MAX_CENTS)
    # CASH: o que foi pago no período. COMPETENCE: o consumo atribuído ao período.
    basis: BudgetBasis = "CASH"
    notes: str | None = None

    @model_validator(mode="after")
    def _period(self):
        if self.period_end < self.period_start:
            raise ValueError("A data final do período deve ser igual ou posterior à inicial.")
        return self


class BudgetUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    period_start: dt.date | None = None
    period_end: dt.date | None = None
    limit_cents: int | None = Field(None, gt=0, le=MAX_CENTS)
    basis: BudgetBasis | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _period(self):
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValueError("A data final do período deve ser igual ou posterior à inicial.")
        return self


class BudgetOut(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    period_start: dt.date
    period_end: dt.date
    limit_cents: int
    basis: BudgetBasis
    notes: str | None = None
    # Realizado: consumo já efetivado no período, conforme a base escolhida.
    spent_cents: int
    # Comprometido: obrigações que ainda vão sair do caixa dentro do período (só na base caixa).
    committed_cents: int
    used_cents: int
    remaining_cents: int
    progress_pct: float
    status: BudgetStatus
    formula: str


class GoalCreate(BaseModel):
    title: Name
    target_cents: int = Field(..., gt=0, le=MAX_CENTS)
    target_date: dt.date | None = None
    notes: str | None = None


class GoalUpdate(BaseModel):
    title: Name | None = None
    target_cents: int | None = Field(None, gt=0, le=MAX_CENTS)
    target_date: dt.date | None = None
    notes: str | None = None


class GoalAllocationCreate(BaseModel):
    """Aporte registrado na meta (sem mexer no caixa)."""

    amount_cents: int = Field(..., gt=0, le=MAX_CENTS)
    allocated_on: dt.date
    transfer_reference: str | None = Field(None, max_length=120)
    notes: str | None = None
    idempotency_key: IdemKey | None = None


class GoalContributionCreate(BaseModel):
    """Aporte com transferência real entre contas próprias: não é receita nem despesa."""

    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount_cents: int = Field(..., gt=0, le=MAX_CENTS)
    effective_date: dt.date
    notes: str | None = None
    idempotency_key: IdemKey | None = None

    @model_validator(mode="after")
    def _distinct(self):
        if self.from_account_id == self.to_account_id:
            raise ValueError("Origem e destino devem ser contas diferentes.")
        return self


class GoalAllocationOut(BaseModel):
    id: uuid.UUID
    amount_cents: int
    allocated_on: dt.date
    transfer_reference: str | None = None
    # Preenchido quando o aporte moveu dinheiro entre contas próprias.
    transfer_group_id: uuid.UUID | None = None
    notes: str | None = None
    reversed_at: dt.datetime | None = None
    reverse_reason: str | None = None
    created_at: dt.datetime


class BudgetCopyIn(BaseModel):
    """Copia os orçamentos de um mês inteiro para outro (YYYY-MM)."""

    from_month: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    to_month: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class BudgetCopyOut(BaseModel):
    created: int
    skipped: int


class GoalOut(BaseModel):
    id: uuid.UUID
    title: str
    target_cents: int
    target_date: dt.date | None = None
    state: GoalState
    notes: str | None = None
    allocated_cents: int
    remaining_cents: int
    progress_pct: float
    allocations: list[GoalAllocationOut] = []


class ProjectionPoint(BaseModel):
    date: dt.date
    conservative_cents: int
    base_cents: int


class ProjectionSummary(BaseModel):
    end_cents: int
    lowest_cents: int
    lowest_date: dt.date
    inflow_cents: int
    outflow_cents: int


class ProjectionOut(BaseModel):
    """Estimativa de saldo diário — nunca um saldo garantido."""

    today: dt.date
    days: int
    start_balance_cents: int
    conservative: ProjectionSummary
    base: ProjectionSummary
    points: list[ProjectionPoint]
