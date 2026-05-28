"""LLM-powered JD generator — generate JobDescription from natural language input."""

from __future__ import annotations

from ..core.llm_client import LLMClient
from ..core.models import (
    HardRequirements,
    JobDescription,
    ScoreWeights,
    TestCase,
    TestScenario,
)
from ..core.enums import ExpectedBehavior


class JobDescriptionGenerator:
    """Generate a JobDescription from free-form requirements using LLM."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    async def generate(self, user_description: str) -> tuple[JobDescription, list[str]]:
        """Generate a JobDescription from a natural language description.

        Returns:
            Tuple of (JobDescription, suggested_search_queries).
        """
        if not self.llm.available:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Set the environment variable or configure it in config."
            )

        raw = await self.llm.generate_jd(user_description)
        job = self._parse_jd(raw)
        search_queries = raw.get("suggested_search_queries", [])
        return job, search_queries

    def _parse_jd(self, raw: dict) -> JobDescription:
        """Parse LLM JSON response into a JobDescription model."""
        # Parse hard requirements
        hard_raw = raw.get("hard_requirements", {})
        hard_req = HardRequirements(
            min_stars=hard_raw.get("min_stars"),
            max_days_since_update=hard_raw.get("max_days_since_update"),
            min_tool_count=hard_raw.get("min_tool_count"),
            require_license=hard_raw.get("require_license", False),
        )

        # Parse test scenarios
        test_scenarios = []
        for s_raw in raw.get("suggested_test_scenarios", []):
            cases = []
            for c_raw in s_raw.get("test_cases", []):
                behavior_str = c_raw.get("expected_behavior", "no_error")
                try:
                    behavior = ExpectedBehavior(behavior_str)
                except ValueError:
                    behavior = ExpectedBehavior.NO_ERROR

                cases.append(TestCase(
                    name=c_raw.get("name", "Test case"),
                    description=c_raw.get("description", ""),
                    mcp_tool_name=c_raw.get("mcp_tool_name", "tools/list"),
                    mcp_arguments=c_raw.get("mcp_arguments", {}),
                    expected_behavior=behavior,
                    expected_value=c_raw.get("expected_value", ""),
                ))

            test_scenarios.append(TestScenario(
                name=s_raw.get("name", "Test scenario"),
                description=s_raw.get("description", ""),
                test_cases=cases,
                timeout_seconds=s_raw.get("timeout_seconds", 60),
                max_retries=s_raw.get("max_retries", 2),
            ))

        # Build JobDescription
        return JobDescription(
            title=raw.get("title", "Technical Solution"),
            problem_statement=raw.get("problem_statement", user_description="" if not locals().get("user_description") else ""),
            required_capabilities=raw.get("required_capabilities", []),
            preferred_capabilities=raw.get("preferred_capabilities", []),
            hard_requirements=hard_req,
            test_scenarios=test_scenarios if test_scenarios else [],
            scoring_weights=ScoreWeights(),
        )

    def build_yaml(
        self,
        job: JobDescription,
        search_queries: list[str],
        user_description: str = "",
    ) -> str:
        """Generate YAML content from a JobDescription and search queries."""
        from datetime import datetime

        caps_yaml = "\n".join(f'  - "{c}"' for c in job.required_capabilities) if job.required_capabilities else "  []"
        pref_yaml = "\n".join(f'  - "{c}"' for c in job.preferred_capabilities) if job.preferred_capabilities else "  []"

        hard_lines = []
        hr = job.hard_requirements
        if hr.min_stars is not None:
            hard_lines.append(f"  min_stars: {hr.min_stars}")
        if hr.max_days_since_update is not None:
            hard_lines.append(f"  max_days_since_update: {hr.max_days_since_update}")
        if hr.min_tool_count is not None:
            hard_lines.append(f"  min_tool_count: {hr.min_tool_count}")
        hard_lines.append(f"  require_license: {'true' if hr.require_license else 'false'}")
        hard_yaml = "\n".join(hard_lines) if hard_lines else "  {}"

        queries_comment = "\n".join(f"#   - {q}" for q in search_queries[:5])

        test_yaml = ""
        for s in job.test_scenarios:
            test_yaml += f"""  - name: "{s.name}"
    description: "{s.description}"
    timeout_seconds: {s.timeout_seconds}
    max_retries: {s.max_retries}
    test_cases:
"""
            for tc in s.test_cases:
                test_yaml += f"""      - name: "{tc.name}"
        mcp_tool_name: "{tc.mcp_tool_name}"
        expected_behavior: "{tc.expected_behavior.value}"
"""

        return f"""# Generated by MCP Recruiter LLM JD Generator
# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# User description: {user_description[:100]}

title: "{job.title}"

problem_statement: >
  {job.problem_statement}

# Suggested search queries (LLM generated):
{queries_comment}

required_capabilities:
{caps_yaml}

preferred_capabilities:
{pref_yaml}

hard_requirements:
{hard_yaml}

top_n_candidates: {getattr(job, 'top_n_candidates', 5)}

scoring_weights:
  preset: balanced

test_scenarios:
{test_yaml if test_yaml else '  []'}
"""
