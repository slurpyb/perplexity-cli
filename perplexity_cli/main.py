from __future__ import annotations

import json
import sys
from functools import wraps
from typing import Annotated, Any

import os

import typer
from pydantic import ValidationError
from perplexity import APIError, APIStatusError

from .client import get_client
from .models import AskInput, AskOutput, SearchInput, SearchOutput, SearchResultItem, UsageInfo, merge_json_with_cli
from .output import OutputFormat, render, render_error, render_streaming_chunk

app = typer.Typer(
    name="perplexity-cli",
    help=(
        "Query the Perplexity AI API from the command line.\n\n"
        "Supports web search, single-question chat completions, and streaming conversations. "
        "Designed for both interactive use and programmatic use by AI agents.\n\n"
        "All commands output compact JSON by default (ideal for piping to jq or consumption by agents). "
        "Use --pretty for formatted JSON or --text for human-readable output.\n\n"
        "API key: Set PERPLEXITY_API_KEY in your environment.\n"
        '  export PERPLEXITY_API_KEY="$(cat ~/.secrets/perplexity-api-key)"'
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ---------------------------------------------------------------------------
# Global state passed through typer context
# ---------------------------------------------------------------------------


class State:
    def __init__(self) -> None:
        self.fmt: OutputFormat = OutputFormat.JSON
        self.api_key: str | None = None


# ---------------------------------------------------------------------------
# Error handling decorator
# ---------------------------------------------------------------------------


def handle_errors(f):
    """Wrap a command function with structured error handling."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        # Extract format from context if available
        ctx = kwargs.get("ctx") or (args[0] if args and isinstance(args[0], typer.Context) else None)
        fmt = OutputFormat.JSON
        if ctx and ctx.obj:
            fmt = ctx.obj.fmt

        try:
            return f(*args, **kwargs)
        except SystemExit:
            raise
        except ValidationError as exc:
            render_error(
                "Invalid input",
                str(exc),
                fmt,
                exit_code=4,
            )
        except json.JSONDecodeError as exc:
            render_error(
                "Invalid JSON input",
                str(exc),
                fmt,
                exit_code=4,
            )
        except APIStatusError as exc:
            code_map = {401: 2, 429: 3, 400: 4}
            exit_code = code_map.get(exc.status_code, 5 if exc.status_code >= 500 else 1)
            render_error(
                f"API error ({exc.status_code})",
                str(exc.message) if hasattr(exc, "message") else str(exc),
                fmt,
                exit_code=exit_code,
            )
        except KeyboardInterrupt:
            print(file=sys.stderr)
            raise SystemExit(130)
        except APIError as exc:
            render_error("API error", str(exc), fmt, exit_code=5)
        except Exception as exc:
            if os.environ.get("PERPLEXITY_CLI_DEBUG"):
                raise
            render_error(
                "Internal CLI error",
                f"{type(exc).__name__}: {exc}. Set PERPLEXITY_CLI_DEBUG=1 for traceback.",
                fmt,
                exit_code=70,
            )

    return wrapper


# ---------------------------------------------------------------------------
# Global callback -- sets output format and API key
# ---------------------------------------------------------------------------


@app.callback()
def main(
    ctx: typer.Context,
    pretty: Annotated[
        bool,
        typer.Option(
            "--pretty",
            help=(
                "Output pretty-printed JSON with indentation. "
                "Useful when reading output in a terminal. "
                "Mutually exclusive with --text."
            ),
        ),
    ] = False,
    text: Annotated[
        bool,
        typer.Option(
            "--text",
            help=(
                "Output human-readable text instead of JSON. "
                "Shows answers, citations, and search results in a readable format. "
                "Mutually exclusive with --pretty."
            ),
        ),
    ] = False,
    api_key: Annotated[
        str | None,
        typer.Option(
            "--api-key",
            envvar="PERPLEXITY_API_KEY",
            help=(
                "Perplexity API key. If not provided, reads from the PERPLEXITY_API_KEY "
                "environment variable. Get your key at https://www.perplexity.ai/settings/api"
            ),
            show_default=False,
        ),
    ] = None,
) -> None:
    """Configure global options for output format and authentication."""
    state = State()
    if text:
        state.fmt = OutputFormat.TEXT
    elif pretty:
        state.fmt = OutputFormat.PRETTY
    state.api_key = api_key
    ctx.obj = state


# ---------------------------------------------------------------------------
# Helper: read JSON from --json flag or stdin
# ---------------------------------------------------------------------------


def _read_json_input(json_input: str | None) -> str | None:
    """Return JSON string from --json flag, stdin pipe, or None."""
    if json_input is not None:
        return json_input
    if not sys.stdin.isatty():
        data = sys.stdin.read().strip()
        return data if data else None
    return None


# ---------------------------------------------------------------------------
# Helper: build SDK kwargs, excluding None values
# ---------------------------------------------------------------------------


def _sdk_kwargs(**kwargs: Any) -> dict[str, Any]:
    """Filter out None values so the SDK uses its own defaults."""
    return {k: v for k, v in kwargs.items() if v is not None}


def _split_csv(value: str | None) -> list[str] | None:
    """Split comma-separated string, trim entries, drop empties."""
    if value is None:
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    return items or None


# ---------------------------------------------------------------------------
# search command
# ---------------------------------------------------------------------------


@app.command()
@handle_errors
def search(
    ctx: typer.Context,
    query: Annotated[
        str | None,
        typer.Argument(
            help=(
                "The search query. What you want to find on the web. "
                "Can be a natural language question or keyword-based query.\n\n"
                "Example: 'latest Python 3.13 features'\n\n"
                "Optional when using --json or stdin to provide the query."
            ),
            show_default=False,
        ),
    ] = None,
    mode: Annotated[
        str | None,
        typer.Option(
            "--mode",
            "-m",
            help=(
                "Search mode controlling which sources to prioritize.\n\n"
                "  [bold]web[/bold]       General web search (default)\n"
                "  [bold]academic[/bold]  Scholarly and peer-reviewed sources\n"
                "  [bold]sec[/bold]       SEC filings and financial documents\n\n"
                "Use 'academic' for research papers. Use 'sec' for company financials."
            ),
        ),
    ] = None,
    recency: Annotated[
        str | None,
        typer.Option(
            "--recency",
            "-r",
            help=(
                "Filter results by how recently they were published.\n\n"
                "  hour | day | week | month | year\n\n"
                "Useful for finding recent news or filtering out stale content."
            ),
        ),
    ] = None,
    domains: Annotated[
        str | None,
        typer.Option(
            "--domains",
            "-d",
            help=(
                "Comma-separated list of domains to restrict results to. "
                "Only results from these domains will be returned.\n\n"
                "Example: --domains 'github.com,stackoverflow.com'"
            ),
        ),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option(
            "--language",
            "-l",
            help=(
                "ISO 639-1 language code(s), comma-separated. "
                "Filter results by language.\n\n"
                "Example: --language 'en,fr'"
            ),
        ),
    ] = None,
    max_results: Annotated[
        int | None,
        typer.Option(
            "--max-results",
            "-n",
            help="Maximum number of search results to return. Lower values are faster and cheaper.",
        ),
    ] = None,
    country: Annotated[
        str | None,
        typer.Option(
            "--country",
            help="ISO 3166-1 alpha-2 country code for geo-localized results. Example: 'US'",
        ),
    ] = None,
    after: Annotated[
        str | None,
        typer.Option(
            "--after",
            help="Only return results published after this date. Format: MM/DD/YYYY",
        ),
    ] = None,
    before: Annotated[
        str | None,
        typer.Option(
            "--before",
            help="Only return results published before this date. Format: MM/DD/YYYY",
        ),
    ] = None,
    json_input: Annotated[
        str | None,
        typer.Option(
            "--json",
            "-j",
            help=(
                "JSON string with search parameters. Overrides CLI options.\n\n"
                'Example: --json \'{"query": "AI news", "search_mode": "web", "max_results": 5}\'\n\n'
                "You can also pipe JSON via stdin:\n"
                "  echo '{\"query\": \"AI news\"}' | perplexity-cli search"
            ),
        ),
    ] = None,
) -> None:
    """Search the web and retrieve relevant page contents.

    Returns raw search results -- titles, URLs, and snippets -- without an AI-generated answer.
    Use 'ask' or 'chat' for AI-answered questions grounded in search.

    [bold]Examples:[/bold]

      perplexity-cli search "latest AI developments"

      perplexity-cli search "climate research" --mode academic --recency year

      perplexity-cli search --json '{"query": "Python 3.13", "max_results": 3}'
    """
    state: State = ctx.obj
    raw_json = _read_json_input(json_input)

    # Build CLI kwargs for merge
    cli_kwargs: dict[str, Any] = {
        "search_mode": mode,
        "search_recency_filter": recency,
        "search_domain_filter": _split_csv(domains),
        "search_language_filter": _split_csv(language),
        "max_results": max_results,
        "country": country,
        "search_after_date_filter": after,
        "search_before_date_filter": before,
    }

    if query is not None:
        cli_kwargs["query"] = query

    if raw_json or any(v is not None for v in cli_kwargs.values()):
        params = merge_json_with_cli(SearchInput, raw_json, cli_kwargs)
    elif query is not None:
        params = SearchInput(query=query)
    else:
        typer.echo(ctx.get_help())
        raise SystemExit(0)

    client = get_client(state.api_key)
    response = client.search.create(**_sdk_kwargs(
        query=params.query,
        search_mode=params.search_mode,
        search_recency_filter=params.search_recency_filter,
        search_domain_filter=params.search_domain_filter,
        search_language_filter=params.search_language_filter,
        max_results=params.max_results,
        max_tokens=params.max_tokens,
        country=params.country,
        search_after_date_filter=params.search_after_date_filter,
        search_before_date_filter=params.search_before_date_filter,
    ))

    results = []
    if hasattr(response, "results") and response.results:
        for r in response.results:
            results.append(SearchResultItem(
                url=getattr(r, "url", ""),
                name=getattr(r, "name", None) or getattr(r, "title", None),
                snippet=getattr(r, "snippet", None) or getattr(r, "text", None),
                date=getattr(r, "date", None),
            ))

    output = SearchOutput(query=params.query, results=results)
    render(output, state.fmt)


# ---------------------------------------------------------------------------
# ask command
# ---------------------------------------------------------------------------


@app.command()
@handle_errors
def ask(
    ctx: typer.Context,
    question: Annotated[
        str | None,
        typer.Argument(
            help=(
                "The question to ask Perplexity AI. Provide a natural language question "
                "and get an AI-generated answer grounded in real-time web search results.\n\n"
                "Example: 'What are the key features of Python 3.13?'\n\n"
                "Optional when using --json or stdin."
            ),
            show_default=False,
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help=(
                "The Sonar model to use for generating the answer.\n\n"
                "  [bold]sonar[/bold]               Fast, affordable general-purpose model (default)\n"
                "  [bold]sonar-pro[/bold]            More capable, multi-step reasoning\n"
                "  [bold]sonar-reasoning[/bold]      Specialized for complex analytical questions\n"
                "  [bold]sonar-deep-research[/bold]  Extended research with multiple search rounds\n\n"
                "Use 'sonar' for quick factual questions. "
                "Use 'sonar-pro' for deeper analysis."
            ),
        ),
    ] = None,
    system_prompt: Annotated[
        str | None,
        typer.Option(
            "--system",
            "-s",
            help=(
                "System prompt to guide the AI's behavior and response style. "
                "Sets the persona, tone, or constraints for the response.\n\n"
                "Example: --system 'Respond in bullet points. Be concise.'"
            ),
        ),
    ] = None,
    mode: Annotated[
        str | None,
        typer.Option(
            "--mode",
            help="Search mode: web (default), academic, or sec.",
        ),
    ] = None,
    recency: Annotated[
        str | None,
        typer.Option(
            "--recency",
            "-r",
            help=(
                "Filter search grounding by recency: hour, day, week, month, year. "
                "Ensures the AI's answer is based on recent sources."
            ),
        ),
    ] = None,
    domains: Annotated[
        str | None,
        typer.Option(
            "--domains",
            "-d",
            help="Comma-separated domains to restrict search grounding.",
        ),
    ] = None,
    temperature: Annotated[
        float | None,
        typer.Option(
            "--temperature",
            "-t",
            help=(
                "Controls randomness in the response (0.0-2.0). "
                "Lower values (0.0-0.3) = focused. Higher values (0.7+) = creative."
            ),
            min=0.0,
            max=2.0,
        ),
    ] = None,
    max_tokens: Annotated[
        int | None,
        typer.Option(
            "--max-tokens",
            help="Maximum number of tokens in the response.",
        ),
    ] = None,
    reasoning: Annotated[
        str | None,
        typer.Option(
            "--reasoning",
            help=(
                "Controls reasoning effort: minimal, low, medium, high. "
                "Higher effort = better answers for complex questions, but slower."
            ),
        ),
    ] = None,
    related: Annotated[
        bool,
        typer.Option(
            "--related",
            help="Include related follow-up questions in the response.",
        ),
    ] = False,
    images: Annotated[
        bool,
        typer.Option(
            "--images",
            help="Include image URLs in the response when available.",
        ),
    ] = False,
    json_input: Annotated[
        str | None,
        typer.Option(
            "--json",
            "-j",
            help=(
                "JSON string with all parameters. CLI options override JSON values.\n\n"
                'Example: --json \'{"question": "...", "model": "sonar-pro"}\''
            ),
        ),
    ] = None,
) -> None:
    """Ask a question and get an AI-generated answer grounded in web search.

    Sends a single question to Perplexity's Chat Completions API and returns
    a complete answer with citations. Non-streaming -- waits for the full response.

    Use 'chat' instead for streaming output.

    [bold]Examples:[/bold]

      perplexity-cli ask "What is quantum computing?"

      perplexity-cli ask "Compare React vs Vue" --model sonar-pro --reasoning high

      perplexity-cli --text ask "Latest Python features" --recency month
    """
    state: State = ctx.obj
    raw_json = _read_json_input(json_input)

    cli_kwargs: dict[str, Any] = {
        "model": model,
        "system_prompt": system_prompt,
        "search_mode": mode,
        "search_recency_filter": recency,
        "search_domain_filter": _split_csv(domains),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "reasoning_effort": reasoning,
        "return_related_questions": related if related else None,
        "return_images": images if images else None,
    }

    if question is not None:
        cli_kwargs["question"] = question

    if raw_json or any(v is not None for v in cli_kwargs.values()):
        params = merge_json_with_cli(AskInput, raw_json, cli_kwargs)
    else:
        typer.echo(ctx.get_help())
        raise SystemExit(0)

    # Build messages
    messages: list[dict[str, str]] = []
    if params.system_prompt:
        messages.append({"role": "system", "content": params.system_prompt})
    messages.append({"role": "user", "content": params.question})

    client = get_client(state.api_key)
    response = client.chat.completions.create(**_sdk_kwargs(
        messages=messages,
        model=params.model,
        stream=False,
        search_mode=params.search_mode,
        search_recency_filter=params.search_recency_filter,
        search_domain_filter=params.search_domain_filter,
        temperature=params.temperature,
        max_tokens=params.max_tokens,
        reasoning_effort=params.reasoning_effort,
        return_related_questions=params.return_related_questions or None,
        return_images=params.return_images or None,
    ))

    if not response.choices:
        render_error(
            "Empty response from API",
            "The API returned no choices. This may indicate a content filter or upstream error.",
            state.fmt,
            exit_code=5,
        )

    msg = response.choices[0].message
    content = msg.content if msg and msg.content else ""
    if not content:
        render_error(
            "Empty response from API",
            "The API returned a choice with no content.",
            state.fmt,
            exit_code=5,
        )

    citations = list(response.citations) if hasattr(response, "citations") and response.citations else []

    usage_info = None
    if hasattr(response, "usage") and response.usage:
        u = response.usage
        usage_info = UsageInfo(
            prompt_tokens=getattr(u, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(u, "completion_tokens", 0) or 0,
            total_tokens=getattr(u, "total_tokens", 0) or 0,
        )

    related_qs: list[str] = []
    if hasattr(response, "related_questions") and response.related_questions:
        related_qs = list(response.related_questions)

    output = AskOutput(
        content=content,
        model=params.model,
        citations=citations,
        usage=usage_info,
        related_questions=related_qs,
    )
    render(output, state.fmt)


# ---------------------------------------------------------------------------
# chat command (streaming)
# ---------------------------------------------------------------------------


@app.command()
@handle_errors
def chat(
    ctx: typer.Context,
    question: Annotated[
        str | None,
        typer.Argument(
            help=(
                "The question or message to send. The response streams to stdout in real time.\n\n"
                "Example: perplexity-cli chat 'Explain quantum computing simply'"
            ),
            show_default=False,
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Model to use. See 'ask --help' for descriptions."),
    ] = None,
    system_prompt: Annotated[
        str | None,
        typer.Option("--system", "-s", help="System prompt to guide the AI's behavior."),
    ] = None,
    mode: Annotated[
        str | None,
        typer.Option("--mode", help="Search mode: web, academic, or sec."),
    ] = None,
    recency: Annotated[
        str | None,
        typer.Option("--recency", "-r", help="Filter grounding by recency."),
    ] = None,
    domains: Annotated[
        str | None,
        typer.Option("--domains", "-d", help="Comma-separated domain filter."),
    ] = None,
    temperature: Annotated[
        float | None,
        typer.Option("--temperature", "-t", min=0.0, max=2.0, help="Response randomness (0.0-2.0)."),
    ] = None,
    max_tokens: Annotated[
        int | None,
        typer.Option("--max-tokens", help="Maximum tokens in the response."),
    ] = None,
    reasoning: Annotated[
        str | None,
        typer.Option("--reasoning", help="Reasoning effort: minimal, low, medium, high."),
    ] = None,
    no_stream: Annotated[
        bool,
        typer.Option(
            "--no-stream",
            help="Disable streaming and wait for the complete response. Equivalent to 'ask'.",
        ),
    ] = False,
    json_input: Annotated[
        str | None,
        typer.Option("--json", "-j", help="JSON string with parameters."),
    ] = None,
) -> None:
    """Stream an AI-generated answer with real-time token output.

    Like 'ask', but streams tokens as they arrive. In text mode, you see the
    answer appear word-by-word. In JSON mode, tokens stream to stderr while
    the final structured JSON goes to stdout.

    [bold]Examples:[/bold]

      perplexity-cli --text chat "Explain quantum computing"

      perplexity-cli chat "Latest AI news" --model sonar-pro
    """
    state: State = ctx.obj

    if no_stream:
        # Delegate to ask logic by re-invoking with same params
        ctx.invoke(
            ask,
            ctx=ctx,
            question=question,
            model=model,
            system_prompt=system_prompt,
            mode=mode,
            recency=recency,
            domains=domains,
            temperature=temperature,
            max_tokens=max_tokens,
            reasoning=reasoning,
            json_input=json_input,
        )
        return

    raw_json = _read_json_input(json_input)

    cli_kwargs: dict[str, Any] = {
        "model": model,
        "system_prompt": system_prompt,
        "search_mode": mode,
        "search_recency_filter": recency,
        "search_domain_filter": _split_csv(domains),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "reasoning_effort": reasoning,
    }

    if question is not None:
        cli_kwargs["question"] = question

    if raw_json or any(v is not None for v in cli_kwargs.values()):
        params = merge_json_with_cli(AskInput, raw_json, cli_kwargs)
    else:
        typer.echo(ctx.get_help())
        raise SystemExit(0)

    messages: list[dict[str, str]] = []
    if params.system_prompt:
        messages.append({"role": "system", "content": params.system_prompt})
    messages.append({"role": "user", "content": params.question})

    client = get_client(state.api_key)
    stream = client.chat.completions.create(**_sdk_kwargs(
        messages=messages,
        model=params.model,
        stream=True,
        search_mode=params.search_mode,
        search_recency_filter=params.search_recency_filter,
        search_domain_filter=params.search_domain_filter,
        temperature=params.temperature,
        max_tokens=params.max_tokens,
        reasoning_effort=params.reasoning_effort,
    ))

    full_content = ""
    citations: list[str] = []
    usage_info = None
    stream_error: BaseException | None = None

    try:
        for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    render_streaming_chunk(delta.content, state.fmt)
                    full_content += delta.content

            if hasattr(chunk, "citations") and chunk.citations:
                citations = list(chunk.citations)
            if hasattr(chunk, "usage") and chunk.usage:
                u = chunk.usage
                usage_info = UsageInfo(
                    prompt_tokens=getattr(u, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(u, "completion_tokens", 0) or 0,
                    total_tokens=getattr(u, "total_tokens", 0) or 0,
                )
    except BaseException as exc:
        stream_error = exc

    # Finish streaming output -- always flush partial state, even on error
    if state.fmt == OutputFormat.TEXT:
        print()  # newline after streamed content
        if citations:
            print("\nSources:", file=sys.stderr)
            for i, c in enumerate(citations, 1):
                print(f"  [{i}] {c}", file=sys.stderr)
    else:
        print(file=sys.stderr)  # newline after stderr progress
        output = AskOutput(
            content=full_content,
            model=params.model or "sonar",
            citations=citations,
            usage=usage_info,
        )
        render(output, state.fmt)

    if stream_error is not None:
        raise stream_error
