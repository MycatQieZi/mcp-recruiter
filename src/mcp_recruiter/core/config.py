from __future__ import annotations

from pathlib import Path
from typing import Optional
import yaml

from pydantic import BaseModel, Field

from .enums import ScoringPreset
from .models import ScoreWeights


class AppConfig(BaseModel):
    """Global application configuration."""

    # Workspace
    workspace_dir: str = "./sandbox-workspace"
    reports_dir: str = "./reports"
    data_dir: str = "./data"

    # Registry
    github_token: str = ""
    registry_cache_ttl_hours: dict[str, int] = Field(
        default_factory=lambda: {"github": 1, "npm": 6, "mcp_hub": 24}
    )

    # Sandbox
    sandbox_timeout_seconds: int = 120
    sandbox_memory_limit_mb: int = 512
    sandbox_network_mode: str = "none"
    sandbox_keep_containers: bool = False

    # Scoring defaults
    default_weights: ScoreWeights = Field(default_factory=ScoreWeights)
    default_top_n: int = 5

    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    # Search strategy
    search_web_enabled: bool = True
    search_awesome_enabled: bool = True
    search_pypi_enabled: bool = True
    search_use_llm_expansion: bool = True

    # Display
    verbose: bool = False


def load_config(path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML file or return defaults."""
    if path:
        config_path = Path(path)
        if config_path.exists():
            data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            return AppConfig(**data)
    return AppConfig()


def create_default_config(path: str) -> AppConfig:
    """Create a default config file and return it."""
    config = AppConfig()
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.dump(config.model_dump(), default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    return config
