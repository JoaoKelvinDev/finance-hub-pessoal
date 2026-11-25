"""Regras puras do rateio: a soma das partes é SEMPRE igual ao total, em centavos exatos."""

from app.core.errors import DomainError
from app.domains.money import split_cents

FULL_BP = 10_000  # 100% em pontos-base


def compute_shares(
    total_cents: int,
    method: str,
    include_owner: bool,
    amounts: list[int | None],
    percents_bp: list[int | None],
) -> tuple[int, list[int]]:
    """Retorna (parte do proprietário, partes dos participantes na ordem recebida).

    - EQUAL: divide entre participantes (+ proprietário se include_owner). Centavo
      que sobrar fica com o proprietário quando ele participa; senão, com os primeiros.
    - FIXED: valores informados; o proprietário fica com a diferença.
    - PERCENT: percentuais em pontos-base; o proprietário fica com a diferença.
      Sem o proprietário, os percentuais devem somar 100% e o arredondamento é
      distribuído pelo maior resto (soma exata).
    """
    n = len(amounts)
    if n == 0:
        raise DomainError("split_no_participants", "Informe ao menos uma pessoa no rateio.")
    if total_cents <= 0:
        raise DomainError("split_total_invalid", "O valor a ratear deve ser maior que zero.")

    if method == "EQUAL":
        parts = split_cents(total_cents, n + (1 if include_owner else 0))
        if include_owner:
            return parts[0], parts[1:]
        return 0, parts

    if method == "FIXED":
        if any(a is None or a <= 0 for a in amounts):
            raise DomainError("split_amount_invalid", "Informe um valor maior que zero para cada pessoa.")
        shares = [int(a) for a in amounts]  # type: ignore[arg-type]
        owner = total_cents - sum(shares)
        if owner < 0:
            raise DomainError("split_exceeds_total", "A soma das partes passa do valor total.")
        if not include_owner and owner != 0:
            raise DomainError("split_sum_mismatch", "Sem a sua parte, a soma das partes deve ser igual ao total.")
        if include_owner and owner == 0:
            raise DomainError("split_owner_zero", "Sua parte ficou zerada; desmarque 'incluir minha parte'.")
        return owner, shares

    if method == "PERCENT":
        if any(p is None or p <= 0 or p > FULL_BP for p in percents_bp):
            raise DomainError("split_percent_invalid", "Cada percentual deve estar entre 0,01% e 100%.")
        bps = [int(p) for p in percents_bp]  # type: ignore[arg-type]
        total_bp = sum(bps)
        if total_bp > FULL_BP:
            raise DomainError("split_exceeds_total", "Os percentuais somam mais de 100%.")
        if not include_owner and total_bp != FULL_BP:
            raise DomainError("split_sum_mismatch", "Sem a sua parte, os percentuais devem somar 100%.")
        if include_owner and total_bp == FULL_BP:
            raise DomainError("split_owner_zero", "Sua parte ficou zerada; desmarque 'incluir minha parte'.")

        raw = [total_cents * bp for bp in bps]
        shares = [r // FULL_BP for r in raw]
        if not include_owner:
            # Maior resto: distribui os centavos que faltam sem perder exatidão.
            missing = total_cents - sum(shares)
            order = sorted(range(n), key=lambda i: raw[i] % FULL_BP, reverse=True)
            for i in order[:missing]:
                shares[i] += 1
        if any(s <= 0 for s in shares):
            raise DomainError("split_share_zero", "Alguma parte ficou zerada; aumente o percentual.")
        return total_cents - sum(shares), shares

    raise DomainError("split_method_invalid", f"Método de rateio inválido: {method}.")
