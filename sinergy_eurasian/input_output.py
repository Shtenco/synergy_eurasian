from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext
from typing import Sequence


getcontext().prec = 50
ZERO = Decimal("0")
ONE = Decimal("1")


class ModelInvariantError(ValueError):
    """Raised when the reference EIIOM input is structurally invalid."""


def _d(value: Decimal | int | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True)
class CapacityViolation:
    sector: int
    requested_output: Decimal
    capacity: Decimal

    @property
    def excess(self) -> Decimal:
        return self.requested_output - self.capacity


def _validate_system(
    technical_coefficients: Sequence[Sequence[Decimal | int | str]],
    final_demand: Sequence[Decimal | int | str],
) -> tuple[list[list[Decimal]], list[Decimal]]:
    n = len(final_demand)
    if n == 0:
        raise ModelInvariantError("final_demand must not be empty")
    if len(technical_coefficients) != n:
        raise ModelInvariantError("technical coefficient matrix must be square")

    matrix: list[list[Decimal]] = []
    for row in technical_coefficients:
        if len(row) != n:
            raise ModelInvariantError("technical coefficient matrix must be square")
        converted = [_d(v) for v in row]
        if any(v < ZERO for v in converted):
            raise ModelInvariantError("technical coefficients must be non-negative")
        matrix.append(converted)

    demand = [_d(v) for v in final_demand]
    if any(v < ZERO for v in demand):
        raise ModelInvariantError("final demand must be non-negative")
    return matrix, demand


def leontief_gross_output(
    technical_coefficients: Sequence[Sequence[Decimal | int | str]],
    final_demand: Sequence[Decimal | int | str],
) -> list[Decimal]:
    """Solve `(I - A) x = y` using Decimal Gaussian elimination.

    This returns the *unconstrained* Leontief baseline. Physical feasibility is
    a separate question and should be checked against capacity/energy/labor/etc.
    The function deliberately does not clip or fabricate output to satisfy a
    constraint.
    """

    a, y = _validate_system(technical_coefficients, final_demand)
    n = len(y)

    augmented: list[list[Decimal]] = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append((ONE if i == j else ZERO) - a[i][j])
        row.append(y[i])
        augmented.append(row)

    for pivot_col in range(n):
        pivot_row = max(
            range(pivot_col, n),
            key=lambda r: abs(augmented[r][pivot_col]),
        )
        pivot = augmented[pivot_row][pivot_col]
        if pivot == ZERO:
            raise ModelInvariantError("Leontief system is singular")

        if pivot_row != pivot_col:
            augmented[pivot_col], augmented[pivot_row] = (
                augmented[pivot_row],
                augmented[pivot_col],
            )

        pivot = augmented[pivot_col][pivot_col]
        augmented[pivot_col] = [value / pivot for value in augmented[pivot_col]]

        for row_idx in range(n):
            if row_idx == pivot_col:
                continue
            factor = augmented[row_idx][pivot_col]
            if factor == ZERO:
                continue
            augmented[row_idx] = [
                current - factor * pivot_value
                for current, pivot_value in zip(
                    augmented[row_idx], augmented[pivot_col], strict=True
                )
            ]

    solution = [augmented[i][-1] for i in range(n)]
    if any(value < ZERO for value in solution):
        raise ModelInvariantError(
            "Leontief solution contains negative gross output; inspect model assumptions"
        )
    return solution


def capacity_violations(
    gross_output: Sequence[Decimal | int | str],
    capacities: Sequence[Decimal | int | str],
) -> list[CapacityViolation]:
    """Return explicit physical-capacity violations without altering output."""

    if len(gross_output) != len(capacities):
        raise ModelInvariantError("gross_output and capacities must have equal length")

    violations: list[CapacityViolation] = []
    for sector, (raw_output, raw_capacity) in enumerate(
        zip(gross_output, capacities, strict=True)
    ):
        output = _d(raw_output)
        capacity = _d(raw_capacity)
        if output < ZERO or capacity < ZERO:
            raise ModelInvariantError("output and capacity must be non-negative")
        if output > capacity:
            violations.append(
                CapacityViolation(
                    sector=sector,
                    requested_output=output,
                    capacity=capacity,
                )
            )
    return violations
