"""HTML report renderer — self-contained HTML with Chart.js visualizations."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..core.models import PipelineReport, ScoreCard


def render_html(report: PipelineReport, output_path: str) -> str:
    """Generate a self-contained HTML report and write to output_path."""
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("report.html.j2")

    # Prepare data for Chart.js
    chart_data = _prepare_chart_data(report.score_cards)

    html = template.render(
        report=report,
        chart_data_json=json.dumps(chart_data, ensure_ascii=False),
    )

    Path(output_path).write_text(html, encoding="utf-8")
    return html


def _prepare_chart_data(cards: list[ScoreCard]) -> dict:
    """Prepare data structure for Chart.js visualizations."""
    labels = [c.display_name for c in cards]

    return {
        "labels": labels,
        "datasets": {
            "composite": [round(c.composite_score, 1) for c in cards],
            "capability": [round(c.capability_score * 100, 1) for c in cards],
            "health": [round(c.health_score * 100, 1) for c in cards],
            "ecosystem": [round(c.ecosystem_score * 100, 1) for c in cards],
            "test": [round(c.test_score * 100, 1) for c in cards],
        },
        "radar": [
            {
                "label": c.display_name,
                "data": [
                    round(c.capability_score * 100, 1),
                    round(c.health_score * 100, 1),
                    round(c.ecosystem_score * 100, 1),
                    round(c.test_score * 100, 1),
                ],
            }
            for c in cards
        ],
    }
