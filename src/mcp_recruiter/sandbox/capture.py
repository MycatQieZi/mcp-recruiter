"""Output capture — collect and parse sandbox test outputs."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..core.enums import ExpectedBehavior
from ..core.models import CaseResult


def capture_test_output(
    case_name: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    latency_ms: float,
    expected_behavior: ExpectedBehavior,
    expected_value: str = "",
) -> CaseResult:
    """Capture and evaluate a single test case result."""
    passed = _evaluate_result(stdout, exit_code, expected_behavior, expected_value)
    error_message = stderr.strip() if not passed and stderr else ""

    return CaseResult(
        case_name=case_name,
        passed=passed,
        exit_code=exit_code,
        stdout=stdout.strip(),
        stderr=error_message,
        latency_ms=latency_ms,
        error_message=error_message,
        expected_behavior=expected_behavior,
    )


def _evaluate_result(
    stdout: str,
    exit_code: int,
    behavior: ExpectedBehavior,
    expected_value: str,
) -> bool:
    """Evaluate if a test case passed."""
    if exit_code != 0 and behavior != ExpectedBehavior.NO_ERROR:
        return False

    output = stdout.strip()

    if behavior == ExpectedBehavior.NO_ERROR:
        return exit_code == 0

    elif behavior == ExpectedBehavior.EXACT_MATCH:
        return output == expected_value.strip()

    elif behavior == ExpectedBehavior.CONTAINS:
        return expected_value.strip().lower() in output.lower()

    elif behavior == ExpectedBehavior.SCHEMA_MATCH:
        # Try to parse as JSON and check if it has expected keys
        if expected_value:
            try:
                data = json.loads(output)
                expected_keys = set(k.strip() for k in expected_value.split(","))
                actual_keys = set(data.keys()) if isinstance(data, dict) else set()
                return expected_keys.issubset(actual_keys)
            except json.JSONDecodeError:
                return False
        # No expected schema — any valid JSON passes
        try:
            json.loads(output)
            return True
        except json.JSONDecodeError:
            return False

    return exit_code == 0  # fallback
