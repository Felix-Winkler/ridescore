"""Weighted overall score and ranking."""
from __future__ import annotations

from typing import Optional

from logic.scaling import clamp_score
from models.models import ScoredRoute, Weights


def overall_score(curves: float, weather: Optional[float], traffic: float,
                  weights: Weights) -> float:
    """Weighted mean of the available scores. A missing weather score is left out."""
    parts = [(curves, weights.curves), (traffic, weights.traffic)]
    if weather is not None:
        parts.append((weather, weights.weather))
    total_w = sum(w for _, w in parts)
    if total_w <= 0:  # all weights zero -> plain mean
        return clamp_score(sum(v for v, _ in parts) / len(parts))
    return clamp_score(sum(v * w for v, w in parts) / total_w)


def rank_routes(routes: list[ScoredRoute]) -> list[ScoredRoute]:
    """Sort by overall score (best first); ties are broken by the curve score."""
    return sorted(routes, key=lambda r: (r.score.overall, r.score.curves), reverse=True)


def rescore(routes: list[ScoredRoute], weights: Weights) -> list[ScoredRoute]:
    """Recompute the overall score with new weights and return the new ranking."""
    for r in routes:
        s = r.score
        s.overall = overall_score(s.curves, s.weather, s.traffic, weights)
    return rank_routes(routes)
