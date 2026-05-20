"""CLI entry point — build with Typer + Rich."""
import asyncio
import sys
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..core.config import load_config
from ..core.enums import Stage
from ..core.models import (
    HardRequirements,
    JobDescription,
    PipelineReport,
    ScoreWeights,
    TestScenario,
)
from ..core.state import PipelineStateMachine
from ..core.store import PipelineStore
from ..registry.aggregator import RegistryAggregator
from ..screening.hard_filter import apply_hard_filters
from ..screening.resume_builder import build_resume
from ..screening.soft_scorer import score_capability, score_ecosystem, score_health
from ..sandbox.scenario_loader import load_scenarios_from_yaml
from ..sandbox.manager import SandboxManager
from ..sandbox.test_runner import TestRunner
from ..scoring.engine import ScoringEngine
from ..reporting.terminal_render import render_report
from ..reporting.html_render import render_html
from .interactive import interactive_create_job

app = typer.Typer(
    name="mcp-recruiter",
    help="技术方案招聘系统 — 用 HR 面试流程评估 MCP 工具和方案",
    add_completion=False,
)

console = Console()


def _load_job(job_file: str) -> JobDescription:
    """Load a job description from a YAML file."""
    data = yaml.safe_load(Path(job_file).read_text(encoding="utf-8"))
    hard = HardRequirements(**data.get("hard_requirements", {}))
    weights = ScoreWeights(**data.get("scoring_weights", {}))
    scenarios_raw = data.get("test_scenarios", [])
    scenarios = [TestScenario(**s) for s in scenarios_raw] if scenarios_raw else []
    return JobDescription(
        title=data.get("title", "Untitled Job"),
        problem_statement=data.get("problem_statement", ""),
        required_capabilities=data.get("required_capabilities", []),
        preferred_capabilities=data.get("preferred_capabilities", []),
        hard_requirements=hard,
        test_scenarios=scenarios,
        scoring_weights=weights,
        top_n_candidates=data.get("top_n_candidates", 5),
    )


def _extract_search_query_from_yaml(job_file: str) -> str:
    """Extract the search_query hint embedded in YAML comments."""
    try:
        text = Path(job_file).read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# search_query:"):
                return stripped.split(":", 1)[1].strip()
    except Exception:
        pass
    return ""


@app.command()
def create_job(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output YAML file path"),
):
    """交互式创建招聘职位: 通过 TUI 问答式生成 job_description.yaml."""
    path, meta = interactive_create_job(output_path=output)
    if not path:
        return
    run_now = typer.confirm("\n是否立即运行招聘流程?", default=True)
    if run_now:
        _run_pipeline(path, None, False, meta.get("search_query", ""))


@app.command()
def run(
    job_file: Optional[str] = typer.Option(None, "--job", "-j", help="Job description YAML file path (leave empty for interactive creation)"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    skip_test: bool = typer.Option(False, "--skip-test", help="Skip sandbox testing stage"),
    search_query: str = typer.Option("", "--query", "-q", help="Additional search query terms"),
):
    """Run the full hiring pipeline (Sea -> Screen -> Written -> Interview).

    If no --job is provided, launches interactive TUI to create one first.
    """
    if not job_file:
        console.print("[bold yellow]未指定职位文件，启动交互式创建向导...[/bold yellow]")
        path, _meta = interactive_create_job(output_path=None)
        if not path:
            console.print("[yellow]已取消[/yellow]")
            return
        # Extract the search query the user entered during TUI
        search_query = search_query or _meta.get("search_query", "")
        job_file = path

    _run_pipeline(job_file, config_file, skip_test, search_query)


def _run_pipeline(
    job_file: str,
    config_file: Optional[str],
    skip_test: bool,
    search_query: str,
):
    config = load_config(config_file)
    store = PipelineStore(config.data_dir)
    sm = PipelineStateMachine()

    console.print("[bold green]正在启动 MCP 技术方案招聘流程...[/bold green]")
    console.print()

    # Load job description
    job = _load_job(job_file)

    # Fallback search query: from YAML hint -> command line -> capabilities
    if not search_query:
        search_query = _extract_search_query_from_yaml(job_file)
    if not search_query:
        search_query = " ".join(job.required_capabilities[:3] if job.required_capabilities else ["mcp server"])
    console.print()

    # ── Stage 1: Sea Selection ──
    console.rule("[bold blue]1/4 海选 — 搜索候选方案[/bold blue]")
    sm.set_result(Stage.SEA, {"status": "running"})

    aggregator = RegistryAggregator(
        cache_dir=f"{config.data_dir}/cache",
        github_token=config.github_token,
    )

    console.print(f"[dim]Search query: {search_query}[/dim]")

    candidates = asyncio.run(aggregator.search(search_query))
    console.print(f"[green]Found {len(candidates)} candidates from registries[/green]")

    if not candidates:
        console.print("[yellow]No candidates found. Try broadening search criteria.[/yellow]")
        return

    # Build resumes
    resumes = [build_resume(c) for c in candidates]
    store.save_resumes([r.model_dump(mode="json") for r in resumes])
    sm.set_result(Stage.SEA, {"candidates": len(candidates), "status": "complete"})

    # Show summary table
    table = Table(title=f"海选结果 — {len(candidates)} 位候选人")
    table.add_column("#", justify="right")
    table.add_column("名称")
    table.add_column("来源")
    table.add_column("Stars", justify="right")
    table.add_column("简介")
    for i, r in enumerate(resumes[:10], 1):
        table.add_row(str(i), r.display_name, r.source, str(r.health.stars), r.one_line_pitch[:60])
    console.print(table)

    sm.advance()

    # ── Stage 2: Initial Screening ──
    console.rule("[bold blue]2/4 初试 — 筛选候选方案[/bold blue]")

    passed_resumes = []
    for resume in resumes:
        result = apply_hard_filters(resume, job.hard_requirements)
        if result.passed:
            passed_resumes.append(resume)
        else:
            console.print(f"[red]X[/red] {resume.display_name} - {result.reason}")

    console.print(f"[green]Hard filter: {len(passed_resumes)}/{len(resumes)} passed[/green]")

    # Score and rank
    scored_cards = []
    for resume in passed_resumes:
        cap = score_capability(resume, job)
        health = score_health(resume.health)
        eco = score_ecosystem(resume.ecosystem)
        composite = cap * 0.5 + health * 0.25 + eco * 0.25
        scored_cards.append((resume, cap, health, eco, composite))

    scored_cards.sort(key=lambda x: x[4], reverse=True)
    top_n = min(job.top_n_candidates, len(scored_cards))
    shortlisted = scored_cards[:top_n]

    # Display screening results
    screen_table = Table(title=f"初试结果 — Top {top_n}")
    screen_table.add_column("排名", justify="right")
    screen_table.add_column("名称")
    screen_table.add_column("能力", justify="right")
    screen_table.add_column("健康", justify="right")
    screen_table.add_column("生态", justify="right")
    for i, (r, cap, health, eco, comp) in enumerate(shortlisted, 1):
        color = "green" if comp >= 0.7 else ("yellow" if comp >= 0.4 else "red")
        screen_table.add_row(
            f"#{i}", r.display_name,
            f"[{color}]{cap:.2f}[/{color}]",
            f"{health:.2f}", f"{eco:.2f}"
        )
    console.print(screen_table)

    shortlisted_resumes = [r for r, *_ in shortlisted]
    sm.set_result(Stage.SCREEN, {"passed": len(shortlisted), "status": "complete"})
    sm.advance()

    # ── Stage 3: Written Test ──
    if skip_test:
        console.print("[yellow]3/4 笔试 — 已跳过[/yellow]")
        test_results_map = {}
    else:
        console.rule("[bold blue]3/4 笔试 — 沙盒测试[/bold blue]")

        sandbox = SandboxManager(
            workspace_dir=config.workspace_dir,
            timeout_seconds=config.sandbox_timeout_seconds,
            memory_limit_mb=config.sandbox_memory_limit_mb,
            network_mode=config.sandbox_network_mode,
        )
        runner = TestRunner(sandbox)

        test_scenarios = job.test_scenarios
        if not test_scenarios:
            try:
                test_scenarios = load_scenarios_from_yaml(job_file)
            except Exception:
                pass

        if not test_scenarios:
            console.print("[yellow]No test scenarios defined. Skipping written test.[/yellow]")
            test_results_map = {}
        else:
            console.print(f"Testing {len(shortlisted_resumes)} candidates against {len(test_scenarios)} scenarios...")
            test_results_map = runner.run_all(shortlisted_resumes, test_scenarios)

            # Display test summary
            test_table = Table(title="笔试结果")
            test_table.add_column("候选人")
            test_table.add_column("通过率", justify="right")
            test_table.add_column("P95延迟", justify="right")
            test_table.add_column("质量分", justify="right")
            for r in shortlisted_resumes:
                results = test_results_map.get(str(r.candidate_id), [])
                if results:
                    avg_success = sum(t.success_rate for t in results) / len(results)
                    avg_p95 = sum(t.p95_latency_ms for t in results) / len(results)
                    avg_quality = sum(t.output_quality_score for t in results) / len(results)
                    test_table.add_row(
                        r.display_name,
                        f"{avg_success:.0%}",
                        f"{avg_p95:.0f}ms",
                        f"{avg_quality:.2f}"
                    )
                else:
                    test_table.add_row(r.display_name, "[dim]N/A[/dim]", "[dim]N/A[/dim]", "[dim]N/A[/dim]")
            console.print(test_table)

            runner.cleanup()

    sm.set_result(Stage.WRITTEN, {"tested": len(shortlisted), "status": "complete"})
    sm.advance()

    # ── Stage 4: Final Interview ──
    console.rule("[bold blue]4/4 终面 — 生成报告[/bold blue]")

    engine = ScoringEngine()
    score_cards = engine.compute_score_cards(shortlisted_resumes, test_results_map, job)
    store.save_score_cards([c.model_dump(mode="json") for c in score_cards])

    report = PipelineReport(
        job_id=job.id,
        job_title=job.title,
        score_cards=score_cards,
        generated_at=datetime.now(),
        total_candidates_discovered=len(candidates),
        total_screened=len(shortlisted),
        total_tested=len(shortlisted) if not skip_test and test_results_map else 0,
        recommendation=score_cards[0].display_name if score_cards else "",
        runner_up=score_cards[1].display_name if len(score_cards) > 1 else "",
    )

    # Terminal report
    render_report(report)

    # HTML report
    reports_dir = Path(config.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    html_path = reports_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    render_html(report, str(html_path))
    console.print(f"[green]HTML report saved to: {html_path}[/green]")

    # Save JSON report
    store.save_report(report.model_dump(mode="json"))

    sm.transition(Stage.COMPLETE)
    console.print("[bold green]招聘流程完成![/bold green]")


if __name__ == "__main__":
    app()
