"""Reference real-economy / EIIOM primitives for SINERGY Eurasian."""

from .input_output import (
    CapacityViolation,
    ModelInvariantError,
    capacity_violations,
    leontief_gross_output,
)

__all__ = [
    "CapacityViolation",
    "ModelInvariantError",
    "capacity_violations",
    "leontief_gross_output",
]
