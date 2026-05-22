"""Tests for perplexity_cli.output."""
from __future__ import annotations

import json
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from perplexity_cli.models import AskOutput, SearchOutput, SearchResultItem, UsageInfo
from perplexity_cli.output import (
    OutputFormat,
    render,
    render_error,
    render_streaming_chunk,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def capture_stdout(fn, *args, **kwargs):
    """Run fn(*args, **kwargs), return everything printed to stdout as a string."""
    buf = StringIO()
    with patch("sys.stdout", buf):
        fn(*args, **kwargs)
    return buf.getvalue()


def capture_stderr(fn, *args, **kwargs):
    """Run fn(*args, **kwargs), return everything printed to stderr as a string."""
    buf = StringIO()
    with patch("sys.stderr", buf):
        fn(*args, **kwargs)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# render — JSON mode (default)
# ---------------------------------------------------------------------------


class TestRenderJson:
    def test_search_output_json(self):
        data = SearchOutput(
            query="python",
            results=[SearchResultItem(url="https://python.org", name="Python")],
        )
        output = capture_stdout(render, data, OutputFormat.JSON)
        parsed = json.loads(output.strip())
        assert parsed["query"] == "python"
        assert parsed["results"][0]["url"] == "https://python.org"

    def test_ask_output_json(self):
        data = AskOutput(content="Answer", model="sonar")
        output = capture_stdout(render, data, OutputFormat.JSON)
        parsed = json.loads(output.strip())
        assert parsed["content"] == "Answer"
        assert parsed["model"] == "sonar"

    def test_json_output_is_compact(self):
        data = AskOutput(content="Hello", model="sonar")
        output = capture_stdout(render, data, OutputFormat.JSON)
        # Compact JSON has no indentation newlines beyond the trailing newline
        assert "\n  " not in output


# ---------------------------------------------------------------------------
# render — PRETTY mode
# ---------------------------------------------------------------------------


class TestRenderPretty:
    def test_search_output_pretty(self):
        data = SearchOutput(query="test", results=[])
        output = capture_stdout(render, data, OutputFormat.PRETTY)
        parsed = json.loads(output)
        assert parsed["query"] == "test"
        # Pretty-printed JSON contains indented lines
        assert "  " in output

    def test_ask_output_pretty(self):
        data = AskOutput(content="Hello", model="sonar-pro")
        output = capture_stdout(render, data, OutputFormat.PRETTY)
        parsed = json.loads(output)
        assert parsed["model"] == "sonar-pro"


# ---------------------------------------------------------------------------
# render — TEXT mode
# ---------------------------------------------------------------------------


class TestRenderText:
    def test_search_text_with_results(self):
        data = SearchOutput(
            query="python",
            results=[
                SearchResultItem(url="https://python.org", name="Python", snippet="Official site"),
                SearchResultItem(url="https://docs.python.org", name=None, snippet=None),
            ],
        )
        output = capture_stdout(render, data, OutputFormat.TEXT)
        assert "python" in output
        assert "https://python.org" in output
        assert "Official site" in output
        assert "(untitled)" in output  # name=None case
        assert "2 result(s)" in output

    def test_search_text_no_results(self):
        data = SearchOutput(query="noresults", results=[])
        output = capture_stdout(render, data, OutputFormat.TEXT)
        assert "No results found" in output

    def test_search_text_list_query(self):
        data = SearchOutput(query=["a", "b"], results=[])
        output = capture_stdout(render, data, OutputFormat.TEXT)
        assert "a, b" in output

    def test_ask_text_with_citations(self):
        data = AskOutput(
            content="The answer.",
            model="sonar",
            citations=["https://source1.com", "https://source2.com"],
        )
        output = capture_stdout(render, data, OutputFormat.TEXT)
        assert "The answer." in output
        assert "Sources:" in output
        assert "https://source1.com" in output

    def test_ask_text_with_related_questions(self):
        data = AskOutput(
            content="Answer",
            model="sonar",
            related_questions=["What else?", "Why?"],
        )
        output = capture_stdout(render, data, OutputFormat.TEXT)
        assert "Related questions:" in output
        assert "What else?" in output

    def test_ask_text_no_citations_no_related(self):
        data = AskOutput(content="Plain answer", model="sonar")
        output = capture_stdout(render, data, OutputFormat.TEXT)
        assert "Plain answer" in output
        assert "Sources" not in output
        assert "Related" not in output

    def test_unknown_model_type_fallback_to_json(self):
        """render() falls back to model_dump_json() for unrecognized model types."""
        from pydantic import BaseModel

        class CustomModel(BaseModel):
            value: str = "x"

        output = capture_stdout(render, CustomModel(), OutputFormat.TEXT)
        assert "x" in output


# ---------------------------------------------------------------------------
# render_error
# ---------------------------------------------------------------------------


class TestRenderError:
    def test_text_format_writes_to_stderr(self):
        with pytest.raises(SystemExit) as exc_info:
            render_error("Something broke", "details here", OutputFormat.TEXT, exit_code=1)
        assert exc_info.value.code == 1

    def test_text_format_stderr_content(self):
        stderr_buf = StringIO()
        with patch("sys.stderr", stderr_buf):
            with pytest.raises(SystemExit):
                render_error("Broken", "detail", OutputFormat.TEXT)
        output = stderr_buf.getvalue()
        assert "Error: Broken" in output
        assert "detail" in output

    def test_json_format_writes_json_to_stderr(self):
        stderr_buf = StringIO()
        with patch("sys.stderr", stderr_buf):
            with pytest.raises(SystemExit) as exc_info:
                render_error("API error", "bad request", OutputFormat.JSON, exit_code=4)
        assert exc_info.value.code == 4
        parsed = json.loads(stderr_buf.getvalue().strip())
        assert parsed["error"] == "API error"
        assert parsed["detail"] == "bad request"

    def test_pretty_format_writes_indented_json_to_stderr(self):
        stderr_buf = StringIO()
        with patch("sys.stderr", stderr_buf):
            with pytest.raises(SystemExit):
                render_error("Oops", "detail", OutputFormat.PRETTY)
        output = stderr_buf.getvalue()
        parsed = json.loads(output)
        assert parsed["error"] == "Oops"
        assert "  " in output  # indented

    def test_empty_detail_in_text_mode(self):
        stderr_buf = StringIO()
        with patch("sys.stderr", stderr_buf):
            with pytest.raises(SystemExit):
                render_error("Error only", "", OutputFormat.TEXT)
        output = stderr_buf.getvalue()
        assert "Error only" in output

    def test_default_exit_code_is_1(self):
        with pytest.raises(SystemExit) as exc_info:
            render_error("e", "d", OutputFormat.JSON)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# render_streaming_chunk
# ---------------------------------------------------------------------------


class TestRenderStreamingChunk:
    def test_text_mode_goes_to_stdout(self):
        stdout_buf = StringIO()
        with patch("sys.stdout", stdout_buf):
            render_streaming_chunk("hello", OutputFormat.TEXT)
        assert stdout_buf.getvalue() == "hello"

    def test_json_mode_goes_to_stderr(self):
        stderr_buf = StringIO()
        with patch("sys.stderr", stderr_buf):
            render_streaming_chunk("world", OutputFormat.JSON)
        assert stderr_buf.getvalue() == "world"

    def test_pretty_mode_goes_to_stderr(self):
        stderr_buf = StringIO()
        with patch("sys.stderr", stderr_buf):
            render_streaming_chunk("chunk", OutputFormat.PRETTY)
        assert stderr_buf.getvalue() == "chunk"

    def test_empty_string(self):
        buf = StringIO()
        with patch("sys.stdout", buf):
            render_streaming_chunk("", OutputFormat.TEXT)
        assert buf.getvalue() == ""
