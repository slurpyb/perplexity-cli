from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CONFIG_DIR_NAME = "perplexity-cli"
CONFIG_FILE_NAME = "perplexity-cli.json"


def config_path() -> Path:
    """Resolve the config file location.

    Honors $XDG_CONFIG_HOME, falling back to ~/.config. The file itself need
    not exist -- callers handle absence gracefully.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    root = Path(xdg) if xdg else Path.home() / ".config"
    return root / CONFIG_DIR_NAME / CONFIG_FILE_NAME


class Config(BaseModel):
    """Global, read-only configuration loaded from the config file.

    Every field is optional. Values here are the LOWEST-priority source:
    CLI flags and environment variables override them (see client.resolve_keys
    and models.merge_json_with_cli). Unknown keys are rejected so typos surface
    as errors instead of being silently ignored.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    perplexity_api_key: str | None = None
    openrouter_api_key: str | None = None
    model: str | None = None
    output: Literal["json", "pretty", "text"] | None = None
    search_mode: Literal["web", "academic", "sec"] | None = None
    recency: Literal["hour", "day", "week", "month", "year"] | None = None
    reasoning_effort: Literal["minimal", "low", "medium", "high"] | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)

    def ask_defaults(self) -> dict[str, Any]:
        """Config-sourced defaults keyed by AskInput field names (non-None only)."""
        mapped = {
            "model": self.model,
            "search_mode": self.search_mode,
            "search_recency_filter": self.recency,
            "reasoning_effort": self.reasoning_effort,
            "temperature": self.temperature,
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def search_defaults(self) -> dict[str, Any]:
        """Config-sourced defaults keyed by SearchInput field names (non-None only)."""
        mapped = {
            "search_mode": self.search_mode,
            "search_recency_filter": self.recency,
        }
        return {k: v for k, v in mapped.items() if v is not None}


def _warn_if_insecure(path: Path) -> None:
    """Warn (without blocking) when the file is group/world readable."""
    try:
        mode = path.stat().st_mode
    except OSError:
        return
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        print(
            f"Warning: {path} is group/world-readable and may contain secrets; "
            f"run: chmod 600 {path}",
            file=sys.stderr,
        )


def load_config(path: Path | None = None) -> Config:
    """Load and validate the config file.

    A missing file returns an empty Config (no error). Malformed JSON raises
    json.JSONDecodeError and invalid/unknown fields raise pydantic
    ValidationError -- both are mapped to exit code 4 by the caller.
    """
    resolved = path or config_path()
    if not resolved.exists():
        return Config()
    _warn_if_insecure(resolved)
    data = json.loads(resolved.read_text(encoding="utf-8"))
    return Config.model_validate(data)
