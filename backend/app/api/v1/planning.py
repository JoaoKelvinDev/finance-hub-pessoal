"""Planejamento: orçamentos por categoria/período e metas com aportes."""

import uuid

from fastapi import APIRouter, Query, Response, status

from app.api.v1.deps import DB, RequestId
from app.core.errors import DomainError
from app.domains.planning import service
from app.domains.planning.projection import build_projection
from app.schemas.parties import ReasonIn
from app.schemas.planning import (
    BudgetCopyIn,
    BudgetCopyOut,
    BudgetCreate,
    BudgetOut,
    BudgetUpdate,
    GoalAllocationCreate,
    GoalContributionCreate,
    GoalCreate,
    GoalOut,
    GoalUpdate,
    ProjectionOut,
)

router = APIRouter(tags=["Planejamento"])


# ---------- orçamentos ----------

@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(db: DB):
    return service.list_budgets(db)


@router.post("/budgets", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
def create_budget(data: BudgetCreate, db: DB, rid: RequestId):
    budget_id = service.create_budget(db, data, rid)
    db.commit()
    return service.budget_out(db, service.get_budget(db, budget_id))


@router.post("/budgets/copy", response_model=BudgetCopyOut)
def copy_budgets(data: BudgetCopyIn, db: DB, rid: RequestId):
    """Repete os orçamentos de um mês no outro (os já existentes no destino são mantidos)."""
    created, skipped = service.copy_budgets(db, data.from_month, data.to_month, rid)
    db.commit()
    return BudgetCopyOut(created=created, skipped=skipped)


@router.patch("/budgets/{budget_id}", response_model=BudgetOut)
def update_budget(budget_id: uuid.UUID, data: BudgetUpdate, db: DB, rid: RequestId):
    budget = service.update_budget(db, budget_id, data, rid)
    db.commit()
    return service.budget_out(db, budget)


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(budget_id: uuid.UUID, db: DB, rid: RequestId):
    service.delete_budget(db, budget_id, rid)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- metas ----------

@router.get("/goals", response_model=list[GoalOut])
def list_goals(db: DB):
    return service.list_goals(db)


@router.post("/goals", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(data: GoalCreate, db: DB, rid: RequestId):
    goal_id = service.create_goal(db, data, rid)
    db.commit()
    return service.goal_out(db, service.get_goal(db, goal_id))


@router.get("/goals/{goal_id}", response_model=GoalOut)
def get_goal(goal_id: uuid.UUID, db: DB):
    return service.goal_out(db, service.get_goal(db, goal_id))


@router.patch("/goals/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: uuid.UUID, data: GoalUpdate, db: DB, rid: RequestId):
    goal = service.update_goal(db, goal_id, data, rid)
    db.commit()
    return service.goal_out(db, goal)


@router.post("/goals/{goal_id}/cancel", response_model=GoalOut)
def cancel_goal(goal_id: uuid.UUID, data: ReasonIn, db: DB, rid: RequestId):
    goal = service.cancel_goal(db, goal_id, data.reason, rid)
    db.commit()
    return service.goal_out(db, goal)


@router.post("/goals/{goal_id}/allocations", response_model=GoalOut)
def allocate_goal(goal_id: uuid.UUID, data: GoalAllocationCreate, db: DB, rid: RequestId, response: Response):
    """Registra um aporte na meta (sem mexer no caixa)."""
    _allocation_id, created = service.allocate_goal(db, goal_id, data, rid)
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return service.goal_out(db, service.get_goal(db, goal_id))


@router.post("/goals/{goal_id}/contributions", response_model=GoalOut)
def contribute_goal(goal_id: uuid.UUID, data: GoalContributionCreate, db: DB, rid: RequestId, response: Response):
    """Aporte com transferência real entre contas próprias (não é receita nem despesa)."""
    _allocation_id, created = service.contribute_goal(db, goal_id, data, rid)
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return service.goal_out(db, service.get_goal(db, goal_id))


@router.post("/goals/{goal_id}/allocations/{allocation_id}/reverse", response_model=GoalOut)
def reverse_allocation(goal_id: uuid.UUID, allocation_id: uuid.UUID, data: ReasonIn, db: DB, rid: RequestId):
    """Estorna um aporte (e a transferência entre contas, se houver)."""
    goal = service.reverse_allocation(db, goal_id, allocation_id, data.reason, rid)
    db.commit()
    return service.goal_out(db, goal)


@router.get("/projection", response_model=ProjectionOut)
def projection(db: DB, days: int = Query(30, description="Horizonte: 30, 60 ou 90 dias")):
    """Saldo projetado dia a dia (cenários conservador e base). Estimativa, não garantia."""
    if days not in (30, 60, 90):
        raise DomainError("projection_days", "O horizonte da projeção deve ser 30, 60 ou 90 dias.")
    return build_projection(db, days)
