from datetime import date, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.domains.calendar.service import collect_events
from app.domains.ledger.rules import EXPENSE_KINDS, INCOME_KINDS
from app.domains.ledger.service import balances
from app.domains.money import pct_change
from app.domains.parties.service import open_totals as party_open_totals
from app.domains.planning.projection import build_projection
from app.domains.reporting.reports import category_report
from app.domains.support import today_local
from app.models import FinancialAccount, Transaction
from app.schemas.dashboard import BalancePoint, CategorySlice, Dashboard, Health, Kpi, MonthPoint
from app.schemas.finance import AccountOut, TransactionOut

HORIZON_DAYS = 30
MAX_RANGE_DAYS = 731
TOP_CATEGORIES = 5
# Vencidos em aberto até 1 ano atrás contam como compromisso (mesma janela da projeção).
OVERDUE_LOOKBACK_DAYS = 365
OPEN_STATUSES = ("PENDING", "OVERDUE", "PARTIAL", "FORECAST")


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def _sum(db: Session, *conds) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(*conds)) or 0)


def _realized(db: Session, kinds: tuple[str, ...], start: date, end: date) -> int:
    """Lançamentos efetivados no período, em regime de caixa (igual ao relatório de fluxo de caixa).

    O pagamento da fatura É a saída de caixa do cartão: as compras não são lançamentos,
    então não há dupla contagem. Transferências, empréstimos e acertos não entram (filtro por kind).
    """
    return abs(
        _sum(
            db,
            Transaction.status == "POSTED",
            Transaction.kind.in_(kinds),
            Transaction.effective_date.between(start, end),
        )
    )


def build_dashboard(db: Session, period_from: date, period_to: date) -> Dashboard:
    if period_to < period_from:
        raise DomainError("period_invalid", "A data final deve ser posterior à inicial.")
    if (period_to - period_from).days > MAX_RANGE_DAYS:
        raise DomainError("period_too_long", "Período máximo de 2 anos.")

    today = today_local()
    span = period_to - period_from
    prev_to = period_from - timedelta(days=1)
    prev_from = prev_to - span

    accounts = db.scalars(select(FinancialAccount).order_by(FinancialAccount.name)).all()
    bal = balances(db)
    active = [a for a in accounts if a.archived_at is None]
    active_ids = [a.id for a in active]
    available = sum(bal.get(a.id, (a.opening_balance_cents, 0))[0] for a in active)

    income = _realized(db, INCOME_KINDS, period_from, period_to)
    expense = _realized(db, EXPENSE_KINDS, period_from, period_to)
    prev_income = _realized(db, INCOME_KINDS, prev_from, prev_to)
    prev_expense = _realized(db, EXPENSE_KINDS, prev_from, prev_to)

    horizon = today + timedelta(days=HORIZON_DAYS)
    planned_active = and_(Transaction.status == "PLANNED", Transaction.account_id.in_(active_ids))

    # Compromissos = os mesmos eventos do calendário (faturas, contas da casa, previsões de
    # recorrência, dívidas com terceiros e lançamentos previstos). Antes só os previstos contavam.
    events = collect_events(
        db, today - timedelta(days=OVERDUE_LOOKBACK_DAYS), horizon, today, include_forecast=True
    )
    out_open = [e for e in events if e.direction == "OUT" and e.status in OPEN_STATUSES and e.open_cents > 0]
    overdue_events = [e for e in out_open if e.status == "OVERDUE" or (e.date < today and e.status == "PARTIAL")]
    # "A vencer" e "Vencidas" mostram obrigações reais; previsão de recorrência só entra no saldo livre.
    due_soon = sum(
        e.open_cents for e in out_open if e.status != "FORECAST" and e not in overdue_events and today <= e.date
    )
    overdue = sum(e.open_cents for e in overdue_events)
    overdue_count = len(overdue_events)

    next_income = min(
        (e.date for e in events if e.source == "PLANNED_TRANSACTION" and e.direction == "IN"
         and e.status == "PENDING" and e.date >= today),
        default=None,
    )
    free_until = next_income or horizon
    # Tudo que ainda vai sair até o próximo recebimento (vencidos em aberto inclusos).
    commitments_until = sum(e.open_cents for e in out_open if e.date <= free_until)
    projection = build_projection(db, HORIZON_DAYS)

    receivable_open, payable_open = party_open_totals(db)

    kpis = {
        "available_balance": Kpi(
            value_cents=available,
            formula="Saldo inicial + lançamentos efetivados das contas ativas. Previstos não entram.",
        ),
        "income": Kpi(
            value_cents=income, previous_cents=prev_income, change_pct=pct_change(income, prev_income),
            formula="Receitas efetivadas no período. Transferências, ajustes e reembolsos não contam.",
        ),
        "expense": Kpi(
            value_cents=expense, previous_cents=prev_expense, change_pct=pct_change(expense, prev_expense),
            formula="Despesas efetivadas no período, em regime de caixa: inclui o pagamento da fatura do cartão "
            "e das contas da casa. Transferências, empréstimos e ajustes não contam.",
        ),
        "net": Kpi(
            value_cents=income - expense,
            previous_cents=prev_income - prev_expense,
            change_pct=pct_change(income - expense, prev_income - prev_expense),
            formula="Receitas − despesas efetivadas no período.",
        ),
        "due_soon": Kpi(
            value_cents=due_soon,
            formula=f"Faturas, contas da casa, dívidas com terceiros e despesas previstas que vencem de hoje até "
            f"{HORIZON_DAYS} dias (o que falta pagar).",
        ),
        "overdue": Kpi(
            value_cents=overdue,
            formula="Faturas, contas da casa, dívidas com terceiros e despesas previstas já vencidas e ainda em aberto.",
        ),
        "projected": Kpi(
            value_cents=projection.base.end_cents,
            formula=f"Saldo daqui a {HORIZON_DAYS} dias no cenário base da Projeção (Planejamento). "
            "Estimativa, não garantia.",
        ),
        "receivables": Kpi(
            value_cents=receivable_open,
            formula="Quanto terceiros me devem hoje: principal + encargos − descontos − acertos. Não é receita.",
        ),
        "payables": Kpi(
            value_cents=payable_open,
            formula="Quanto devo a terceiros hoje: principal + encargos − descontos − acertos. Não é despesa.",
        ),
    }

    return Dashboard(
        period_from=period_from,
        period_to=period_to,
        today=today,
        timezone=get_settings().app_timezone,
        kpis=kpis,
        free_after_commitments_cents=available - commitments_until,
        free_until=free_until,
        monthly=_monthly(db, period_to, today),
        balance_series=_balance_series(db, active, active_ids, period_from, period_to, today),
        expenses_by_category=_categories(db, period_from, period_to),
        upcoming=[
            TransactionOut.from_model(t)
            for t in db.scalars(
                select(Transaction).where(planned_active).order_by(Transaction.effective_date).limit(8)
            ).unique()
        ],
        recent=[
            TransactionOut.from_model(t)
            for t in db.scalars(
                select(Transaction)
                .where(Transaction.status == "POSTED")
                .order_by(Transaction.effective_date.desc(), Transaction.created_at.desc())
                .limit(8)
            ).unique()
        ],
        accounts=[
            AccountOut.model_validate(a).model_copy(
                update={
                    "balance_cents": bal.get(a.id, (a.opening_balance_cents, 0))[0],
                    "planned_balance_cents": bal.get(a.id, (0, a.opening_balance_cents))[1],
                }
            )
            for a in active
        ],
        health=Health(
            savings_rate_pct=round((income - expense) * 100 / income, 1) if income > 0 else None,
            overdue_count=overdue_count,
            overdue_cents=overdue,
        ),
    )


def _monthly(db: Session, period_to: date, today: date) -> list[MonthPoint]:
    end_month = _month_start(period_to)
    start = _add_months(end_month, -5)
    month = func.to_char(Transaction.effective_date, "YYYY-MM")
    rows = db.execute(
        select(month, Transaction.kind, func.sum(Transaction.amount_cents))
        .where(
            Transaction.status == "POSTED",
            Transaction.kind.in_(INCOME_KINDS + EXPENSE_KINDS),
            Transaction.effective_date >= start,
            Transaction.effective_date < _add_months(end_month, 1),
        )
        .group_by(month, Transaction.kind)
    ).all()
    agg: dict[str, dict[str, int]] = {}
    for m, kind, total in rows:
        agg.setdefault(m, {})[kind] = abs(int(total))
    out = []
    for i in range(6):
        ms = _add_months(start, i)
        key = ms.strftime("%Y-%m")
        inc = agg.get(key, {}).get("INCOME", 0)
        exp = agg.get(key, {}).get("EXPENSE", 0)
        out.append(
            MonthPoint(
                month=key, income_cents=inc, expense_cents=exp, net_cents=inc - exp,
                partial=ms <= today < _add_months(ms, 1),
            )
        )
    return out


def _balance_series(db, active, active_ids, period_from, period_to, today) -> list[BalancePoint]:
    if not active_ids:
        return []
    start_balance = sum(a.opening_balance_cents for a in active if a.opening_date < period_from)
    start_balance += _sum(
        db,
        Transaction.status == "POSTED",
        Transaction.account_id.in_(active_ids),
        Transaction.effective_date < period_from,
    )
    deltas: dict[date, int] = {}
    for a in active:
        if period_from <= a.opening_date <= period_to:
            deltas[a.opening_date] = deltas.get(a.opening_date, 0) + a.opening_balance_cents
    for d, total in db.execute(
        select(Transaction.effective_date, func.sum(Transaction.amount_cents))
        .where(
            Transaction.status == "POSTED",
            Transaction.account_id.in_(active_ids),
            Transaction.effective_date.between(period_from, period_to),
        )
        .group_by(Transaction.effective_date)
    ):
        deltas[d] = deltas.get(d, 0) + int(total)

    # Depois de hoje: o cenário base da Projeção (faturas, contas, previsões, terceiros),
    # deslocado para continuar a linha realizada sem salto.
    projected: dict[date, int] = {}
    if period_to > today:
        proj = build_projection(db, min((period_to - today).days, 366))
        offset = None
        for p in proj.points:
            if p.date == today:
                offset = p.base_cents
            elif offset is not None:
                projected[p.date] = p.base_cents - offset

    points, running, d = [], start_balance, period_from
    real_today = None
    while d <= period_to:
        if d <= today:
            running += deltas.get(d, 0)
            real_today = running
            value = running
        else:
            base = real_today if real_today is not None else running
            value = base + projected.get(d, 0)
        points.append(BalancePoint(date=d, balance_cents=value, projected=d > today))
        d += timedelta(days=1)
    return points


def _categories(db: Session, period_from: date, period_to: date) -> list[CategorySlice]:
    """Rosca do dashboard = relatório de Categorias na base caixa (5 maiores + demais)."""
    report = category_report(db, period_from, period_to, "CASH")
    total = report.total_cents
    if total == 0:
        return []
    head, tail = report.rows[:TOP_CATEGORIES], report.rows[TOP_CATEGORIES:]
    slices = [
        CategorySlice(
            category_id=r.category_id,
            name=r.name,
            color=r.color,
            amount_cents=r.amount_cents,
            share_pct=r.share_pct,
            previous_cents=r.previous_cents,
            change_pct=r.change_pct,
        )
        for r in head
    ]
    if tail:
        amount = sum(r.amount_cents for r in tail)
        prev = sum(r.previous_cents for r in tail)
        slices.append(
            CategorySlice(
                category_id=None, name="Demais categorias", color="#8A8A85", amount_cents=amount,
                share_pct=round(amount * 100 / total, 1), previous_cents=prev, change_pct=pct_change(amount, prev),
            )
        )
    return slices
