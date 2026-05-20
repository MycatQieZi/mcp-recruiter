"""Scoring engine — compute composite scores and rankings."""

from __future__ import annotations

from uuid import uuid4

from ..core.models import (
    JobDescription,
    Resume,
    ScoreCard,
    ScoreWeights,
    StageScore,
    TestResult,
)
from ..core.enums import Stage
from ..screening.soft_scorer import score_capability, score_ecosystem, score_health
from .normalizers import log_normalize


class ScoringEngine:
    """Aggregate all dimension scores into composite rankings."""

    def compute_score_cards(
        self,
        resumes: list[Resume],
        test_results: dict[str, list[TestResult]],
        job: JobDescription,
    ) -> list[ScoreCard]:
        """Compute ScoreCard for each candidate."""
        weights = job.scoring_weights
        cards: list[ScoreCard] = []

        for resume in resumes:
            cid = str(resume.candidate_id)
            tests = test_results.get(cid, [])

            # Dimension scores (0-1)
            cap = score_capability(resume, job)
            health = score_health(resume.health)
            eco = score_ecosystem(resume.ecosystem)
            test_score = self._compute_test_dimension(tests)

            # Composite (0-100)
            composite = (
                weights.capability * cap
                + weights.health * health
                + weights.ecosystem * eco
                + weights.test * test_score
            ) * 100

            # Strengths / weaknesses
            strengths = self._identify_strengths(cap, health, eco, test_score)
            weaknesses = self._identify_weaknesses(cap, health, eco, test_score)

            card = ScoreCard(
                id=uuid4(),
                candidate_id=resume.candidate_id,
                display_name=resume.display_name,
                capability_score=cap,
                health_score=health,
                ecosystem_score=eco,
                test_score=test_score,
                composite_score=composite,
                strengths=strengths,
                weaknesses=weaknesses,
                factor_breakdown={
                    "capability_tool_count": len(resume.tools_provided),
                    "capability_match": cap,
                    "health_stars": resume.health.stars,
                    "health_recency": health,
                    "ecosystem_dependents": resume.ecosystem.dependents,
                    "ecosystem_docs": resume.ecosystem.documentation_score,
                    "test_success_rate": self._get_test_metric(tests, "success_rate"),
                    "test_avg_latency_ms": self._get_test_metric(tests, "avg_latency_ms"),
                },
                stage_scores=[
                    StageScore(stage=Stage.SCREEN, score=(cap + health + eco) / 3),
                    StageScore(stage=Stage.WRITTEN, score=test_score),
                ],
            )
            cards.append(card)

        # Rank by composite score descending
        cards.sort(key=lambda c: c.composite_score, reverse=True)
        for i, card in enumerate(cards):
            card.rank = i + 1

        return cards

    @staticmethod
    def _compute_test_dimension(tests: list[TestResult]) -> float:
        if not tests:
            return 0.0
        success = sum(t.success_rate for t in tests) / len(tests)
        quality = sum(t.output_quality_score for t in tests) / len(tests)
        avg_p95 = sum(t.p95_latency_ms for t in tests) / len(tests)
        latency = 1.0 / (1.0 + avg_p95 / 5000.0)
        return 0.5 * success + 0.25 * quality + 0.25 * latency

    @staticmethod
    def _get_test_metric(tests: list[TestResult], metric: str) -> float:
        if not tests:
            return 0.0
        return sum(getattr(t, metric, 0.0) for t in tests) / len(tests)

    @staticmethod
    def _identify_strengths(
        cap: float, health: float, eco: float, test_score: float
    ) -> list[str]:
        strengths = []
        if cap >= 0.7:
            strengths.append("能力匹配度高")
        if health >= 0.7:
            strengths.append("项目健康度好")
        if eco >= 0.7:
            strengths.append("生态完善")
        if test_score >= 0.7:
            strengths.append("测试表现优异")
        return strengths

    @staticmethod
    def _identify_weaknesses(
        cap: float, health: float, eco: float, test_score: float
    ) -> list[str]:
        weaknesses = []
        if cap < 0.3:
            weaknesses.append("能力匹配度不足")
        if health < 0.3:
            weaknesses.append("项目活跃度低")
        if eco < 0.3:
            weaknesses.append("生态薄弱")
        if test_score < 0.3:
            weaknesses.append("测试表现不佳")
        return weaknesses
