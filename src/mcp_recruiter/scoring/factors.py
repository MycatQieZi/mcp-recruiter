"""Scoring factors — individual scoring dimension definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..core.models import JobDescription, Resume, TestResult


@dataclass
class ScoringFactor:
    """A single scoring factor with its weight in its parent dimension."""

    name: str
    weight: float
    compute: Callable[[Resume, JobDescription, list[TestResult]], float]


def factor_tool_count(resume: Resume, _job: JobDescription, _tests: list[TestResult]) -> float:
    return float(len(resume.tools_provided))


def factor_capability_match(resume: Resume, job: JobDescription, _tests: list[TestResult]) -> float:
    if not job.required_capabilities:
        return 1.0
    resume_caps = set(t.name.lower() for t in resume.tools_provided)
    required = set(c.lower() for c in job.required_capabilities)
    intersection = resume_caps & required
    union = resume_caps | required
    return len(intersection) / len(union) if union else 0.0


def factor_stars(resume: Resume, _job: JobDescription, _tests: list[TestResult]) -> float:
    return float(resume.health.stars)


def factor_issue_health(resume: Resume, _job: JobDescription, _tests: list[TestResult]) -> float:
    return 1.0 - (resume.health.open_issues / (resume.health.open_issues + 10))


def factor_recency(resume: Resume, _job: JobDescription, _tests: list[TestResult]) -> float:
    from datetime import datetime
    if resume.health.last_commit_date:
        days = max(0, (datetime.now() - resume.health.last_commit_date.replace(tzinfo=None)).days)
        return 1.0 / (1.0 + days / 365.0)
    return 0.0


def factor_contributors(resume: Resume, _job: JobDescription, _tests: list[TestResult]) -> float:
    return float(resume.health.contributor_count)


def factor_ecosystem_adoption(resume: Resume, _job: JobDescription, _tests: list[TestResult]) -> float:
    return float(resume.ecosystem.dependents)


def factor_documentation(resume: Resume, _job: JobDescription, _tests: list[TestResult]) -> float:
    return resume.ecosystem.documentation_score


def factor_downloads(resume: Resume, _job: JobDescription, _tests: list[TestResult]) -> float:
    return float(resume.ecosystem.downloads_weekly or 0)


def factor_test_success(resume: Resume, _job: JobDescription, tests: list[TestResult]) -> float:
    if not tests:
        return 0.0
    return sum(t.success_rate for t in tests) / len(tests)


def factor_test_latency(resume: Resume, _job: JobDescription, tests: list[TestResult]) -> float:
    # Lower latency is better — invert
    if not tests:
        return 0.0
    avg_p95 = sum(t.p95_latency_ms for t in tests) / len(tests)
    return 1.0 / (1.0 + avg_p95 / 5000.0)


def factor_output_quality(resume: Resume, _job: JobDescription, tests: list[TestResult]) -> float:
    if not tests:
        return 0.0
    return sum(t.output_quality_score for t in tests) / len(tests)
