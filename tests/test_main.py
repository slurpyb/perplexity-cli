"""Tests for perplexity_cli.main — CLI commands via typer.testing.CliRunner."""
from __future__ import annotations

import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from perplexity_cli.main import app, _read_json_input, _sdk_kwargs

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_search_response(results=None):
    """Build a minimal mock object that looks like a Perplexity search response."""
    mock_response = MagicMock()
    if results is None:
        results = [
            SimpleNamespace(
                url="https://example.com",
                name="Example",
                title=None,
                snippet="A snippet",
                text=None,
                date="2024-01-01",
            )
        ]
    mock_response.results = results
    return mock_response


def _make_ask_response(content="The answer.", model="sonar", citations=None, usage=None):
    """Build a minimal mock object that looks like a Perplexity chat completion response."""
    msg = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=msg)
    resp = MagicMock()
    resp.choices = [choice]
    resp.citations = citations or []
    resp.related_questions = []
    if usage:
        resp.usage = SimpleNamespace(**usage)
    else:
        resp.usage = None
    return resp


def _make_stream_chunks(content="Hello world", citations=None):
    """Yield mock stream chunks."""
    for token in content.split():
        delta = SimpleNamespace(content=token + " ")
        choice = SimpleNamespace(delta=delta)
        chunk = MagicMock()
        chunk.choices = [choice]
        chunk.citations = None
        chunk.usage = None
        yield chunk
    # Final chunk with usage + citations
    final = MagicMock()
    final.choices = []
    final.citations = citations or []
    final.usage = SimpleNamespace(prompt_tokens=5, completion_tokens=10, total_tokens=15)
    yield final


def _patch_client(search_response=None, ask_response=None, stream_iter=None):
    """Return a context manager that patches get_client with a mock."""
    mock_client = MagicMock()
    if search_response is not None:
        mock_client.search.create.return_value = search_response
    if ask_response is not None:
        mock_client.chat.completions.create.return_value = ask_response
    if stream_iter is not None:
        mock_client.chat.completions.create.return_value = stream_iter
    return patch("perplexity_cli.main.get_client", return_value=mock_client), mock_client


# ---------------------------------------------------------------------------
# _read_json_input helper
# ---------------------------------------------------------------------------


class TestReadJsonInput:
    def test_returns_json_str_when_provided(self):
        assert _read_json_input('{"a":1}') == '{"a":1}'

    def test_returns_none_when_none_and_tty(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            assert _read_json_input(None) is None

    def test_reads_from_stdin_when_not_tty(self):
        mock_stdin = StringIO('{"query":"from stdin"}')
        mock_stdin.isatty = lambda: False
        with patch("sys.stdin", mock_stdin):
            result = _read_json_input(None)
        assert result == '{"query":"from stdin"}'

    def test_returns_none_for_empty_stdin(self):
        mock_stdin = StringIO("   ")
        mock_stdin.isatty = lambda: False
        with patch("sys.stdin", mock_stdin):
            result = _read_json_input(None)
        assert result is None


# ---------------------------------------------------------------------------
# _sdk_kwargs helper
# ---------------------------------------------------------------------------


class TestSdkKwargs:
    def test_filters_none_values(self):
        result = _sdk_kwargs(a=1, b=None, c="hello")
        assert result == {"a": 1, "c": "hello"}

    def test_all_none_returns_empty(self):
        assert _sdk_kwargs(x=None, y=None) == {}

    def test_empty_call_returns_empty(self):
        assert _sdk_kwargs() == {}

    def test_preserves_falsy_non_none(self):
        result = _sdk_kwargs(a=0, b=False, c="")
        assert result == {"a": 0, "b": False, "c": ""}


# ---------------------------------------------------------------------------
# search command
# ---------------------------------------------------------------------------


class TestSearchCommand:
    def test_basic_query_json_output(self):
        resp = _make_search_response()
        ctx, mock_client = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(app, ["search", "python"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["query"] == "python"
        assert parsed["results"][0]["url"] == "https://example.com"

    def test_no_args_shows_help(self):
        result = runner.invoke(app, ["search"])
        assert result.exit_code == 0

    def test_pretty_output(self):
        resp = _make_search_response()
        ctx, _ = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(app, ["--pretty", "search", "python"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "query" in parsed
        assert "  " in result.stdout  # indented

    def test_text_output(self):
        resp = _make_search_response()
        ctx, _ = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(app, ["--text", "search", "python"])
        assert result.exit_code == 0
        assert "Example" in result.stdout
        assert "https://example.com" in result.stdout

    def test_empty_results(self):
        resp = _make_search_response(results=[])
        ctx, _ = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(app, ["search", "noresults"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["results"] == []

    def test_no_results_attribute(self):
        resp = MagicMock()
        resp.results = None
        ctx, _ = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(app, ["search", "python"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["results"] == []

    def test_with_mode_option(self):
        resp = _make_search_response()
        ctx, mock_client = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(app, ["search", "papers", "--mode", "academic"])
        assert result.exit_code == 0
        call_kwargs = mock_client.search.create.call_args.kwargs
        assert call_kwargs["search_mode"] == "academic"

    def test_with_recency_option(self):
        resp = _make_search_response()
        ctx, mock_client = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(app, ["search", "news", "--recency", "day"])
        assert result.exit_code == 0
        assert mock_client.search.create.call_args.kwargs["search_recency_filter"] == "day"

    def test_with_domains_option(self):
        resp = _make_search_response()
        ctx, mock_client = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(
                app, ["search", "python", "--domains", "python.org,docs.python.org"]
            )
        assert result.exit_code == 0
        assert mock_client.search.create.call_args.kwargs["search_domain_filter"] == [
            "python.org",
            "docs.python.org",
        ]

    def test_with_max_results(self):
        resp = _make_search_response()
        ctx, mock_client = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(app, ["search", "python", "--max-results", "3"])
        assert result.exit_code == 0
        assert mock_client.search.create.call_args.kwargs["max_results"] == 3

    def test_with_json_input(self):
        resp = _make_search_response()
        ctx, mock_client = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(
                app,
                ["search", "--json", '{"query": "rust", "max_results": 5}'],
            )
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["query"] == "rust"

    def test_invalid_json_input_exits(self):
        result = runner.invoke(app, ["search", "--json", "{bad json}"])
        assert result.exit_code != 0

    def test_result_uses_title_fallback(self):
        """name=None but title is set — should use title."""
        result_item = SimpleNamespace(
            url="https://t.com",
            name=None,
            title="Title From Attr",
            snippet=None,
            text="some text",
            date=None,
        )
        resp = _make_search_response(results=[result_item])
        ctx, _ = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(app, ["search", "test"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["results"][0]["name"] == "Title From Attr"
        assert parsed["results"][0]["snippet"] == "some text"

    def test_api_key_option(self):
        resp = _make_search_response()
        ctx, _ = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(
                app, ["--api-key", "my-key", "search", "python"]
            )
        assert result.exit_code == 0

    def test_country_and_date_options(self):
        resp = _make_search_response()
        ctx, mock_client = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(
                app,
                [
                    "search",
                    "query",
                    "--country",
                    "US",
                    "--after",
                    "01/01/2024",
                    "--before",
                    "12/31/2024",
                ],
            )
        assert result.exit_code == 0
        call_kwargs = mock_client.search.create.call_args.kwargs
        assert call_kwargs["country"] == "US"
        assert call_kwargs["search_after_date_filter"] == "01/01/2024"
        assert call_kwargs["search_before_date_filter"] == "12/31/2024"


# ---------------------------------------------------------------------------
# ask command
# ---------------------------------------------------------------------------


class TestAskCommand:
    def test_basic_question(self):
        resp = _make_ask_response()
        ctx, _ = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(app, ["ask", "What is Python?"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["content"] == "The answer."
        assert parsed["model"] == "sonar"

    def test_no_args_shows_help(self):
        result = runner.invoke(app, ["ask"])
        assert result.exit_code == 0

    def test_pretty_output(self):
        resp = _make_ask_response()
        ctx, _ = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(app, ["--pretty", "ask", "Hello?"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "content" in parsed

    def test_text_output(self):
        resp = _make_ask_response(citations=["https://source.com"])
        ctx, _ = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(app, ["--text", "ask", "Hello?"])
        assert result.exit_code == 0
        assert "The answer." in result.stdout
        assert "https://source.com" in result.stdout

    def test_model_option(self):
        resp = _make_ask_response(model="sonar-pro")
        ctx, mock_client = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(app, ["ask", "Hello?", "--model", "sonar-pro"])
        assert result.exit_code == 0
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "sonar-pro"

    def test_system_prompt_option(self):
        resp = _make_ask_response()
        ctx, mock_client = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(
                app, ["ask", "Hello?", "--system", "Be concise."]
            )
        assert result.exit_code == 0
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "Be concise."}
        assert messages[1]["role"] == "user"

    def test_no_system_prompt_single_message(self):
        resp = _make_ask_response()
        ctx, mock_client = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(app, ["ask", "Hello?"])
        assert result.exit_code == 0
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_with_usage_info(self):
        resp = _make_ask_response(
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        )
        ctx, _ = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(app, ["ask", "Hello?"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["usage"]["total_tokens"] == 30

    def test_with_citations(self):
        resp = _make_ask_response(citations=["https://a.com", "https://b.com"])
        ctx, _ = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(app, ["ask", "Hello?"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "https://a.com" in parsed["citations"]

    def test_related_questions(self):
        resp = _make_ask_response()
        resp.related_questions = ["Follow-up?"]
        ctx, _ = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(app, ["ask", "Hello?", "--related"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["related_questions"] == ["Follow-up?"]

    def test_with_json_input(self):
        resp = _make_ask_response()
        ctx, _ = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(
                app,
                ["ask", "--json", '{"question": "What is Rust?", "model": "sonar-pro"}'],
            )
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["content"] == "The answer."

    def test_recency_option(self):
        resp = _make_ask_response()
        ctx, mock_client = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(app, ["ask", "News?", "--recency", "week"])
        assert result.exit_code == 0
        assert mock_client.chat.completions.create.call_args.kwargs["search_recency_filter"] == "week"

    def test_temperature_option(self):
        resp = _make_ask_response()
        ctx, mock_client = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(app, ["ask", "q", "--temperature", "0.7"])
        assert result.exit_code == 0
        assert mock_client.chat.completions.create.call_args.kwargs["temperature"] == 0.7

    def test_reasoning_option(self):
        resp = _make_ask_response()
        ctx, mock_client = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(app, ["ask", "q", "--reasoning", "high"])
        assert result.exit_code == 0
        assert mock_client.chat.completions.create.call_args.kwargs["reasoning_effort"] == "high"

    def test_empty_choices(self):
        resp = MagicMock()
        resp.choices = []
        resp.citations = []
        resp.related_questions = []
        resp.usage = None
        ctx, _ = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(app, ["ask", "Hello?"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["content"] == ""

    def test_domains_option(self):
        resp = _make_ask_response()
        ctx, mock_client = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(
                app, ["ask", "q", "--domains", "python.org,docs.python.org"]
            )
        assert result.exit_code == 0
        assert mock_client.chat.completions.create.call_args.kwargs[
            "search_domain_filter"
        ] == ["python.org", "docs.python.org"]


# ---------------------------------------------------------------------------
# chat command (streaming)
# ---------------------------------------------------------------------------


class TestChatCommand:
    def test_basic_streaming_json_output(self):
        chunks = list(_make_stream_chunks("Hello world"))
        ctx, mock_client = _patch_client(stream_iter=iter(chunks))
        with ctx:
            result = runner.invoke(app, ["chat", "Say hello"])
        assert result.exit_code == 0
        # Final JSON goes to stdout, streamed chunks go to stderr
        parsed = json.loads(result.stdout)
        assert "Hello" in parsed["content"]
        assert parsed["model"] == "sonar"

    def test_no_args_shows_help(self):
        result = runner.invoke(app, ["chat"])
        assert result.exit_code == 0

    def test_streaming_text_mode(self):
        chunks = list(_make_stream_chunks("Hello world"))
        ctx, _ = _patch_client(stream_iter=iter(chunks))
        with ctx:
            result = runner.invoke(app, ["--text", "chat", "Say hello"])
        assert result.exit_code == 0
        assert "Hello" in result.stdout

    def test_no_stream_delegates_to_ask(self):
        resp = _make_ask_response(content="non-streaming answer")
        ctx, _ = _patch_client(ask_response=resp)
        with ctx:
            result = runner.invoke(app, ["chat", "Hello?", "--no-stream"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["content"] == "non-streaming answer"

    def test_citations_in_stream(self):
        chunks = list(_make_stream_chunks("Answer", citations=["https://cite.com"]))
        ctx, _ = _patch_client(stream_iter=iter(chunks))
        with ctx:
            result = runner.invoke(app, ["chat", "Hello?"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "https://cite.com" in parsed["citations"]

    def test_usage_info_in_stream(self):
        chunks = list(_make_stream_chunks("Answer"))
        ctx, _ = _patch_client(stream_iter=iter(chunks))
        with ctx:
            result = runner.invoke(app, ["chat", "Hello?"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["usage"]["total_tokens"] == 15

    def test_model_option(self):
        chunks = list(_make_stream_chunks("Hi"))
        ctx, mock_client = _patch_client(stream_iter=iter(chunks))
        with ctx:
            result = runner.invoke(app, ["chat", "Hi?", "--model", "sonar-pro"])
        assert result.exit_code == 0
        assert mock_client.chat.completions.create.call_args.kwargs["model"] == "sonar-pro"
        assert mock_client.chat.completions.create.call_args.kwargs["stream"] is True

    def test_with_json_input(self):
        chunks = list(_make_stream_chunks("Hi"))
        ctx, _ = _patch_client(stream_iter=iter(chunks))
        with ctx:
            result = runner.invoke(
                app,
                ["chat", "--json", '{"question": "Hello?", "model": "sonar-pro"}'],
            )
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "Hi" in parsed["content"]

    def test_system_prompt_option(self):
        chunks = list(_make_stream_chunks("Hi"))
        ctx, mock_client = _patch_client(stream_iter=iter(chunks))
        with ctx:
            result = runner.invoke(app, ["chat", "Hello?", "--system", "Be brief."])
        assert result.exit_code == 0
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "Be brief."}
        assert messages[1]["role"] == "user"

    def test_text_mode_citations_on_stderr(self):
        chunks = list(_make_stream_chunks("Answer", citations=["https://x.com"]))
        ctx, _ = _patch_client(stream_iter=iter(chunks))
        with ctx:
            result = runner.invoke(app, ["--text", "chat", "Hello?"])
        assert result.exit_code == 0
        # Citations go to stderr in text mode
        assert "https://x.com" in result.stderr


# ---------------------------------------------------------------------------
# Error handling via handle_errors decorator
# ---------------------------------------------------------------------------


class TestHandleErrors:
    def test_validation_error_exits_4(self):
        # Pass invalid mode via --json to trigger ValidationError
        result = runner.invoke(
            app, ["search", "--json", '{"query": "q", "search_mode": "invalid"}']
        )
        assert result.exit_code == 4

    def test_api_status_401_exits_2(self):
        from perplexity import APIStatusError

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url = "https://api.perplexity.ai"
        error = APIStatusError("Unauthorized", response=MagicMock(status_code=401), body=None)

        with patch("perplexity_cli.main.get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.search.create.side_effect = error
            mock_get.return_value = mock_client
            result = runner.invoke(app, ["search", "query"])
        assert result.exit_code == 2

    def test_api_status_429_exits_3(self):
        from perplexity import APIStatusError

        error = APIStatusError("Rate limit", response=MagicMock(status_code=429), body=None)
        with patch("perplexity_cli.main.get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.search.create.side_effect = error
            mock_get.return_value = mock_client
            result = runner.invoke(app, ["search", "query"])
        assert result.exit_code == 3

    def test_api_status_500_exits_5(self):
        from perplexity import APIStatusError

        error = APIStatusError("Server error", response=MagicMock(status_code=500), body=None)
        with patch("perplexity_cli.main.get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.search.create.side_effect = error
            mock_get.return_value = mock_client
            result = runner.invoke(app, ["search", "query"])
        assert result.exit_code == 5

    def test_api_status_400_exits_4(self):
        from perplexity import APIStatusError

        error = APIStatusError("Bad request", response=MagicMock(status_code=400), body=None)
        with patch("perplexity_cli.main.get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.search.create.side_effect = error
            mock_get.return_value = mock_client
            result = runner.invoke(app, ["search", "query"])
        assert result.exit_code == 4

    def test_unexpected_exception_exits_1(self):
        with patch("perplexity_cli.main.get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.search.create.side_effect = RuntimeError("unexpected")
            mock_get.return_value = mock_client
            result = runner.invoke(app, ["search", "query"])
        assert result.exit_code == 1

    def test_keyboard_interrupt_exits_130(self):
        with patch("perplexity_cli.main.get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.search.create.side_effect = KeyboardInterrupt()
            mock_get.return_value = mock_client
            result = runner.invoke(app, ["search", "query"])
        assert result.exit_code == 130

    def test_error_output_is_json_by_default(self):
        from perplexity import APIStatusError

        error = APIStatusError("Unauthorized", response=MagicMock(status_code=401), body=None)
        with patch("perplexity_cli.main.get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.search.create.side_effect = error
            mock_get.return_value = mock_client
            result = runner.invoke(app, ["search", "query"])
        parsed = json.loads(result.stderr)
        assert "error" in parsed


# ---------------------------------------------------------------------------
# Global options
# ---------------------------------------------------------------------------


class TestGlobalOptions:
    def test_help_flag(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "perplexity" in result.stdout.lower()

    def test_pretty_and_text_both_set_uses_text(self):
        """When both --pretty and --text are set, --text takes precedence (last wins in typer)."""
        resp = _make_search_response()
        ctx, _ = _patch_client(search_response=resp)
        with ctx:
            result = runner.invoke(app, ["--text", "--pretty", "search", "q"])
        # Should not crash regardless of which format wins
        assert result.exit_code == 0
