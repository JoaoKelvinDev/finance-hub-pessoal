"""Planejamento: orçamentos por categoria/período e metas com aportes rastreáveis.

Métricas do orçamento (documentadas em docs/REPORTS.md):

- `spent_cents` (realizado)
  - base CASH: despesas manuais efetivadas no período + o que saiu da conta em
    cartão no período (atribuído por categoria, proporcional ao valor pago) +
    parcelas de contas da casa pagas no período.
  - base COMPETENCE: consumo atribuído ao período: compras de cartão pela data
    da compra + parcelas de contas pelo vencimento + despesas manuais.
- `committed_cents` (comprometido): só na base CASH. Obrigações que ainda vão
  sair do caixa dentro do período: parcelas em aberto e faturas em aberto com
  vencimento no período.
- `used_cents` = realizado (+ comprometido na base caixa), `remaining_cents` =
  teto − used, `progress_pct` = used / teto.

Nada aqui soma transferência interna: aporte entre contas próprias não é gasto.
"""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError, NotFound
from app.domains.ledger import service as ledger
from app.domains.ledger.rules import EXPENSE_KINDS
from app.domains.planning import rules
from app.domains.support import audit, run_idempotent, snapshot, today_local
from app.models import (
    Bill,
    BillInstallment,
    Budget,
    CardInstallment,
    CardPurchase,
    CardStatement,
    Category,
    Goal,
    GoalAllocation,
    Transaction,
)
from app.schemas.finance import TransferCreate
from app.schemas.planning import (
    BudgetCreate,
    BudgetOut,
    BudgetUpdate,
    GoalAllocationCreate,
    GoalAllocationOut,
    GoalContributionCreate,
    GoalCreate,
    GoalOut,
    GoalUpdate,
)

BUDGET_AUDIT_FIELDS = ("category_id", "period_start", "period_end", "limit_cents", "basis", "notes")
GOAL_AUDIT_FIELDS = ("title", "target_cents", "target_date", "state", "notes")


# ---------- categorias ----------

def category_scope(db: Session, category_id: UUID | None) -> list[UUID] | None:
    """IDs da categoria e das filhas. None = todas as categorias (orçamento geral)."""
    if category_id is None:
        return None
    ids = {category_id}
    frontier = [category_id]
    while frontier:
        parent = frontier.pop()
        for child in db.scalars(select(Category.id).where(Category.parent_id == parent)).all():
            if child not in ids:
                ids.add(child)
                frontier.append(child)
    return list(ids)


def _expense_category(db: Session, category_id: UUID | None) -> Category | None:
    if category_id is None:
        return None
    cat = db.get(Category, category_id)
    if cat is None:
        raise NotFound("Categoria")
    if cat.kind != "EXPENSE":
        raise DomainError("category_kind", "Orçamento só se aplica a categorias de despesa.")
    return cat


def _bill_category_ids(db: Session) -> dict[str, UUID]:
    """Categoria da conta da casa (WATER, RENT...) -> id da categoria do catálogo."""
    names = set(rules.BILL_CATEGORY_TO_CATEGORY_NAME.values())
    rows = db.execute(select(Category.id, Category.name).where(Category.name.in_(names))).all()
    by_name = {name: cid for cid, name in rows}
    return {
        bill_cat: by_name[name]
        for bill_cat, name in rules.BILL_CATEGORY_TO_CATEGORY_NAME.items()
        if name in by_name
    }


# ---------- consumo ----------

def _statement_total(db: Session, statement_id: UUID) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(CardInstallment.amount_cents), 0)).where(
            CardInstallment.statement_id == statement_id,
            CardInstallment.status.notin_(("REVERSED", "CANCELLED")),
        )
    )
    return int(total or 0)


def _bill_installments(db: Session, start: date, end: date) -> list[tuple[int, str, date, str]]:
    """(valor, categoria da conta, vencimento, status) das parcelas no período."""
    return [
        (int(amount), category, due, status)
        for amount, category, due, status in db.execute(
            select(BillInstallment.amount_cents, Bill.category, BillInstallment.due_date, BillInstallment.status)
            .join(Bill, Bill.id == BillInstallment.bill_id)
            .where(BillInstallment.due_date.between(start, end))
        ).all()
    ]


Totals = dict[UUID | None, int]


def _add(totals: Totals, category_id: UUID | None, cents: int) -> None:
    if cents:
        totals[category_id] = totals.get(category_id, 0) + cents


def _manual_by_category(db: Session, start: date, end: date, totals: Totals) -> None:
    """Despesas manuais efetivadas (sem cartão e sem pagamento de conta da casa)."""
    for category_id, total in db.execute(
        select(Transaction.category_id, func.sum(Transaction.amount_cents))
        .where(
            Transaction.status == "POSTED",
            Transaction.kind.in_(EXPENSE_KINDS),
            Transaction.effective_date.between(start, end),
            or_(
                Transaction.source_type.is_(None),
                Transaction.source_type.notin_(("statement_payment", "bill_payment")),
            ),
        )
        .group_by(Transaction.category_id)
    ).all():
        _add(totals, category_id, abs(int(total or 0)))


def _card_cash_by_category(db: Session, start: date, end: date, totals: Totals) -> None:
    """Cartão em regime de caixa: o pagamento da fatura é o evento de caixa.

    A atribuição por categoria é proporcional ao quanto foi pago da fatura, em centavos
    inteiros (arredonda para baixo por parcela).
    """
    rows = db.execute(
        select(Transaction.source_id, func.sum(Transaction.amount_cents))
        .where(
            Transaction.status == "POSTED",
            Transaction.source_type == "statement_payment",
            Transaction.effective_date.between(start, end),
        )
        .group_by(Transaction.source_id)
    ).all()
    for statement_id, paid in rows:
        if statement_id is None:
            continue
        stmt_total = _statement_total(db, statement_id)
        if stmt_total <= 0:
            continue
        paid_cents = min(abs(int(paid or 0)), stmt_total)
        for amount, category_id in db.execute(
            select(CardInstallment.amount_cents, CardPurchase.category_id)
            .join(CardPurchase, CardPurchase.id == CardInstallment.purchase_id)
            .where(
                CardInstallment.statement_id == statement_id,
                CardInstallment.status.notin_(("REVERSED", "CANCELLED")),
            )
        ).all():
            _add(totals, category_id, int(amount) * paid_cents // stmt_total)


def _card_competence_by_category(db: Session, start: date, end: date, totals: Totals) -> None:
    """Cartão em regime de competência: o consumo do período é a compra."""
    for category_id, total in db.execute(
        select(CardPurchase.category_id, func.sum(CardInstallment.amount_cents))
        .join(CardPurchase, CardPurchase.id == CardInstallment.purchase_id)
        .where(
            CardPurchase.purchased_on.between(start, end),
            CardPurchase.status == "ACTIVE",
            CardInstallment.status.notin_(("REVERSED", "CANCELLED")),
        )
        .group_by(CardPurchase.category_id)
    ).all():
        _add(totals, category_id, int(total or 0))


def _bill_paid_by_category(db: Session, start: date, end: date, totals: Totals) -> None:
    """Parcelas de contas da casa pagas no período (data do pagamento, no fuso do app)."""
    from zoneinfo import ZoneInfo

    zone = ZoneInfo(get_settings().app_timezone)
    lo = datetime.combine(start, time.min, tzinfo=zone).astimezone(UTC)
    hi = datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
    mapping = _bill_category_ids(db)
    for amount, bill_category, paid_at in db.execute(
        select(BillInstallment.amount_cents, Bill.category, BillInstallment.paid_at)
        .join(Bill, Bill.id == BillInstallment.bill_id)
        .where(
            BillInstallment.status == "PAID",
            BillInstallment.paid_at.is_not(None),
            BillInstallment.paid_at >= lo,
            BillInstallment.paid_at < hi,
        )
    ).all():
        if start <= paid_at.astimezone(zone).date() <= end:
            _add(totals, mapping.get(bill_category), int(amount))


def _bill_competence_by_category(db: Session, start: date, end: date, totals: Totals) -> None:
    """Contas da casa em competência: a parcela conta pelo vencimento."""
    mapping = _bill_category_ids(db)
    for amount, bill_category, _due, status in _bill_installments(db, start, end):
        if status not in ("CANCELLED", "SKIPPED", "REVERSED"):
            _add(totals, mapping.get(bill_category), amount)


def consumption_by_category(db: Session, start: date, end: date, basis: str) -> Totals:
    """Consumo do período por categoria (None = sem categoria).

    Fonte única para orçamentos e relatórios: os dois sempre mostram os mesmos números.
    Transferências, empréstimos e acertos com terceiros nunca entram.
    """
    totals: Totals = {}
    _manual_by_category(db, start, end, totals)
    if basis == "COMPETENCE":
        _card_competence_by_category(db, start, end, totals)
        _bill_competence_by_category(db, start, end, totals)
    else:
        _card_cash_by_category(db, start, end, totals)
        _bill_paid_by_category(db, start, end, totals)
    return totals


def _committed_cents(db: Session, scope: list[UUID] | None, start: date, end: date) -> int:
    """Obrigações ainda em aberto que vencem no período (base caixa)."""
    mapping = _bill_category_ids(db)
    total = 0
    for amount, bill_category, _due, status in _bill_installments(db, start, end):
        if status not in ("PENDING", "POSTED"):
            continue
        category_id = mapping.get(bill_category)
        if scope is not None and (category_id is None or category_id not in scope):
            continue
        total += amount

    # Faturas em aberto: o pagamento da fatura é a saída de caixa.
    rows = db.execute(
        select(CardStatement.id, CardStatement.paid_cents)
        .where(
            CardStatement.due_date.between(start, end),
            CardStatement.status.notin_(("PAID", "CANCELLED")),
        )
    ).all()
    for statement_id, paid in rows:
        stmt_total = _statement_total(db, statement_id)
        open_cents = stmt_total - int(paid or 0)
        if open_cents <= 0:
            continue
        for _amount, category_id in db.execute(
            select(CardInstallment.amount_cents, CardPurchase.category_id)
            .join(CardPurchase, CardPurchase.id == CardInstallment.purchase_id)
            .where(
                CardInstallment.statement_id == statement_id,
                CardInstallment.status.notin_(("REVERSED", "CANCELLED")),
            )
        ).all():
            if scope is not None and category_id not in scope:
                continue
            total += open_cents * int(_amount) // stmt_total
    return total


def budget_metrics(db: Session, budget: Budget) -> tuple[int, int]:
    """(realizado, comprometido) do orçamento."""
    scope = category_scope(db, budget.category_id)
    start, end = budget.period_start, budget.period_end
    totals = consumption_by_category(db, start, end, budget.basis)
    spent = sum(totals.values()) if scope is None else sum(v for k, v in totals.items() if k in scope)
    if budget.basis == "COMPETENCE":
        return spent, 0
    return spent, _committed_cents(db, scope, start, end)


def budget_out(db: Session, budget: Budget) -> BudgetOut:
    spent, committed = budget_metrics(db, budget)
    used = spent + committed
    limit = budget.limit_cents
    formula = (
        "Realizado: consumo do período por competência (compras de cartão pela compra, "
        "contas da casa pelo vencimento, despesas manuais pela data)."
        if budget.basis == "COMPETENCE"
        else "Realizado: o que foi pago no período (despesas, cartão pela fatura, contas da casa). "
        "Comprometido: obrigações em aberto que vencem no período."
    )
    return BudgetOut(
        id=budget.id,
        category_id=budget.category_id,
        category_name=budget.category.name if budget.category else None,
        period_start=budget.period_start,
        period_end=budget.period_end,
        limit_cents=limit,
        basis=budget.basis,
        notes=budget.notes,
        spent_cents=spent,
        committed_cents=committed,
        used_cents=used,
        remaining_cents=limit - used,
        progress_pct=rules.progress_pct(used, limit),
        status=rules.budget_status(used, limit),
        formula=formula,
    )


# ---------- orçamentos ----------

def list_budgets(db: Session) -> list[BudgetOut]:
    budgets = db.scalars(select(Budget).order_by(Budget.period_start.desc(), Budget.created_at.desc())).all()
    return [budget_out(db, b) for b in budgets]


def get_budget(db: Session, budget_id: UUID) -> Budget:
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise NotFound("Orçamento")
    return budget


def create_budget(db: Session, data: BudgetCreate, request_id: str | None) -> UUID:
    _expense_category(db, data.category_id)
    existing = db.scalar(
        select(Budget.id).where(
            Budget.category_id == data.category_id,
            Budget.period_start == data.period_start,
            Budget.period_end == data.period_end,
        )
    )
    if existing:
        raise DomainError(
            "budget_exists",
            "Já existe um orçamento para esta categoria neste período.",
            status_code=409,
        )

    budget = Budget(
        category_id=data.category_id,
        period_start=data.period_start,
        period_end=data.period_end,
        limit_cents=data.limit_cents,
        basis=data.basis,
        notes=data.notes,
    )
    db.add(budget)
    db.flush()
    audit(db, "budget", budget.id, "create", None, snapshot(budget, BUDGET_AUDIT_FIELDS), request_id)
    return budget.id


def update_budget(db: Session, budget_id: UUID, data: BudgetUpdate, request_id: str | None) -> Budget:
    budget = get_budget(db, budget_id)
    before = snapshot(budget, BUDGET_AUDIT_FIELDS)
    payload = data.model_dump(exclude_none=True)
    if "category_id" in payload:
        _expense_category(db, payload["category_id"])
    for field, value in payload.items():
        setattr(budget, field, value)
    db.flush()
    audit(db, "budget", budget.id, "update", before, snapshot(budget, BUDGET_AUDIT_FIELDS), request_id)
    return budget


def delete_budget(db: Session, budget_id: UUID, request_id: str | None) -> None:
    budget = get_budget(db, budget_id)
    before = snapshot(budget, BUDGET_AUDIT_FIELDS)
    db.delete(budget)
    db.flush()
    audit(db, "budget", budget_id, "delete", before, None, request_id)


# ---------- metas ----------

def _allocated_cents(db: Session, goal: Goal) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(GoalAllocation.amount_cents), 0)).where(
            GoalAllocation.goal_id == goal.id, GoalAllocation.reversed_at.is_(None)
        )
    )
    return int(total or 0)


def goal_out(db: Session, goal: Goal) -> GoalOut:
    allocated = _allocated_cents(db, goal)
    remaining = max(goal.target_cents - allocated, 0)
    pct = round(allocated * 100 / goal.target_cents, 1) if goal.target_cents else 0.0
    return GoalOut(
        id=goal.id,
        title=goal.title,
        target_cents=goal.target_cents,
        target_date=goal.target_date,
        state=goal.state,
        notes=goal.notes,
        allocated_cents=allocated,
        remaining_cents=remaining,
        progress_pct=pct,
        allocations=[
            GoalAllocationOut(
                id=a.id,
                amount_cents=a.amount_cents,
                allocated_on=a.allocated_on,
                transfer_reference=a.transfer_reference,
                transfer_group_id=a.transfer_group_id,
                notes=a.notes,
                reversed_at=a.reversed_at,
                reverse_reason=a.reverse_reason,
                created_at=a.created_at,
            )
            for a in goal.allocations
        ],
    )


def list_goals(db: Session) -> list[GoalOut]:
    goals = db.scalars(select(Goal).order_by(Goal.state, Goal.created_at.desc())).all()
    return [goal_out(db, g) for g in goals]


def get_goal(db: Session, goal_id: UUID) -> Goal:
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise NotFound("Meta")
    return goal


def create_goal(db: Session, data: GoalCreate, request_id: str | None) -> UUID:
    goal = Goal(
        title=data.title,
        target_cents=data.target_cents,
        target_date=data.target_date,
        notes=data.notes,
    )
    db.add(goal)
    db.flush()
    audit(db, "goal", goal.id, "create", None, snapshot(goal, GOAL_AUDIT_FIELDS), request_id)
    return goal.id


def update_goal(db: Session, goal_id: UUID, data: GoalUpdate, request_id: str | None) -> Goal:
    goal = get_goal(db, goal_id)
    before = snapshot(goal, GOAL_AUDIT_FIELDS)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(goal, field, value)
    db.flush()
    audit(db, "goal", goal.id, "update", before, snapshot(goal, GOAL_AUDIT_FIELDS), request_id)
    return goal


def cancel_goal(db: Session, goal_id: UUID, reason: str, request_id: str | None) -> Goal:
    goal = get_goal(db, goal_id)
    if goal.state == "CANCELLED":
        raise DomainError("already_cancelled", "Esta meta já foi cancelada.", status_code=409)
    before = snapshot(goal, GOAL_AUDIT_FIELDS)
    goal.state = "CANCELLED"
    goal.cancelled_at = datetime.now(tz=UTC)
    goal.cancel_reason = reason
    db.flush()
    audit(db, "goal", goal.id, "cancel", before, snapshot(goal, GOAL_AUDIT_FIELDS), request_id)
    return goal


def allocate_goal(db: Session, goal_id: UUID, data: GoalAllocationCreate, request_id: str | None) -> tuple[UUID, bool]:
    """Registra um aporte na meta. Não movimenta o caixa."""
    payload = {"goal_id": str(goal_id), **data.model_dump(exclude={"idempotency_key"})}

    def _create() -> UUID:
        goal = get_goal(db, goal_id)
        if goal.state == "CANCELLED":
            raise DomainError("goal_cancelled", "Não é possível aportar em uma meta cancelada.", status_code=409)
        if data.allocated_on > today_local():
            raise DomainError("future_allocation", "O aporte não pode ter data futura.")
        allocation = GoalAllocation(
            goal=goal,
            amount_cents=data.amount_cents,
            allocated_on=data.allocated_on,
            transfer_reference=data.transfer_reference,
            notes=data.notes,
        )
        db.add(allocation)
        db.flush()
        _refresh_goal_state(db, goal)
        db.refresh(goal)
        audit(
            db, "goal_allocation", allocation.id, "create", None,
            {"goal_id": str(goal.id), "amount_cents": data.amount_cents, "allocated_on": data.allocated_on.isoformat()},
            request_id,
        )
        return allocation.id

    return run_idempotent(db, data.idempotency_key, "goal.allocation.create", payload, _create)


def contribute_goal(db: Session, goal_id: UUID, data: GoalContributionCreate, request_id: str | None) -> tuple[UUID, bool]:
    """Aporte com transferência real entre contas próprias (não é receita nem despesa)."""
    payload = {"goal_id": str(goal_id), **data.model_dump(exclude={"idempotency_key"})}

    def _create() -> UUID:
        goal = get_goal(db, goal_id)
        if goal.state == "CANCELLED":
            raise DomainError("goal_cancelled", "Não é possível aportar em uma meta cancelada.", status_code=409)
        if data.effective_date > today_local():
            raise DomainError("future_allocation", "O aporte não pode ter data futura.")
        group, _created = ledger.transfer(
            db,
            TransferCreate(
                from_account_id=data.from_account_id,
                to_account_id=data.to_account_id,
                amount_cents=data.amount_cents,
                effective_date=data.effective_date,
                description=f"Aporte para meta {goal.title}",
                idempotency_key=None,
            ),
            request_id,
        )
        allocation = GoalAllocation(
            goal=goal,
            amount_cents=data.amount_cents,
            allocated_on=data.effective_date,
            transfer_reference=str(group),
            transfer_group_id=group,
            notes=data.notes,
        )
        db.add(allocation)
        db.flush()
        _refresh_goal_state(db, goal)
        db.refresh(goal)
        audit(
            db, "goal_allocation", allocation.id, "create", None,
            {
                "goal_id": str(goal.id),
                "amount_cents": data.amount_cents,
                "allocated_on": data.effective_date.isoformat(),
                "transfer_group_id": str(group),
            },
            request_id,
        )
        return allocation.id

    return run_idempotent(db, data.idempotency_key, "goal.contribution.create", payload, _create)


def _refresh_goal_state(db: Session, goal: Goal) -> None:
    """Meta atingida vira ACHIEVED; cancelada não volta."""
    if goal.state == "CANCELLED":
        return
    allocated = _allocated_cents(db, goal)
    goal.state = "ACHIEVED" if allocated >= goal.target_cents else "ACTIVE"
    # Grava já: quem chama costuma fazer db.refresh(goal), que descartaria a mudança não enviada.
    db.flush()


def reverse_allocation(
    db: Session, goal_id: UUID, allocation_id: UUID, reason: str, request_id: str | None
) -> Goal:
    """Estorna um aporte. Se ele moveu dinheiro entre contas, a transferência é cancelada junto."""
    goal = get_goal(db, goal_id)
    allocation = db.get(GoalAllocation, allocation_id)
    if allocation is None or allocation.goal_id != goal.id:
        raise NotFound("Aporte")
    if allocation.reversed_at is not None:
        raise DomainError("already_reversed", "Este aporte já foi estornado.", status_code=409)
    if allocation.transfer_group_id is not None:
        legs = db.scalars(
            select(Transaction).where(
                Transaction.transfer_group_id == allocation.transfer_group_id, Transaction.status != "CANCELLED"
            )
        ).all()
        if legs:
            ledger.cancel_transaction(db, legs[0].id, f"Estorno de aporte: {reason}"[:200], request_id)
    allocation.reversed_at = datetime.now(tz=UTC)
    allocation.reverse_reason = reason
    db.flush()
    _refresh_goal_state(db, goal)
    audit(
        db, "goal_allocation", allocation.id, "reverse", None,
        {"goal_id": str(goal.id), "reason": reason, "transfer_group_id": str(allocation.transfer_group_id or "")},
        request_id,
    )
    db.flush()
    return goal


def _month_bounds(month: str) -> tuple[date, date]:
    import calendar

    y, m = (int(x) for x in month.split("-"))
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def copy_budgets(db: Session, from_month: str, to_month: str, request_id: str | None) -> tuple[int, int]:
    """Repete os tetos dos orçamentos do mês inteiro de origem no mês de destino.

    Só copia orçamentos que cobrem exatamente o mês de origem; os que já existem no destino são mantidos.
    """
    if from_month == to_month:
        raise DomainError("same_month", "Escolha meses diferentes para copiar.")
    src_start, src_end = _month_bounds(from_month)
    dst_start, dst_end = _month_bounds(to_month)
    sources = db.scalars(
        select(Budget).where(Budget.period_start == src_start, Budget.period_end == src_end)
    ).all()
    created = skipped = 0
    for b in sources:
        exists = db.scalar(
            select(Budget.id).where(
                Budget.category_id.is_(None) if b.category_id is None else Budget.category_id == b.category_id,
                Budget.period_start == dst_start,
                Budget.period_end == dst_end,
            )
        )
        if exists:
            skipped += 1
            continue
        new = Budget(
            category_id=b.category_id,
            period_start=dst_start,
            period_end=dst_end,
            limit_cents=b.limit_cents,
            basis=b.basis,
            notes=b.notes,
        )
        db.add(new)
        db.flush()
        audit(db, "budget", new.id, "copy", None, {"from_budget_id": str(b.id), **snapshot(new, BUDGET_AUDIT_FIELDS)}, request_id)
        created += 1
    return created, skipped


def active_budgets_today(db: Session) -> list[BudgetOut]:
    """Orçamentos cujo período contém hoje — usados pela central de alertas."""
    today = today_local()
    budgets = db.scalars(select(Budget).where(Budget.period_start <= today, Budget.period_end >= today)).all()
    return [budget_out(db, b) for b in budgets]
