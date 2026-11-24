from datetime import date

import pytest

from app.core.errors import DomainError
from app.domains.ledger import rules
from app.domains.money import format_brl, parse_brl, pct_change, split_cents


def test_split_100_em_3_parcelas():
    assert split_cents(10000, 3) == [3334, 3333, 3333]


@pytest.mark.parametrize("total,n", [(10000, 3), (1, 7), (299999, 10), (60000, 6), (0, 4)])
def test_split_soma_exata(total, n):
    parts = split_cents(total, n)
    assert sum(parts) == total and len(parts) == n
    assert max(parts) - min(parts) <= 1


@pytest.mark.parametrize(
    "text,cents",
    [("1.234,56", 123456), ("10", 1000), ("0,5", 50), ("R$ 99,90", 9990), ("-3,5", -350), ("1234,00", 123400)],
)
def test_parse_brl(text, cents):
    assert parse_brl(text) == cents


@pytest.mark.parametrize("bad", ["1,234.56", "abc", "1,999", ""])
def test_parse_brl_invalido(bad):
    with pytest.raises(ValueError):
        parse_brl(bad)


def test_format_brl():
    assert format_brl(123456) == "R$ 1.234,56"
    assert format_brl(-5) == "-R$ 0,05"


def test_variacao_sem_denominador_e_na():
    assert pct_change(100, 0) is None
    assert pct_change(150, 100) == 50.0


def test_sinal_derivado_do_tipo():
    assert rules.signed_amount("INCOME", 500) == 500
    assert rules.signed_amount("EXPENSE", 500) == -500
    assert rules.signed_amount("ADJUSTMENT", -20) == -20
    with pytest.raises(DomainError):
        rules.signed_amount("EXPENSE", -500)
    with pytest.raises(DomainError):
        rules.signed_amount("TRANSFER_IN", 500)


def test_efetivado_nao_pode_ser_futuro():
    with pytest.raises(DomainError):
        rules.validate_status_date("POSTED", date(2030, 1, 1), date(2026, 11, 24))
    rules.validate_status_date("PLANNED", date(2030, 1, 1), date(2026, 11, 24))


def test_pernas_da_transferencia_somam_zero():
    out_leg, in_leg = rules.transfer_legs(50000)
    assert out_leg + in_leg == 0 and out_leg < 0
