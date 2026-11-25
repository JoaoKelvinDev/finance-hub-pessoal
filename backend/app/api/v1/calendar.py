from datetime import date

from fastapi import APIRouter, Query

from app.api.v1.deps import DB
from app.domains.calendar.service import build_calendar
from app.schemas.calendar import CalendarResponse

router = APIRouter(tags=["Calendário"])


@router.get("/calendar", response_model=CalendarResponse)
def calendar_endpoint(
    db: DB,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
):
    """Eventos financeiros unificados (faturas, contas, previsões e lançamentos previstos), sem duplicidade."""
    return build_calendar(db, date_from, date_to)
