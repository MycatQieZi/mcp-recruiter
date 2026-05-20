"""Scoring weight presets."""

from __future__ import annotations

from ..core.enums import ScoringPreset
from ..core.models import ScoreWeights


PRESETS: dict[ScoringPreset, ScoreWeights] = {
    ScoringPreset.BALANCED: ScoreWeights(
        capability=0.25, health=0.25, ecosystem=0.25, test=0.25, preset=ScoringPreset.BALANCED,
    ),
    ScoringPreset.PERF_FIRST: ScoreWeights(
        capability=0.20, health=0.15, ecosystem=0.15, test=0.50, preset=ScoringPreset.PERF_FIRST,
    ),
    ScoringPreset.COMMUNITY_FIRST: ScoreWeights(
        capability=0.20, health=0.30, ecosystem=0.30, test=0.20, preset=ScoringPreset.COMMUNITY_FIRST,
    ),
    ScoringPreset.QUICK_SCAN: ScoreWeights(
        capability=0.60, health=0.10, ecosystem=0.20, test=0.10, preset=ScoringPreset.QUICK_SCAN,
    ),
}


def get_preset(preset: ScoringPreset) -> ScoreWeights:
    return PRESETS[preset]
