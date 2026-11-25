from fastapi import APIRouter

from app.api.v1.deps import DB
from app.domains.alerts import service
from app.schemas.alerts import AlertDismissIn, AlertList

router = APIRouter(tags=["Alertas"])


@router.get("/alerts", response_model=AlertList)
def list_alerts(db: DB):
    """Alertas ativos (calculados agora), sem os dispensados."""
    return service.list_alerts(db)


@router.post("/alerts/dismiss", response_model=AlertList)
def dismiss_alert(data: AlertDismissIn, db: DB):
    """Dispensa um alerta. Se ele se agravar (ex.: D-3 → vencido), volta a aparecer."""
    service.dismiss(db, data.key)
    db.commit()
    return service.list_alerts(db)
