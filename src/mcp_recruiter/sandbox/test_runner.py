"""Test runner — orchestrates sandbox testing for multiple candidates."""

from __future__ import annotations

from ..core.models import Resume, TestResult, TestScenario
from .manager import SandboxManager


class TestRunner:
    """Orchestrate testing of multiple candidates against multiple scenarios."""

    def __init__(self, manager: SandboxManager):
        self.manager = manager

    def run_all(
        self,
        resumes: list[Resume],
        scenarios: list[TestScenario],
    ) -> dict[str, list[TestResult]]:
        """Run all test scenarios against all candidates.

        Returns: {candidate_id: [TestResult, ...]}
        """
        results: dict[str, list[TestResult]] = {}

        for resume in resumes:
            candidate_results: list[TestResult] = []
            for scenario in scenarios:
                try:
                    result = self.manager.test_candidate(resume, scenario)
                    if result:
                        candidate_results.append(result)
                except Exception as e:
                    # Log error but continue
                    print(f"[error] Test failed for {resume.display_name}: {e}")

            key = str(resume.candidate_id)
            results[key] = candidate_results

        return results

    def cleanup(self) -> None:
        """Clean up all sandbox resources."""
        self.manager.cleanup()
