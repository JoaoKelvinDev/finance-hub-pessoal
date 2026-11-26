"""Regras de negócio para contas da casa (bills) e recorrências."""

from datetime import date
from typing import Literal

from dateutil.relativedelta import relativedelta

from app.domains.support import today_local

RecurrenceFrequency = Literal["MONTHLY", "BIMONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL", "CUSTOM"]
RecurrenceStatus = Literal["ACTIVE", "PAUSED", "ENDED"]
BillInstallmentStatus = Literal["PENDING", "POSTED", "PAID", "REVERSED", "CANCELLED", "SKIPPED"]


def months_for_frequency(freq: RecurrenceFrequency) -> int:
    """Retorna o número de meses para uma dada frequência."""
    mapping = {
        "MONTHLY": 1,
        "BIMONTHLY": 2,
        "QUARTERLY": 3,
        "SEMIANNUAL": 6,
        "ANNUAL": 12,
    }
    return mapping.get(freq, 1)


def next_due_date(
    current_due: date,
    frequency: RecurrenceFrequency,
    custom_months_interval: int | None = None,
) -> date:
    """
    Calcula a próxima data de vencimento baseada na frequência.

    Para frequências fixas, usa relativedelta com months.
    Para CUSTOM, usa custom_months_interval.
    """
    if frequency == "CUSTOM":
        if not custom_months_interval or custom_months_interval <= 0:
            raise ValueError("custom_months_interval deve ser > 0 para frequência CUSTOM")
        months = custom_months_interval
    else:
        months = months_for_frequency(frequency)

    return current_due + relativedelta(months=months)


def generate_installment_dates(
    start_date: date,
    frequency: RecurrenceFrequency,
    day_of_month: int | None,
    end_date: date | None,
    custom_months_interval: int | None = None,
    max_count: int = 100,
) -> list[date]:
    """
    Gera lista de datas de vencimento para uma recorrência.

    - start_date: primeira data de vencimento
    - frequency: frequência da recorrência
    - day_of_month: dia do mês para vencimento (1-31). Se None, usa dia do start_date.
    - end_date: data limite (inclusive). Se None, gera até max_count parcelas.
    - custom_months_interval: intervalo em meses para frequência CUSTOM.
    - max_count: máximo de parcelas a gerar (segurança).

    Retorna lista de datas ordenadas.
    """
    if day_of_month is None:
        day_of_month = start_date.day

    # Valida dia do mês
    if not 1 <= day_of_month <= 31:
        raise ValueError("day_of_month deve estar entre 1 e 31")

    dates = []
    current = start_date

    for _ in range(max_count):
        # Ajusta o dia do mês se necessário (ex: 31 de fevereiro -> 28/29)
        try:
            current = current.replace(day=day_of_month)
        except ValueError:
            # Mês não tem esse dia (ex: 31 em abril), usa último dia do mês
            import calendar
            last_day = calendar.monthrange(current.year, current.month)[1]
            current = current.replace(day=last_day)

        if end_date and current > end_date:
            break

        dates.append(current)
        current = next_due_date(current, frequency, custom_months_interval)

    return dates


def calculate_installment_amounts(
    total_cents: int,
    installments_count: int,
) -> list[int]:
    """
    Divide o valor total em centavos exatos entre as parcelas.
    O resto da divisão vai para as primeiras parcelas.

    Exemplo: 1000 centavos / 3 = [334, 333, 333]
    """
    if installments_count <= 0:
        raise ValueError("installments_count deve ser > 0")
    if total_cents <= 0:
        raise ValueError("total_cents deve ser > 0")

    base = total_cents // installments_count
    remainder = total_cents % installments_count

    amounts = [base] * installments_count
    for i in range(remainder):
        amounts[i] += 1

    return amounts


def is_recurrence_active(
    recurrence_status: RecurrenceStatus,
    current_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> bool:
    """
    Verifica se uma recorrência está ativa para gerar parcelas.
    """
    if recurrence_status != "ACTIVE":
        return False

    if current_date is None:
        from app.domains.support import today_local  # data civil no fuso do app, não do servidor

        current_date = today_local()

    if start_date and current_date < start_date:
        return False

    return not (end_date and current_date > end_date)


def get_next_posting_dates(
    last_posted_due: date | None,
    recurrence_start: date,
    frequency: RecurrenceFrequency,
    day_of_month: int | None,
    end_date: date | None,
    custom_months_interval: int | None = None,
    max_lookahead: int = 600,
) -> list[date]:
    """
    Retorna as datas de vencimento que devem ser postadas (geradas) agora.

    - last_posted_due: última data de vencimento já postada (ou None se nunca postou)
    - recurrence_start: data de início da recorrência
    - max_lookahead: teto de ocorrências geradas desde o início (proteção contra laço;
      600 = 50 anos de mensais). As datas são limitadas a hoje, então o teto não corta
      recorrências longas (antes era 12 e a recorrência parava após a 12ª ocorrência).

    Retorna lista de datas que ainda não foram postadas mas cuja data de vencimento
    já chegou.
    """
    today = today_local()
    all_dates = generate_installment_dates(
        start_date=recurrence_start,
        frequency=frequency,
        day_of_month=day_of_month,
        end_date=min(end_date, today) if end_date else today,
        custom_months_interval=custom_months_interval,
        max_count=max_lookahead,
    )

    if last_posted_due is None:
        # Primeira postagem: pega todas as datas até hoje
        return [d for d in all_dates if d <= today]

    # Pega datas após a última postada e até hoje
    return [d for d in all_dates if last_posted_due < d <= today]


def validate_recurrence_consistency(
    frequency: RecurrenceFrequency,
    custom_months_interval: int | None,
) -> None:
    """Valida consistência entre frequency e custom_months_interval."""
    if frequency == "CUSTOM":
        if not custom_months_interval or custom_months_interval <= 0:
            raise ValueError("Frequência CUSTOM requer custom_months_interval > 0")
    else:
        if custom_months_interval is not None:
            raise ValueError("custom_months_interval só permitido para frequência CUSTOM")


def validate_day_of_month_for_frequency(
    frequency: RecurrenceFrequency,
    day_of_month: int | None,
) -> None:
    """Valida se day_of_month é compatível com a frequência."""
    if frequency in ("MONTHLY", "BIMONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL"):
        if day_of_month is None:
            raise ValueError(f"day_of_month é obrigatório para frequência {frequency}")
        if not 1 <= day_of_month <= 31:
            raise ValueError("day_of_month deve estar entre 1 e 31")
    elif frequency == "CUSTOM" and day_of_month is not None and not 1 <= day_of_month <= 31:
        raise ValueError("day_of_month deve estar entre 1 e 31")