import calendar
from datetime import date

from fastapi import APIRouter, Query

from app.api.v1.deps import DB
from app.domains.reporting.dashboard import build_dashboard
from app.domains.support import today_local
from app.schemas.dashboard import Dashboard

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard", response_model=Dashboard)
def dashboard(
    db: DB,
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
):
    today = today_local()
    start = date_from or today.replace(day=1)
    end = date_to or today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return build_dashboard(db, start, end)
