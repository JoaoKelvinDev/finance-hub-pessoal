"""Regras de domínio para cartões: ciclos, competência, parcelamento, limite."""

import calendar
from datetime import date, datetime
from decimal import Decimal, ROUND_DOWN
from typing import Literal

from app.core.errors import DomainError


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _add_months(d: date, months: int) -> date:
    """Adiciona meses preservando o dia (ajusta para último dia do mês se necessário)."""
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, _last_day_of_month(y, m))
    return date(y, m, day)


def resolve_cycle_start(card_closing_day: int, purchase_date: date, policy: Literal["INCLUSIVE", "EXCLUSIVE"]) -> date:
    """
    Determina o início do ciclo (data de abertura da fatura) para uma compra.

    Regras:
    - O ciclo vai de `closing_day` do mês anterior até `closing_day` do mês atual (exclusivo ou inclusivo).
    - Se purchase_date.day == closing_day:
        - EXCLUSIVE (padrão): compra entra no PRÓXIMO ciclo (início = closing_day do mês atual)
        - INCLUSIVE: compra entra no ciclo ATUAL (início = closing_day do mês anterior)
    - Para dias > closing_day: compra entra no próximo ciclo.
    - Para dias < closing_day: compra entra no ciclo atual.

    Retorna a data de INÍCIO do ciclo (cycle_start_date).
    """
    closing = card_closing_day

    if purchase_date.day < closing:
        # Compra antes do fechamento: ciclo começou no closing_day do mês anterior
        return _add_months(date(purchase_date.year, purchase_date.month, closing), -1)
    elif purchase_date.day > closing:
        # Compra após o fechamento: ciclo começou no closing_day do mês atual
        return date(purchase_date.year, purchase_date.month, closing)
    else:
        # purchase_date.day == closing_day
        if policy == "EXCLUSIVE":
            # Fecha o ciclo no dia anterior; compra vai para o próximo
            return date(purchase_date.year, purchase_date.month, closing)
        else:  # INCLUSIVE
            # Compra no dia do fechamento entra no ciclo atual
            return _add_months(date(purchase_date.year, purchase_date.month, closing), -1)


def resolve_cycle_dates(cycle_start: date) -> tuple[date, date]:
    """
    Dado o início do ciclo, retorna (cycle_start, cycle_end_exclusive).
    cycle_end_exclusive é o primeiro dia do PRÓXIMO ciclo (exclusivo).
    """
    cycle_end = _add_months(cycle_start, 1)
    return cycle_start, cycle_end


def resolve_due_date(cycle_start: date, due_day: int, due_month_offset: Literal[0, 1]) -> date:
    """
    Calcula a data de vencimento da fatura.

    - due_month_offset = 0: vence no mesmo mês do ciclo (raro)
    - due_month_offset = 1 (padrão): vence no mês seguinte ao início do ciclo
    """
    target = _add_months(cycle_start, due_month_offset)
    # Se o dia de vencimento não existe no mês alvo (ex.: 31 em fevereiro), usa último dia
    last = _last_day_of_month(target.year, target.month)
    day = min(due_day, last)
    return date(target.year, target.month, day)


def split_installments(total_cents: int, count: int) -> list[int]:
    """
    Divide o total em centavos em N parcelas sem perda.

    Ex.: 10000 centavos / 3 = [3334, 3333, 3333] (soma = 10000)
    """
    if count <= 1:
        return [total_cents]

    base = total_cents // count
    remainder = total_cents % count
    # As primeiras `remainder` parcelas recebem +1 centavo
    return [base + 1 if i < remainder else base for i in range(count)]


def calculate_used_limit(
    purchases: list,  # CardPurchase objects
    payments: list,   # StatementPayment objects linked to this card's statements
    installments: list,  # CardInstallment objects
    limit_cents: int,
) -> tuple[int, int]:
    """
    Calcula limite utilizado e disponível.

    Limite utilizado = soma de parcelas NÃO estornadas/canceladas de compras ATIVAS
    (parcelas PENDING + POSTED + PAID, exceto REVERSED/CANCELLED)
    """
    # Esta função é simplificada; a implementação real deve consultar o banco
    # com queries apropriadas. Mantida aqui para referência da regra.
    used = sum(
        inst.amount_cents
        for inst in installments
        if inst.status not in ("REVERSED", "CANCELLED")
        and any(p.id == inst.purchase_id and p.status == "ACTIVE" for p in purchases)
    )
    available = limit_cents - used
    return used, available


def validate_closing_day(closing_day: int) -> None:
    if not 1 <= closing_day <= 28:
        raise DomainError("closing_day_invalid", "Dia de fechamento deve ser entre 1 e 28.")


def validate_due_day(due_day: int) -> None:
    if not 1 <= due_day <= 28:
        raise DomainError("due_day_invalid", "Dia de vencimento deve ser entre 1 e 28.")


def validate_due_month_offset(offset: int) -> None:
    if offset not in (0, 1):
        raise DomainError("due_month_offset_invalid", "Offset de vencimento deve ser 0 ou 1.")


def validate_purchase_date_not_future(purchase_date: date, today: date) -> None:
    """Compras não podem ser cadastradas no futuro (política de MVP)."""
    if purchase_date > today:
        raise DomainError("future_purchase", "Não é permitido cadastrar compras com data futura.")


def derive_statement_status(paid_cents: int, total_cents: int, due_date: date, today: date) -> str:
    """Deriva status da fatura baseado em valores e datas."""
    if total_cents == 0:
        return "OPEN"
    if paid_cents <= 0:
        return "OVERDUE" if due_date < today else "OPEN"
    if paid_cents >= total_cents:
        return "PAID"
    return "PARTIALLY_PAID"