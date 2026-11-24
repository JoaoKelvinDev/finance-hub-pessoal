from datetime import date, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.domains.ledger.rules import EXPENSE_KINDS, INCOME_KINDS
from app.domains.ledger.service import balances
from app.domains.money import pct_change
from app.domains.support import today_local
from app.models import Category, FinancialAccount, Transaction
from app.schemas.dashboard import BalancePoint, CategorySlice, Dashboard, Health, Kpi, MonthPoint
from app.schemas.finance import AccountOut, TransactionOut

HORIZON_DAYS = 30
MAX_RANGE_DAYS = 731
TOP_CATEGORIES = 5


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def _sum(db: Session, *conds) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(*conds)) or 0)


def _realized(db: Session, kinds: tuple[str, ...], start: date, end: date) -> int:
    """Lançamentos efetivados no período, excluindo pagamentos de fatura (evita dupla contagem)."""
    return abs(
        _sum(
            db,
            Transaction.status == "POSTED",
            Transaction.kind.in_(kinds),
            Transaction.effective_date.between(start, end),
            Transaction.source_type != "statement_payment",
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
    planned_active = and_(
        Transaction.status == "PLANNED",
        Transaction.account_id.in_(active_ids),
        Transaction.source_type != "statement_payment",
    )
    due_soon = abs(_sum(db, planned_active, Transaction.kind == "EXPENSE", Transaction.effective_date.between(today, horizon)))
    overdue = abs(_sum(db, planned_active, Transaction.kind == "EXPENSE", Transaction.effective_date < today))
    overdue_count = db.scalar(
        select(func.count()).where(planned_active, Transaction.kind == "EXPENSE", Transaction.effective_date < today)
    ) or 0
    planned_in = _sum(db, planned_active, Transaction.kind == "INCOME", Transaction.effective_date <= horizon)
    planned_out = abs(_sum(db, planned_active, Transaction.kind == "EXPENSE", Transaction.effective_date <= horizon))

    next_income = db.scalar(
        select(func.min(Transaction.effective_date)).where(
            planned_active, Transaction.kind == "INCOME", Transaction.effective_date >= today
        )
    )
    free_until = next_income or horizon
    commitments_until = abs(
        _sum(db, planned_active, Transaction.kind == "EXPENSE", Transaction.effective_date <= free_until)
    )

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
            formula="Despesas efetivadas no período (regime de caixa). Transferências e ajustes não contam.",
        ),
        "net": Kpi(
            value_cents=income - expense,
            previous_cents=prev_income - prev_expense,
            change_pct=pct_change(income - expense, prev_income - prev_expense),
            formula="Receitas − despesas efetivadas no período.",
        ),
        "due_soon": Kpi(value_cents=due_soon, formula=f"Despesas previstas de hoje até {HORIZON_DAYS} dias."),
        "overdue": Kpi(value_cents=overdue, formula="Despesas previstas com data anterior a hoje e ainda não pagas."),
        "projected": Kpi(
            value_cents=available + planned_in - planned_out,
            formula=f"Saldo disponível + receitas previstas − despesas previstas (incluindo vencidas) até {HORIZON_DAYS} dias. Estimativa, não garantia.",
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
        expenses_by_category=_categories(db, period_from, period_to, prev_from, prev_to),
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
        Transaction.source_type != "statement_payment",
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
            Transaction.source_type != "statement_payment",
        )
        .group_by(Transaction.effective_date)
    ):
        deltas[d] = deltas.get(d, 0) + int(total)

    projected_deltas: dict[date, int] = {}
    if period_to > today:
        first_proj = today + timedelta(days=1)
        for d, total in db.execute(
            select(Transaction.effective_date, func.sum(Transaction.amount_cents))
            .where(
                Transaction.status == "PLANNED",
                Transaction.account_id.in_(active_ids),
                Transaction.source_type != "statement_payment",
                Transaction.effective_date <= period_to,
            )
            .group_by(Transaction.effective_date)
        ):
            # Previstos vencidos entram no primeiro dia projetado.
            key = max(d, first_proj)
            projected_deltas[key] = projected_deltas.get(key, 0) + int(total)

    points, running, d = [], start_balance, period_from
    while d <= period_to:
        running += deltas.get(d, 0)
        if d > today:
            running += projected_deltas.get(d, 0)
        points.append(BalancePoint(date=d, balance_cents=running, projected=d > today))
        d += timedelta(days=1)
    return points


def _categories(db, period_from, period_to, prev_from, prev_to) -> list[CategorySlice]:
    """Agrupa pela categoria principal (subcategoria soma no pai) para manter poucas fatias."""
    root = func.coalesce(Category.parent_id, Category.id)

    def by_cat(start, end) -> dict:
        rows = db.execute(
            select(root, func.sum(Transaction.amount_cents))
            .select_from(Transaction)
            .outerjoin(Category, Category.id == Transaction.category_id)
            .where(
                Transaction.status == "POSTED", Transaction.kind.in_(EXPENSE_KINDS),
                Transaction.effective_date.between(start, end),
            )
            .group_by(root)
        ).all()
        return {cid: abs(int(t)) for cid, t in rows}

    current, previous = by_cat(period_from, period_to), by_cat(prev_from, prev_to)
    total = sum(current.values())
    if total == 0:
        return []
    cats = {c.id: c for c in db.scalars(select(Category).where(Category.id.in_([k for k in current if k])))}
    ranked = sorted(current.items(), key=lambda kv: kv[1], reverse=True)
    head, tail = ranked[:TOP_CATEGORIES], ranked[TOP_CATEGORIES:]

    slices = []
    for cid, amount in head:
        cat = cats.get(cid)
        prev = previous.get(cid, 0)
        slices.append(
            CategorySlice(
                category_id=cid,
                name=cat.name if cat else "Sem categoria",
                color=cat.color if cat else "#8A8A85",
                amount_cents=amount,
                share_pct=round(amount * 100 / total, 1),
                previous_cents=prev,
                change_pct=pct_change(amount, prev),
            )
        )
    if tail:
        amount = sum(a for _, a in tail)
        prev = sum(previous.get(cid, 0) for cid, _ in tail)
        slices.append(
            CategorySlice(
                category_id=None, name="Demais categorias", color="#8A8A85", amount_cents=amount,
                share_pct=round(amount * 100 / total, 1), previous_cents=prev, change_pct=pct_change(amount, prev),
            )
        )
    return slices
