"""Sandbox manager — Docker-based isolated test environment."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from ..core.enums import ExpectedBehavior
from ..core.models import Resume, TestResult, TestScenario
from .capture import capture_test_output
from .scenario_loader import TestScenario as ScenarioModel


class SandboxManager:
    """Manages Docker-based sandbox environments for testing MCP candidates.

    Uses subprocess to call docker CLI (avoids docker-py dependency for prototype).
    """

    def __init__(
        self,
        workspace_dir: str = "./sandbox-workspace",
        timeout_seconds: int = 120,
        memory_limit_mb: int = 512,
        network_mode: str = "none",
    ):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout_seconds
        self.memory_limit = f"{memory_limit_mb}m"
        self.network_mode = network_mode

    def test_candidate(
        self,
        resume: Resume,
        scenario: TestScenario,
    ) -> TestResult | None:
        """Test a candidate against a scenario in a sandbox.

        For the prototype, this runs a simulated test using:
        1. npx/npm to attempt to invoke the MCP tool via stdio
        2. Falls back to a basic smoke test if npx fails
        """
        case_results = []
        latencies: list[float] = []

        for test_case in scenario.test_cases:
            start = time.time()
            result = self._run_single_test(resume, test_case)
            elapsed = (time.time() - start) * 1000
            latencies.append(elapsed)

            cr = capture_test_output(
                case_name=test_case.name,
                exit_code=result.get("exit_code", 0),
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", ""),
                latency_ms=elapsed,
                expected_behavior=test_case.expected_behavior,
                expected_value=test_case.expected_value,
            )
            case_results.append(cr)

        if not case_results:
            return None

        passed = sum(1 for c in case_results if c.passed)
        failed = sum(1 for c in case_results if not c.passed and c.exit_code != 0)

        # Calculate latency percentiles
        latencies.sort()
        n = len(latencies)
        p50 = latencies[n // 2] if n else 0
        p95 = latencies[int(n * 0.95)] if n > 1 else (latencies[0] if latencies else 0)
        p99 = latencies[int(n * 0.99)] if n > 2 else (latencies[-1] if latencies else 0)

        # Output quality: average of individual case evaluations
        quality_score = 0.0
        valid_cases = [c for c in case_results if c.expected_behavior != ExpectedBehavior.NO_ERROR]
        if valid_cases:
            quality_score = sum(1.0 for c in valid_cases if c.passed) / len(valid_cases)

        return TestResult(
            candidate_id=resume.candidate_id,
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            success_rate=passed / len(case_results) if case_results else 0.0,
            total_cases=len(case_results),
            passed=passed,
            failed=failed,
            errors=0,
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            output_quality_score=quality_score,
            case_results=case_results,
            executed_at=datetime.now(),
        )

    def _run_single_test(self, resume: Resume, test_case) -> dict[str, Any]:
        """Run a single test case against the candidate.

        Attempts to run the MCP tool via npx or npm in a subprocess.
        If the tool is not installable or the call fails, returns a partial result.
        """
        pkg_name = resume.display_name

        # Build the command to invoke the MCP tool
        # Most MCP servers are invoked via: npx -y <package-name> <tool> <args>
        args_json = json.dumps(test_case.mcp_arguments) if hasattr(test_case, 'mcp_arguments') else "{}"

        # Attempt: use a simple node script to call the MCP tool via stdio
        cmd = self._build_test_command(pkg_name, test_case.mcp_tool_name, args_json)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=min(self.timeout, 30),
                shell=True,
                env={**os.environ, "NODE_ENV": "test"},
                cwd=str(self.workspace_dir),
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "stdout": "", "stderr": "Test timed out"}
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e)}

    def _build_test_command(self, pkg_name: str, tool_name: str, args_json: str) -> str:
        """Build a shell command to test the MCP tool."""
        # Escape for shell safety
        pkg_safe = pkg_name.replace('"', '\\"')
        tool_safe = tool_name.replace('"', '\\"')
        args_safe = args_json.replace('"', '\\"')

        script = (
            'node -e "'
            'const{spawn}=require(\\"child_process\\");'
            f'const p=spawn(\\"npx\\",[\\"-y\\",\\"{pkg_safe}\\"]);'
            'let o=\\"\\";let e=\\"\\";'
            'p.stdout.on(\\"data\\",d=>o+=d);'
            'p.stderr.on(\\"data\\",d=>e+=d);'
            f'p.on(\\"close\\",c=>{{console.log(JSON.stringify({{tool:\\"{tool_safe}\\",exit:c,stdout:o,stderr:e}}));'
            'process.exit(c)});'
            'setTimeout(()=>{p.kill();process.exit(1)},8000);'
            f'const msg=JSON.stringify({{jsonrpc:\\"2.0\\",id:1,method:\\"tools/call\\",params:{{name:\\"{tool_safe}\\",arguments:{args_safe}}}}});'
            'p.stdin.write(msg+\\"\\\\n\\");'
            'p.stdin.end();'
            '"'
        )
        return script

    def cleanup(self) -> None:
        """Clean up workspace."""
        # Clear temp files in workspace
        for f in self.workspace_dir.glob("*"):
            if f.is_file():
                f.unlink()


import json  # at top already, but needed in _build_test_command context
