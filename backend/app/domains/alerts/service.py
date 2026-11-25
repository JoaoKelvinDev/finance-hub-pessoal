"""Central de alertas in-app (calculada sob demanda; nenhum alerta é gravado).

Vencimentos D-7/D-3/D-1/D0 e vencidos, recebível vencido, uso de cartão acima do limite
configurado e estimativa de conta variável ainda não confirmada. Lembrete não é pagamento.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domains.calendar.service import collect_events
from app.domains.cards.service import get_card_with_limits, list_cards
from app.domains.money import format_brl
from app.domains.support import today_local
from app.models import AlertDismissal, AppSettings
from app.schemas.alerts import Alert, AlertCounts, AlertList
from app.schemas.calendar import CalendarEvent

LOOKAHEAD_DAYS = 7
# Vencidos muito antigos continuam relevantes; a janela só evita varrer o histórico inteiro.
LOOKBACK_DAYS = 730
OPEN_STATUSES = ("PENDING", "OVERDUE", "PARTIAL")
SEVERITY_ORDER = {"danger": 0, "warning": 1, "info": 2}


def _stage(days: int) -> str | None:
    """Estágio do lembrete: D-7 (4–7 dias), D-3 (2–3), D-1, D0 e vencido."""
    if days < 0:
        return "overdue"
    if days == 0:
        return "d0"
    if days == 1:
        return "d1"
    if days <= 3:
        return "d3"
    if days <= LOOKAHEAD_DAYS:
        return "d7"
    return None


def _link(e: CalendarEvent) -> str:
    return {
        "CARD_STATEMENT": f"/cartoes/{e.ref_id}",
        "BILL_INSTALLMENT": "/contas-da-casa",
        "PLANNED_TRANSACTION": "/lancamentos?period=all&status=PLANNED",
        "PARTY_BALANCE": f"/pessoas/{e.ref_id}",
    }.get(e.source, "/calendario")


def _when(days: int) -> str:
    if days < 0:
        n = -days
        return f"venceu há {n} {'dia' if n == 1 else 'dias'}"
    if days == 0:
        return "vence hoje"
    if days == 1:
        return "vence amanhã"
    return f"vence em {days} dias"


def _event_alerts(events: list[CalendarEvent], today: date) -> list[Alert]:
    alerts: list[Alert] = []
    for e in events:
        if e.status not in OPEN_STATUSES or e.open_cents <= 0:
            continue
        days = (e.date - today).days
        stage = _stage(days)
        if stage is None:
            continue

        if e.direction == "IN":
            # Para valores a receber, só o atraso vira alerta (vencimento futuro é boa notícia).
            if stage != "overdue":
                continue
            alerts.append(
                Alert(
                    key=f"receivable:{e.source_id}:overdue",
                    kind="RECEIVABLE_OVERDUE",
                    severity="warning",
                    title=e.title,
                    message=f"{format_brl(e.open_cents)} a receber · {_when(days)}",
                    date=e.date,
                    amount_cents=e.open_cents,
                    source=e.source,
                    source_id=e.source_id,
                    link=_link(e),
                )
            )
            continue

        kind = "OVERDUE" if stage == "overdue" else "DUE_TODAY" if stage == "d0" else "DUE_SOON"
        severity = "danger" if stage == "overdue" else "warning" if stage in ("d0", "d1") else "info"
        estimate = " (estimado)" if e.estimated else ""
        alerts.append(
            Alert(
                key=f"due:{e.key}:{stage}",
                kind=kind,
                severity=severity,
                title=e.title,
                message=f"{format_brl(e.open_cents)}{estimate} · {_when(days)}",
                date=e.date,
                amount_cents=e.open_cents,
                source=e.source,
                source_id=e.source_id,
                link=_link(e),
            )
        )

        if e.estimated and 0 <= days <= LOOKAHEAD_DAYS:
            alerts.append(
                Alert(
                    key=f"estimate:{e.source_id}",
                    kind="ESTIMATE_PENDING",
                    severity="info",
                    title=f"{e.title}: confirme o valor real",
                    message=f"Estimativa de {format_brl(e.amount_cents)} · {_when(days)}",
                    date=e.date,
                    amount_cents=e.amount_cents,
                    source=e.source,
                    source_id=e.source_id,
                    link=_link(e),
                )
            )
    return alerts


def _card_alerts(db: Session, threshold_pct: int) -> list[Alert]:
    alerts = []
    for card in list_cards(db, include_archived=False):
        _, used, _available = get_card_with_limits(db, card.id)
        if card.limit_cents <= 0 or used <= 0:
            continue
        # Inteiro: sem ponto flutuante.
        pct = used * 100 // card.limit_cents
        if pct < threshold_pct:
            continue
        full = pct >= 100
        alerts.append(
            Alert(
                key=f"card:{card.id}:{'full' if full else threshold_pct}",
                kind="CARD_UTILIZATION",
                severity="danger" if full else "warning",
                title=f"Cartão {card.nickname or card.name}: {pct}% do limite usado",
                message=f"{format_brl(used)} de {format_brl(card.limit_cents)} (alerta a partir de {threshold_pct}%)",
                amount_cents=used,
                source="CREDIT_CARD",
                source_id=card.id,
                link=f"/cartoes/{card.id}",
            )
        )
    return alerts


def list_alerts(db: Session) -> AlertList:
    today = today_local()
    settings = db.get(AppSettings, 1)
    threshold = settings.alert_card_utilization_pct if settings else 80

    events = collect_events(
        db, today - timedelta(days=LOOKBACK_DAYS), today + timedelta(days=LOOKAHEAD_DAYS), today,
        include_forecast=False,
    )
    alerts = _event_alerts(events, today) + _card_alerts(db, threshold)

    dismissed = set(db.scalars(select(AlertDismissal.key).where(AlertDismissal.key.in_([a.key for a in alerts]))))
    items = sorted(
        (a for a in alerts if a.key not in dismissed),
        key=lambda a: (SEVERITY_ORDER[a.severity], a.date or today, a.title),
    )
    return AlertList(
        items=items,
        counts=AlertCounts(
            total=len(items),
            danger=sum(a.severity == "danger" for a in items),
            warning=sum(a.severity == "warning" for a in items),
            info=sum(a.severity == "info" for a in items),
        ),
    )


def dismiss(db: Session, key: str) -> None:
    db.execute(insert(AlertDismissal).values(key=key).on_conflict_do_nothing(index_elements=["key"]))
    db.flush()
