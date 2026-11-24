"""Aritmética monetária em centavos inteiros. Nunca usa float."""

import re

_BRL = re.compile(r"^\s*(-)?\s*(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{1,2}))?\s*$")


def parse_brl(text: str) -> int:
    """'1.234,56' -> 123456 ; '10' -> 1000 ; '-3,5' -> -350."""
    m = _BRL.match(text)
    if not m:
        raise ValueError(f"valor monetário inválido: {text!r}")
    sign, integer, frac = m.groups()
    cents = int(integer.replace(".", "")) * 100 + int((frac or "0").ljust(2, "0"))
    return -cents if sign else cents


def format_brl(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    reais, cent = divmod(abs(cents), 100)
    return f"{sign}R$ {reais:,}".replace(",", ".") + f",{cent:02d}"


def split_cents(total_cents: int, parts: int) -> list[int]:
    """Divide sem perda: o resto vai +1 centavo para as primeiras partes."""
    if parts < 1:
        raise ValueError("parts deve ser >= 1")
    if total_cents < 0:
        raise ValueError("total deve ser >= 0")
    base, remainder = divmod(total_cents, parts)
    return [base + 1 if i < remainder else base for i in range(parts)]


def pct_change(current: int, previous: int) -> float | None:
    """Variação percentual; None (N/A) quando o denominador anterior é zero."""
    if previous == 0:
        return None
    return round((current - previous) * 100 / abs(previous), 1)
