"""Terminal report renderer — Rich-based console output."""

from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..core.models import PipelineReport, ScoreCard, TestResult


def render_report(report: PipelineReport) -> None:
    """Render the final report to the terminal using Rich."""
    console = Console()

    # Header
    console.print()
    console.rule("[bold green]最终面试报告[/bold green]")
    console.print(
        f"[bold]职位:[/bold] {report.job_title}",
        f"[dim]生成时间: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
    )
    console.print(
        f"[dim]海选发现: {report.total_candidates_discovered} | "
        f"初试通过: {report.total_screened} | "
        f"笔试完成: {report.total_tested}[/dim]"
    )
    console.print()

    # Ranking table
    _render_ranking_table(console, report.score_cards)

    # Per-candidate detail panels
    for card in report.score_cards:
        _render_candidate_detail(console, card)

    # Recommendation
    if report.recommendation:
        console.print()
        console.print(
            Panel(
                f"[bold green]推荐录用: {report.recommendation}[/bold green]\n"
                + (f"备选: {report.runner_up}" if report.runner_up else ""),
                title="录用决策",
                border_style="green",
            )
        )

    console.rule("[dim]报告结束[/dim]")


def _render_ranking_table(console: Console, cards: list[ScoreCard]) -> None:
    """Render the candidate ranking table."""
    table = Table(title="候选人排名", show_header=True, header_style="bold cyan")
    table.add_column("排名", justify="right", style="dim")
    table.add_column("候选人")
    table.add_column("综合分", justify="right")
    table.add_column("能力", justify="right")
    table.add_column("健康", justify="right")
    table.add_column("生态", justify="right")
    table.add_column("测试", justify="right")
    table.add_column("优势")
    table.add_column("风险")

    for card in cards:
        score_color = "green" if card.composite_score >= 80 else ("yellow" if card.composite_score >= 50 else "red")
        strengths = ", ".join(card.strengths[:2]) if card.strengths else "-"
        weaknesses = ", ".join(card.weaknesses[:2]) if card.weaknesses else "-"

        table.add_row(
            f"#{card.rank}",
            card.display_name,
            f"[{score_color}]{card.composite_score:.1f}[/{score_color}]",
            f"{card.capability_score:.2f}",
            f"{card.health_score:.2f}",
            f"{card.ecosystem_score:.2f}",
            f"{card.test_score:.2f}" if card.test_score > 0 else "[dim]N/A[/dim]",
            f"[green]{strengths}[/green]",
            f"[red]{weaknesses}[/red]",
        )

    console.print(table)


def _render_candidate_detail(console: Console, card: ScoreCard) -> None:
    """Render a detailed panel for one candidate."""
    content = (
        f"[bold]综合得分: {card.composite_score:.1f}/100[/bold]\n"
        f"能力: {card.capability_score:.2f} | "
        f"健康: {card.health_score:.2f} | "
        f"生态: {card.ecosystem_score:.2f} | "
        f"测试: {card.test_score:.2f}"
    )

    if card.factor_breakdown:
        factors = card.factor_breakdown
        detail_lines = []
        if "health_stars" in factors:
            detail_lines.append(f"  Stars: {factors['health_stars']}")
        if "capability_match" in factors:
            detail_lines.append(f"  能力匹配: {factors['capability_match']:.2f}")
        if "test_success_rate" in factors:
            detail_lines.append(f"  测试通过率: {factors['test_success_rate']:.0%}")
        if "test_avg_latency_ms" in factors:
            detail_lines.append(f"  P95延迟: {factors['test_avg_latency_ms']:.0f}ms")
        if detail_lines:
            content += "\n" + "\n".join(detail_lines)

    console.print(
        Panel(
            content,
            title=f"[bold]#{card.rank} {card.display_name}[/bold]",
            border_style="blue",
        )
    )
