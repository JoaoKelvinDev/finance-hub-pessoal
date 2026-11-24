"""Regras puras do livro de caixa."""

from datetime import date

from app.core.errors import DomainError

USER_KINDS = ("INCOME", "EXPENSE", "ADJUSTMENT")
# Somente estes kinds entram em receita/despesa; transferências e ajustes nunca.
INCOME_KINDS = ("INCOME",)
EXPENSE_KINDS = ("EXPENSE",)


def signed_amount(kind: str, amount_cents: int) -> int:
    """Receita/despesa recebem valor positivo e o sinal é derivado do kind; ajuste já vem assinado."""
    if kind == "ADJUSTMENT":
        if amount_cents == 0:
            raise DomainError("amount_invalid", "O ajuste não pode ser zero.")
        return amount_cents
    if amount_cents <= 0:
        raise DomainError("amount_invalid", "O valor deve ser maior que zero.")
    if kind == "INCOME":
        return amount_cents
    if kind == "EXPENSE":
        return -amount_cents
    raise DomainError("kind_invalid", f"Tipo de lançamento não permitido: {kind}.")


def validate_status_date(status: str, effective_date: date, today: date) -> None:
    if status == "POSTED" and effective_date > today:
        raise DomainError(
            "future_posted",
            "Lançamento efetivado não pode ter data futura. Use 'Previsto' para lançamentos futuros.",
        )


def transfer_legs(amount_cents: int) -> tuple[int, int]:
    if amount_cents <= 0:
        raise DomainError("amount_invalid", "O valor da transferência deve ser maior que zero.")
    return -amount_cents, amount_cents


def category_kind_for(kind: str) -> str | None:
    return {"INCOME": "INCOME", "EXPENSE": "EXPENSE"}.get(kind)
