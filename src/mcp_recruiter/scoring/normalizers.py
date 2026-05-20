"""Normalizers — scale raw factor values to 0-1 range."""

from __future__ import annotations

import math


def min_max_normalize(values: list[float]) -> list[float]:
    """Min-max normalization to [0, 1]."""
    if not values:
        return []
    min_v = min(values)
    max_v = max(values)
    if max_v == min_v:
        return [1.0 if v > 0 else 0.0 for v in values]
    return [(v - min_v) / (max_v - min_v) for v in values]


def log_normalize(value: float, reference_max: float) -> float:
    """Log-scale normalization: log(x+1) / log(max+1)."""
    if value <= 0:
        return 0.0
    if reference_max <= 0:
        reference_max = 1.0
    return math.log(value + 1) / math.log(reference_max + 1)


def capped_normalize(value: float, cap: float) -> float:
    """Linear normalization with cap: min(value/cap, 1.0)."""
    if cap <= 0:
        return 0.0
    return min(value / cap, 1.0)


def percentile_normalize(values: list[float]) -> list[float]:
    """Rank-based normalization using percentile."""
    if not values:
        return []
    n = len(values)
    if n == 1:
        return [1.0]
    sorted_vals = sorted(values)
    rank = {v: i / (n - 1) for i, v in enumerate(sorted_vals)}
    return [rank[v] for v in values]
