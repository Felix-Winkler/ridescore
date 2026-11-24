"""Mapping of raw values to the 1..5 score scale."""
from __future__ import annotations


def clamp_score(value: float) -> float:
    """Limit a score to the range 1..5."""
    return max(1.0, min(5.0, value))


def scale_to_score(value: float, worst: float, best: float) -> float:
    """Linear map: ``worst`` -> 1, ``best`` -> 5, clamped. Works for both directions."""
    if worst == best:
        raise ValueError("worst and best must differ")
    t = (value - worst) / (best - worst)
    return clamp_score(1.0 + 4.0 * max(0.0, min(1.0, t)))
