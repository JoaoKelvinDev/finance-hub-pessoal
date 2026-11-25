"""Projeção de saldo em 30/60/90 dias (estimativa, nunca saldo garantido).

Ponto de partida: saldo atual efetivado das contas ativas. Cada compromisso em aberto entra
no dia do vencimento; o que já venceu e segue em aberto entra hoje (ainda vai sair/entrar).

Sem dupla contagem: compras no cartão entram só pelo pagamento da fatura (eventos
CARD_STATEMENT); parcelas de cartão nunca entram sozinhas. Lançamentos previstos já
efetivados não aparecem (são saldo). Transferências internas não mudam o total.

Cenários:
- conservador: só o que já está registrado como obrigação ou receita prevista; valores
  que terceiros me devem ficam de fora (não há garantia de recebimento).
- base: conservador + recebíveis de terceiros + ocorrências futuras das recorrências
  que ainda não viraram parcela.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.calendar.service import collect_events
from app.domains.ledger.service import balances
from app.domains.support import today_local
from app.models import FinancialAccount
from app.schemas.calendar import CalendarEvent
from app.schemas.planning import ProjectionOut, ProjectionPoint, ProjectionSummary

OPEN_STATUSES = ("PENDING", "OVERDUE", "PARTIAL", "FORECAST")
# Vencidos em aberto até 1 ano atrás ainda entram (como saída/entrada de hoje).
LOOKBACK_DAYS = 365


def _in_scenario(e: CalendarEvent, scenario: str) -> bool:
    if e.status not in OPEN_STATUSES or e.open_cents <= 0:
        return False
    if scenario == "conservative":
        if e.source == "RECURRENCE_FORECAST":
            return False
        if e.source == "PARTY_BALANCE" and e.direction == "IN":
            return False
    return True


def build_projection(db: Session, days: int) -> ProjectionOut:
    today = today_local()
    end = today + timedelta(days=days)

    active_ids = list(db.scalars(select(FinancialAccount.id).where(FinancialAccount.archived_at.is_(None))))
    start_balance = sum(b[0] for acc, b in balances(db, active_ids).items()) if active_ids else 0

    events = collect_events(db, today - timedelta(days=LOOKBACK_DAYS), end, today, include_forecast=True)

    deltas: dict[str, dict[date, int]] = {"conservative": {}, "base": {}}
    totals = {s: {"in": 0, "out": 0} for s in deltas}
    for e in events:
        when = max(e.date, today)
        if when > end:
            continue
        signed = e.open_cents if e.direction == "IN" else -e.open_cents
        for scenario, by_day in deltas.items():
            if not _in_scenario(e, scenario):
                continue
            by_day[when] = by_day.get(when, 0) + signed
            totals[scenario]["in" if signed > 0 else "out"] += abs(signed)

    points: list[ProjectionPoint] = []
    running = {s: start_balance for s in deltas}
    lows = {s: (start_balance, today) for s in deltas}
    d = today
    while d <= end:
        for s, by_day in deltas.items():
            running[s] += by_day.get(d, 0)
            if running[s] < lows[s][0]:
                lows[s] = (running[s], d)
        points.append(ProjectionPoint(date=d, conservative_cents=running["conservative"], base_cents=running["base"]))
        d += timedelta(days=1)

    summary = {
        s: ProjectionSummary(
            end_cents=running[s],
            lowest_cents=lows[s][0],
            lowest_date=lows[s][1],
            inflow_cents=totals[s]["in"],
            outflow_cents=totals[s]["out"],
        )
        for s in deltas
    }
    return ProjectionOut(
        today=today,
        days=days,
        start_balance_cents=start_balance,
        conservative=summary["conservative"],
        base=summary["base"],
        points=points,
    )
