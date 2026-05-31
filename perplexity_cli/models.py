from __future__ import annotations

import json
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Input models -- validate JSON from --json / stdin
# ---------------------------------------------------------------------------


class SearchInput(BaseModel):
    """Input schema for the search command.

    All fields mirror the Perplexity Search API parameters.
    When provided via --json or stdin, this model validates the input
    before forwarding to the API.
    """

    query: str | list[str] = Field(
        ..., description="Search query string or list of queries"
    )
    search_mode: Literal["web", "academic", "sec"] | None = Field(
        None, description="Source type: web (general), academic (scholarly), sec (financial filings)"
    )
    search_recency_filter: Literal["hour", "day", "week", "month", "year"] | None = Field(
        None, description="Only include results published within this time window"
    )
    search_domain_filter: list[str] | None = Field(
        None, description="Restrict results to these domains"
    )
    search_language_filter: list[str] | None = Field(
        None, description="ISO 639-1 language codes to filter by"
    )
    max_results: int | None = Field(None, description="Maximum number of results to return")
    max_tokens: int | None = Field(None, description="Maximum tokens in result snippets")
    country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code for geo-localized results")
    search_after_date_filter: str | None = Field(
        None, description="Only return results published after this date (MM/DD/YYYY)"
    )
    search_before_date_filter: str | None = Field(
        None, description="Only return results published before this date (MM/DD/YYYY)"
    )


class AskInput(BaseModel):
    """Input schema for the ask and chat commands.

    All fields map to Perplexity Chat Completions API parameters.
    The 'question' field becomes the user message content.
    """

    question: str = Field(..., description="The question to ask")
    model: str = Field("sonar", description="Sonar model to use (sonar, sonar-pro, sonar-reasoning, etc.)")
    system_prompt: str | None = Field(None, description="System prompt to guide the AI's behavior")
    search_mode: Literal["web", "academic", "sec"] | None = Field(
        None, description="Search mode for grounding the response"
    )
    search_recency_filter: Literal["hour", "day", "week", "month", "year"] | None = Field(
        None, description="Filter grounding sources by recency"
    )
    search_domain_filter: list[str] | None = Field(
        None, description="Restrict grounding to these domains"
    )
    temperature: float | None = Field(None, ge=0.0, le=2.0, description="Response randomness (0.0-2.0)")
    max_tokens: int | None = Field(None, description="Maximum tokens in the response")
    reasoning_effort: Literal["minimal", "low", "medium", "high"] | None = Field(
        None, description="How much reasoning effort to apply"
    )
    return_related_questions: bool = Field(False, description="Include related follow-up questions")
    return_images: bool = Field(False, description="Include image URLs in the response")


# ---------------------------------------------------------------------------
# Output models -- shape API responses for consistent output
# ---------------------------------------------------------------------------


class SearchResultItem(BaseModel):
    """A single search result."""

    url: str
    name: str | None = None
    snippet: str | None = None
    date: str | None = None


class SearchOutput(BaseModel):
    """Structured output for the search command."""

    query: str | list[str]
    results: list[SearchResultItem] = []


class UsageInfo(BaseModel):
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class AskOutput(BaseModel):
    """Structured output for the ask and chat commands."""

    content: str
    model: str
    citations: list[str] = []
    usage: UsageInfo | None = None
    related_questions: list[str] = []


# ---------------------------------------------------------------------------
# JSON + CLI merge helper
# ---------------------------------------------------------------------------


def merge_json_with_cli(
    model_class: type[T],
    json_str: str | None,
    cli_kwargs: dict[str, Any],
    config_defaults: dict[str, Any] | None = None,
) -> T:
    """Layer config defaults, JSON input, and CLI arguments into a validated model.

    Precedence (lowest to highest): config defaults < JSON < CLI. Config-file
    values seed the base, JSON overrides them, and explicit CLI arguments (those
    that are not None) win over both. This lets a global config set defaults
    while agents pass a JSON blob and humans override individual flags.
    """
    base: dict[str, Any] = dict(config_defaults or {})
    if json_str:
        base.update(json.loads(json_str))

    # Overlay CLI kwargs that were explicitly provided (not None)
    for key, value in cli_kwargs.items():
        if value is not None:
            base[key] = value

    return model_class.model_validate(base)
