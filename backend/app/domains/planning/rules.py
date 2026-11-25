"""Regras puras do planejamento: mapeamento de categorias e status de orçamento."""

# A conta da casa guarda a categoria no seu próprio domínio (WATER, RENT...).
# O orçamento usa as categorias do catálogo; o mapeamento abaixo liga as duas coisas.
BILL_CATEGORY_TO_CATEGORY_NAME = {
    "RENT": "Aluguel",
    "CONDOMINIUM": "Condomínio",
    "ELECTRICITY": "Energia",
    "WATER": "Água",
    "GAS": "Gás",
    "INTERNET": "Internet",
    "PHONE": "Telefone",
    "INSURANCE": "Outros",
    "SUBSCRIPTION": "Outros",
    "OTHER": "Outros",
}

# Avisos de orçamento: 80% (atenção) e 100% (estourado).
WARNING_PCT = 80.0
OVER_PCT = 100.0


def budget_status(used_cents: int, limit_cents: int) -> str:
    """OK abaixo de 80%, WARNING entre 80% e 100%, OVER acima ou igual a 100%."""
    if limit_cents <= 0:
        return "OVER"
    pct = used_cents * 100 / limit_cents
    if pct >= OVER_PCT:
        return "OVER"
    if pct >= WARNING_PCT:
        return "WARNING"
    return "OK"


def progress_pct(used_cents: int, limit_cents: int) -> float:
    """Progresso em % (arredondado para uma casa). Teto zero não divide."""
    if limit_cents <= 0:
        return 0.0
    return round(used_cents * 100 / limit_cents, 1)
