"""Soft scorer — weighted multi-factor scoring for initial screening."""

from __future__ import annotations

import math
from datetime import datetime

from ..core.models import HealthMetrics, EcosystemMetrics, JobDescription, Resume


def score_capability(resume: Resume, job: JobDescription) -> float:
    """Score capability match between resume and job requirements (0-1)."""
    if not job.required_capabilities and not job.preferred_capabilities:
        # No requirements specified — score based on tool count
        tool_count = len(resume.tools_provided)
        return min(tool_count / 10.0, 1.0)

    # Jaccard similarity on required capabilities
    resume_caps = set(t.name.lower() for t in resume.tools_provided)
    resume_caps.update(r.lower() for r in resume.resources)
    required_set = set(c.lower() for c in job.required_capabilities)
    preferred_set = set(c.lower() for c in job.preferred_capabilities)

    # Required capabilities match (Jaccard)
    if required_set:
        intersection = resume_caps & required_set
        union = resume_caps | required_set
        required_score = len(intersection) / len(union) if union else 0.0
    else:
        required_score = 1.0

    # Preferred capabilities bonus
    if preferred_set:
        preferred_match = resume_caps & preferred_set
        preferred_bonus = len(preferred_match) / len(preferred_set) * 0.3
    else:
        preferred_bonus = 0.0

    # Tool count factor
    tool_factor = min(len(resume.tools_provided) / 15.0, 1.0) * 0.2

    # Resource count factor
    resource_factor = min(len(resume.resources) / 5.0, 1.0) * 0.1

    score = (
        0.4 * required_score
        + preferred_bonus
        + tool_factor
        + resource_factor
    )
    return min(score, 1.0)


def score_health(health: HealthMetrics) -> float:
    """Score project health (0-1)."""
    factors: list[tuple[float, float]] = []

    # Stars (log scale, normalized)
    star_score = _log_normalize(health.stars, 10000)
    factors.append((star_score, 0.2))

    # Issue health
    issue_score = 1.0 - (health.open_issues / (health.open_issues + 10))
    factors.append((issue_score, 0.2))

    # Recency
    if health.last_commit_date:
        days_since = max(0, (datetime.now() - health.last_commit_date.replace(tzinfo=None)).days)
        recency_score = 1.0 / (1.0 + days_since / 365.0)
    else:
        recency_score = 0.0
    factors.append((recency_score, 0.4))

    # Contributors
    contributor_score = _log_normalize(health.contributor_count, 50)
    factors.append((contributor_score, 0.1))

    # Release cadence
    if health.release_frequency_days and health.release_frequency_days > 0:
        cadence_score = 1.0 / (1.0 + health.release_frequency_days / 90.0)
    else:
        cadence_score = 0.3  # neutral
    factors.append((cadence_score, 0.1))

    return sum(s * w for s, w in factors)


def score_ecosystem(eco: EcosystemMetrics) -> float:
    """Score ecosystem adoption (0-1)."""
    factors: list[tuple[float, float]] = []

    # Adoption (dependents)
    adoption_score = _log_normalize(eco.dependents, 500)
    factors.append((adoption_score, 0.5))

    # Documentation
    factors.append((eco.documentation_score, 0.3))

    # Downloads
    downloads = eco.downloads_weekly or 0
    dl_score = _log_normalize(downloads, 50000)
    factors.append((dl_score, 0.2))

    return sum(s * w for s, w in factors)


def _log_normalize(value: float, max_val: float) -> float:
    """Log-scale normalization to 0-1 range."""
    if value <= 0:
        return 0.0
    return math.log(value + 1) / math.log(max_val + 1)
