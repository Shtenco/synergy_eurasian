from decimal import Decimal

import pytest

from sinergy_eurasian import (
    ModelInvariantError,
    capacity_violations,
    leontief_gross_output,
)


def test_two_sector_leontief_baseline() -> None:
    output = leontief_gross_output(
        [["0.1", "0.2"], ["0.3", "0.1"]],
        ["100", "80"],
    )
    assert output[0].quantize(Decimal("0.000001")) == Decimal("141.333333")
    assert output[1].quantize(Decimal("0.000001")) == Decimal("136.000000")


def test_zero_technical_coefficients_return_final_demand() -> None:
    output = leontief_gross_output(
        [["0", "0"], ["0", "0"]],
        ["25", "40"],
    )
    assert output == [Decimal("25"), Decimal("40")]


def test_non_square_matrix_fails_closed() -> None:
    with pytest.raises(ModelInvariantError):
        leontief_gross_output([["0.1"]], ["10", "20"])


def test_singular_system_fails_closed() -> None:
    with pytest.raises(ModelInvariantError):
        leontief_gross_output([["1", "0"], ["0", "0"]], ["1", "1"])


def test_capacity_violation_is_reported_not_clipped() -> None:
    violations = capacity_violations(
        ["141.333333", "136"],
        ["130", "150"],
    )
    assert len(violations) == 1
    assert violations[0].sector == 0
    assert violations[0].requested_output == Decimal("141.333333")
    assert violations[0].capacity == Decimal("130")
    assert violations[0].excess == Decimal("11.333333")


def test_capacity_check_accepts_feasible_output() -> None:
    assert capacity_violations(["100", "80"], ["100", "100"]) == []
