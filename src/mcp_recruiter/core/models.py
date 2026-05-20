from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .enums import CandidateType, ExpectedBehavior, ScoringPreset, Stage, TransportType


# ── Job Description ──────────────────────────────────────


class HardRequirements(BaseModel):
    """Boolean pass/fail filters applied during initial screening."""

    min_stars: int | None = None
    max_days_since_update: int | None = None
    required_transports: list[TransportType] = Field(default_factory=list)
    min_tool_count: int | None = None
    require_license: bool = False


class ScoreWeights(BaseModel):
    """Configurable dimension weights for composite scoring."""

    capability: float = 0.30
    health: float = 0.15
    ecosystem: float = 0.15
    test: float = 0.40
    preset: ScoringPreset | None = None

    def model_post_init(self, __context):
        if self.preset:
            presets = {
                ScoringPreset.BALANCED: (0.25, 0.25, 0.25, 0.25),
                ScoringPreset.PERF_FIRST: (0.20, 0.15, 0.15, 0.50),
                ScoringPreset.COMMUNITY_FIRST: (0.20, 0.30, 0.30, 0.20),
                ScoringPreset.QUICK_SCAN: (0.60, 0.10, 0.20, 0.10),
            }
            self.capability, self.health, self.ecosystem, self.test = presets[self.preset]


class TestCase(BaseModel):
    """A single test case within a test scenario."""

    name: str
    description: str = ""
    mcp_tool_name: str
    mcp_arguments: dict = Field(default_factory=dict)
    expected_behavior: ExpectedBehavior = ExpectedBehavior.NO_ERROR
    expected_value: str = ""


class TestScenario(BaseModel):
    """A group of test cases that evaluate a candidate."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    test_cases: list[TestCase] = Field(default_factory=list)
    timeout_seconds: int = 60
    max_retries: int = 2


class JobDescription(BaseModel):
    """User's requirement specification — the 'job posting'."""

    id: UUID = Field(default_factory=uuid4)
    title: str
    problem_statement: str = ""
    required_capabilities: list[str] = Field(default_factory=list)
    preferred_capabilities: list[str] = Field(default_factory=list)
    hard_requirements: HardRequirements = Field(default_factory=HardRequirements)
    test_scenarios: list[TestScenario] = Field(default_factory=list)
    scoring_weights: ScoreWeights = Field(default_factory=ScoreWeights)
    top_n_candidates: int = 5  # how many pass to written test
    current_stage: Stage = Stage.SEA
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ── Resume (Candidate Profile) ───────────────────────────


class ToolSignature(BaseModel):
    """Signature of one tool provided by an MCP server."""

    name: str
    description: str = ""
    parameters: dict = Field(default_factory=dict)


class HealthMetrics(BaseModel):
    """Project health indicators."""

    stars: int = 0
    open_issues: int = 0
    last_commit_date: datetime | None = None
    contributor_count: int = 0
    release_frequency_days: float | None = None


class EcosystemMetrics(BaseModel):
    """Ecosystem adoption indicators."""

    dependents: int = 0
    downloads_weekly: int | None = None
    documentation_score: float = 0.0  # 0-1 heuristic
    has_examples: bool = False


class Resume(BaseModel):
    """Standardized candidate resume."""

    id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    display_name: str
    one_line_pitch: str = ""
    description: str = ""
    candidate_type: CandidateType = CandidateType.MCP_TOOL
    tools_provided: list[ToolSignature] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    health: HealthMetrics = Field(default_factory=HealthMetrics)
    ecosystem: EcosystemMetrics = Field(default_factory=EcosystemMetrics)
    source_url: str = ""
    source: str = ""  # github, npm, mcp_hub
    license: str = ""
    raw_metadata: dict = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.now)


# ── ScoreCard ─────────────────────────────────────────────


class StageScore(BaseModel):
    """Score for a single pipeline stage."""

    stage: Stage
    score: float = 0.0  # 0-1 normalized
    details: dict = Field(default_factory=dict)


class ScoreCard(BaseModel):
    """Aggregated evaluation for one candidate."""

    id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    display_name: str = ""
    capability_score: float = 0.0
    health_score: float = 0.0
    ecosystem_score: float = 0.0
    test_score: float = 0.0
    composite_score: float = 0.0  # 0-100
    rank: int = 0
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    factor_breakdown: dict[str, float] = Field(default_factory=dict)
    stage_scores: list[StageScore] = Field(default_factory=list)
    hard_filter_passed: bool = True
    hard_filter_reason: str = ""
    normalization_params: dict = Field(default_factory=dict)


# ── Test Results ──────────────────────────────────────────


class CaseResult(BaseModel):
    """Result of a single test case execution."""

    case_name: str
    passed: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    latency_ms: float = 0.0
    error_message: str = ""
    expected_behavior: ExpectedBehavior = ExpectedBehavior.NO_ERROR


class TestResult(BaseModel):
    """Aggregated test result for one candidate + one scenario."""

    id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    scenario_id: UUID
    scenario_name: str = ""
    success_rate: float = 0.0  # 0-1
    total_cases: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    output_quality_score: float = 0.0
    case_results: list[CaseResult] = Field(default_factory=list)
    sandbox_logs_path: str = ""
    executed_at: datetime = Field(default_factory=datetime.now)


# ── Report ────────────────────────────────────────────────


class PipelineReport(BaseModel):
    """Final report with all candidates ranked."""

    job_id: UUID
    job_title: str = ""
    score_cards: list[ScoreCard] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)
    total_candidates_discovered: int = 0
    total_screened: int = 0
    total_tested: int = 0
    recommendation: str = ""
    runner_up: str = ""
