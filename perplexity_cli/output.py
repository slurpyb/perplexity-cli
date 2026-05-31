from __future__ import annotations

import json
import sys
from enum import Enum

from pydantic import BaseModel

from .models import AskOutput, SearchOutput


class OutputFormat(str, Enum):
    JSON = "json"
    PRETTY = "pretty"
    TEXT = "text"


def resolve_output_format(
    text: bool, pretty: bool, config_output: str | None
) -> OutputFormat:
    """Resolve the output format with precedence: flags > config > JSON default.

    --text and --pretty (mutually exclusive flags) win. Otherwise the config
    file's `output` value applies, falling back to compact JSON.
    """
    if text:
        return OutputFormat.TEXT
    if pretty:
        return OutputFormat.PRETTY
    if config_output:
        return OutputFormat(config_output)
    return OutputFormat.JSON


def render(data: BaseModel, fmt: OutputFormat) -> None:
    """Render a Pydantic model to stdout in the requested format."""
    if fmt == OutputFormat.TEXT:
        if isinstance(data, SearchOutput):
            _render_search_text(data)
        elif isinstance(data, AskOutput):
            _render_ask_text(data)
        else:
            print(data.model_dump_json())
    elif fmt == OutputFormat.PRETTY:
        print(json.dumps(data.model_dump(mode="json"), indent=2))
    else:
        print(data.model_dump_json())


def render_error(message: str, detail: str, fmt: OutputFormat, exit_code: int = 1) -> None:
    """Render an error message and exit."""
    if fmt == OutputFormat.TEXT:
        print(f"Error: {message}", file=sys.stderr)
        if detail:
            print(detail, file=sys.stderr)
    else:
        error_obj = {"error": message, "detail": detail}
        if fmt == OutputFormat.PRETTY:
            print(json.dumps(error_obj, indent=2), file=sys.stderr)
        else:
            print(json.dumps(error_obj), file=sys.stderr)
    raise SystemExit(exit_code)


def render_streaming_chunk(content: str, fmt: OutputFormat) -> None:
    """Print a streaming token chunk.

    In text mode, streams to stdout (the user sees it live).
    In JSON/pretty mode, streams to stderr (so stdout stays clean for final JSON).
    """
    target = sys.stdout if fmt == OutputFormat.TEXT else sys.stderr
    print(content, end="", flush=True, file=target)


# ---------------------------------------------------------------------------
# Text-mode renderers
# ---------------------------------------------------------------------------


def _render_search_text(data: SearchOutput) -> None:
    query_display = data.query if isinstance(data.query, str) else ", ".join(data.query)
    print(f'Results for: "{query_display}"\n')

    if not data.results:
        print("  No results found.")
        return

    for i, result in enumerate(data.results, 1):
        print(f"  {i}. {result.name or '(untitled)'}")
        print(f"     {result.url}")
        if result.snippet:
            print(f"     {result.snippet}")
        print()

    print(f"Found {len(data.results)} result(s)")


def _render_ask_text(data: AskOutput) -> None:
    print(data.content)

    if data.citations:
        print("\nSources:")
        for i, citation in enumerate(data.citations, 1):
            print(f"  [{i}] {citation}")

    if data.related_questions:
        print("\nRelated questions:")
        for q in data.related_questions:
            print(f"  - {q}")
