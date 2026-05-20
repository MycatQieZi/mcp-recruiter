"""Interactive TUI — guided job description creation via Rich prompts.

Walks the user through creating a job description step by step,
then saves it as a YAML file ready for the pipeline.
"""

from __future__ import annotations

import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from ..core.enums import ScoringPreset

console = Console()


# ── Step builders ────────────────────────────────────────

def _ask_title() -> str:
    return Prompt.ask(
        "[bold cyan]1. 职位名称[/bold cyan]\n  给这次招聘起个简短的名字（如：文件系统 MCP 服务器）",
        default="MCP 工具招聘",
    )


def _ask_problem_statement() -> str:
    console.print()
    return Prompt.ask(
        "[bold cyan]2. 需求描述[/bold cyan]\n  用几句话描述你想解决什么问题",
        default="需要一个能够提供工具调用能力的 MCP 服务器",
    )


def _ask_capabilities(kind: str, examples: str) -> list[str]:
    console.print()
    raw = Prompt.ask(
        f"[bold cyan]3. {kind}[/bold cyan]\n  输入关键词，以逗号分隔\n  {examples}",
        default="",
    )
    return [c.strip() for c in raw.split(",") if c.strip()]


def _ask_hard_requirements() -> dict:
    console.print()
    console.print(
        Panel(
            "[bold cyan]4. 硬性过滤条件[/bold cyan]\n"
            "不满足任一条件的候选人将被直接淘汰。\n"
            "留空或输入 0 表示不限制。",
            border_style="cyan",
        )
    )

    min_stars = IntPrompt.ask(
        "  最低 GitHub Stars 数",
        default=0,
        show_default=True,
    )
    max_days = IntPrompt.ask(
        "  最大未更新天数（0=不限）",
        default=365,
        show_default=True,
    )
    min_tools = IntPrompt.ask(
        "  最少提供工具数（0=不限）",
        default=0,
        show_default=True,
    )
    require_license = Confirm.ask(
        "  是否要求必须有开源许可证?",
        default=False,
    )

    return {
        "min_stars": min_stars if min_stars > 0 else None,
        "max_days_since_update": max_days if max_days > 0 else None,
        "min_tool_count": min_tools if min_tools > 0 else None,
        "require_license": require_license,
    }


def _ask_top_n() -> int:
    console.print()
    return IntPrompt.ask(
        "[bold cyan]5. 笔试入围人数[/bold cyan]\n  初试通过后，多少人进入笔试环节？",
        default=5,
        show_default=True,
    )


def _ask_scoring_preset() -> str:
    console.print()
    console.print("[bold cyan]6. 评分权重策略[/bold cyan]")

    presets = {
        "1": ("balanced", "均衡 — 能力/健康/生态/测试 各占 25%"),
        "2": ("perf_first", "性能优先 — 测试表现占 50%"),
        "3": ("community_first", "社区优先 — 健康度和生态各占 30%"),
        "4": ("quick_scan", "快速筛选 — 能力匹配占 60%，适合海选阶段"),
    }

    for key, (name, desc) in presets.items():
        console.print(f"  [bold]{key}[/bold]. {desc}")

    choice = Prompt.ask("  选择策略", choices=["1", "2", "3", "4"], default="1")
    return presets[choice][0]


def _ask_search_query() -> str:
    console.print()
    query = Prompt.ask(
        "[bold cyan]7. 搜索关键词[/bold cyan]\n  用于在市场中搜索候选方案的关键词（英文效果更好）",
        default="mcp server",
    )
    return query


def _ask_output_path(default_name: str) -> str:
    console.print()
    return Prompt.ask(
        "[bold cyan]8. 保存路径[/bold cyan]\n  生成的 YAML 文件保存位置",
        default=f"examples/{default_name}.yaml",
    )


# ── Main interactive flow ────────────────────────────────

def interactive_create_job(
    output_path: Optional[str] = None,
) -> str:
    """Run the full interactive job creation workflow.

    Returns the path to the generated YAML file.
    """
    console.print()
    console.rule("[bold green]创建招聘职位 — 交互式引导[/bold green]")
    console.print(
        "[dim]按提示逐步填写需求，最终生成标准 job_description.yaml[/dim]"
    )
    console.print()

    # Step 1: Title
    title = _ask_title()
    safe_name = title.lower().replace(" ", "_").replace("/", "_")[:40]

    # Step 2: Problem statement
    problem = _ask_problem_statement()

    # Step 3: Required capabilities
    required_caps = _ask_capabilities(
        "必需能力",
        "例: file, search, filesystem, database (英文)",
    )

    # Step 3b: Preferred capabilities
    preferred_caps = _ask_capabilities(
        "加分能力（可跳过）",
        "例: write, directory, wildcard",
    )

    # Step 4: Hard requirements
    hard_req = _ask_hard_requirements()

    # Step 5: Top N
    top_n = _ask_top_n()

    # Step 6: Scoring preset
    preset_name = _ask_scoring_preset()

    # Step 7: Search query
    search_query = _ask_search_query()

    # Step 8: Output path
    if not output_path:
        output_path = _ask_output_path(safe_name)

    # ── Preview ──
    console.print()
    console.rule("[bold]预览 — 即将生成的 YAML 内容[/bold]")

    yaml_content = _build_yaml(
        title=title,
        problem=problem,
        required_caps=required_caps,
        preferred_caps=preferred_caps,
        hard_req=hard_req,
        top_n=top_n,
        preset_name=preset_name,
        search_query=search_query,
    )

    console.print(Panel(yaml_content, border_style="yellow", title="预览"))

    confirmed = Confirm.ask(
        "\n[bold]确认生成此文件？[/bold]",
        default=True,
    )
    if not confirmed:
        console.print("[yellow]已取消[/yellow]")
        return "", {}

    # Write
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml_content, encoding="utf-8")
    console.print(f"[green]已保存到: {out.resolve()}[/green]")

    _metadata = {"search_query": search_query}
    return str(out.resolve()), _metadata


def _build_yaml(
    title: str,
    problem: str,
    required_caps: list[str],
    preferred_caps: list[str],
    hard_req: dict,
    top_n: int,
    preset_name: str,
    search_query: str,
) -> str:
    """Assemble the YAML content string."""
    caps_yaml = "\n".join(f'  - "{c}"' for c in required_caps) if required_caps else "  []"
    pref_yaml = "\n".join(f'  - "{c}"' for c in preferred_caps) if preferred_caps else "  []"

    # Build hard requirements
    hard_lines = []
    for k, v in hard_req.items():
        if v is not None:
            if isinstance(v, bool):
                hard_lines.append(f"  {k}: {'true' if v else 'false'}")
            else:
                hard_lines.append(f"  {k}: {v}")
    hard_yaml = "\n".join(hard_lines) if hard_lines else "  {}"

    return f"""# Generated by MCP Recruiter interactive TUI
# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

title: "{title}"

problem_statement: >
  {problem}

# TUI search query used
# search_query: {search_query}

required_capabilities:
{caps_yaml}

preferred_capabilities:
{pref_yaml}

hard_requirements:
{hard_yaml}

top_n_candidates: {top_n}

scoring_weights:
  preset: {preset_name}

test_scenarios:
  - name: "基本调用测试"
    description: "验证工具能够被正常调用"
    test_cases:
      - name: "列举可用工具"
        mcp_tool_name: "tools/list"
        expected_behavior: "no_error"
"""


def _generate_default_test_scenarios(capabilities: list[str]) -> list[dict]:
    """Generate sensible default test scenarios based on declared capabilities."""
    scenarios = []

    # Always add a basic tools/list test
    scenarios.append({
        "name": "基本功能验证",
        "description": "验证 MCP 工具的基本调用能力",
        "test_cases": [
            {
                "name": "列举所有工具",
                "mcp_tool_name": "tools/list",
                "expected_behavior": "no_error",
            },
        ],
        "timeout_seconds": 30,
        "max_retries": 2,
    })

    return scenarios
