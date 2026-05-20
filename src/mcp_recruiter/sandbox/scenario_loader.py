"""Scenario loader — load and validate test scenarios from YAML/JSON."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..core.enums import ExpectedBehavior
from ..core.models import TestCase, TestScenario


def load_scenarios_from_yaml(path: str | Path) -> list[TestScenario]:
    """Load test scenarios from a YAML file."""
    content = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    if not data:
        return []

    scenarios_raw = data if isinstance(data, list) else data.get("scenarios", [data])
    return [parse_scenario(s) for s in scenarios_raw if s]


def load_scenarios_from_dict(data: list[dict]) -> list[TestScenario]:
    """Load test scenarios from a list of dicts."""
    return [parse_scenario(s) for s in data]


def parse_scenario(raw: dict[str, Any]) -> TestScenario:
    """Parse a single test scenario from raw dict."""
    cases_raw = raw.get("test_cases", raw.get("cases", []))
    cases = [_parse_test_case(c) for c in cases_raw]

    return TestScenario(
        name=raw.get("name", "Unnamed Scenario"),
        description=raw.get("description", ""),
        test_cases=cases,
        timeout_seconds=raw.get("timeout_seconds", 60),
        max_retries=raw.get("max_retries", 2),
    )


def _parse_test_case(raw: dict[str, Any]) -> TestCase:
    behavior_map = {
        "exact_match": ExpectedBehavior.EXACT_MATCH,
        "contains": ExpectedBehavior.CONTAINS,
        "schema_match": ExpectedBehavior.SCHEMA_MATCH,
        "no_error": ExpectedBehavior.NO_ERROR,
    }
    behavior_str = raw.get("expected_behavior", "no_error")
    behavior = behavior_map.get(behavior_str, ExpectedBehavior.NO_ERROR)

    return TestCase(
        name=raw.get("name", "Unnamed Case"),
        description=raw.get("description", ""),
        mcp_tool_name=raw.get("mcp_tool_name", raw.get("tool", "")),
        mcp_arguments=raw.get("mcp_arguments", raw.get("arguments", {})),
        expected_behavior=behavior,
        expected_value=raw.get("expected_value", ""),
    )
