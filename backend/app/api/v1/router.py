from fastapi import APIRouter, Depends

from app.api.v1 import (
    accounts,
    alerts,
    bills,
    calendar,
    cards,
    catalog,
    dashboard,
    parties,
    planning,
    splits,
    transactions,
)
from app.core.owner_access import require_owner

# Toda rota financeira exige a identidade do proprietário.
api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_owner)])
api_router.include_router(dashboard.router)
api_router.include_router(accounts.router)
api_router.include_router(transactions.router)
api_router.include_router(catalog.router)
api_router.include_router(cards.router)
api_router.include_router(splits.router)
api_router.include_router(bills.router)
api_router.include_router(calendar.router)
api_router.include_router(parties.router)
api_router.include_router(alerts.router)
api_router.include_router(planning.router)


@api_router.get("/me", tags=["Sessão"])
def me():
    return {"owner": True}
