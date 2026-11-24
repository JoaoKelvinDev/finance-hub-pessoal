from fastapi import APIRouter, Depends

from app.api.v1 import accounts, catalog, dashboard, transactions
from app.core.owner_access import require_owner

# Toda rota financeira exige a identidade do proprietário.
api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_owner)])
api_router.include_router(dashboard.router)
api_router.include_router(accounts.router)
api_router.include_router(transactions.router)
api_router.include_router(catalog.router)


@api_router.get("/me", tags=["Sessão"])
def me():
    return {"owner": True}
