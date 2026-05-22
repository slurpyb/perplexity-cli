"""Tests for perplexity_cli.models."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from perplexity_cli.models import (
    AskInput,
    AskOutput,
    SearchInput,
    SearchOutput,
    SearchResultItem,
    UsageInfo,
    merge_json_with_cli,
)


# ---------------------------------------------------------------------------
# SearchInput
# ---------------------------------------------------------------------------


class TestSearchInput:
    def test_minimal_string_query(self):
        m = SearchInput(query="python")
        assert m.query == "python"
        assert m.search_mode is None

    def test_list_query(self):
        m = SearchInput(query=["python", "rust"])
        assert m.query == ["python", "rust"]

    def test_all_optional_fields(self):
        m = SearchInput(
            query="test",
            search_mode="academic",
            search_recency_filter="week",
            search_domain_filter=["example.com"],
            search_language_filter=["en", "fr"],
            max_results=5,
            max_tokens=200,
            country="US",
            search_after_date_filter="01/01/2024",
            search_before_date_filter="12/31/2024",
        )
        assert m.search_mode == "academic"
        assert m.search_recency_filter == "week"
        assert m.search_domain_filter == ["example.com"]
        assert m.search_language_filter == ["en", "fr"]
        assert m.max_results == 5
        assert m.max_tokens == 200
        assert m.country == "US"
        assert m.search_after_date_filter == "01/01/2024"
        assert m.search_before_date_filter == "12/31/2024"

    def test_invalid_search_mode_raises(self):
        with pytest.raises(ValidationError):
            SearchInput(query="test", search_mode="invalid")

    def test_invalid_recency_raises(self):
        with pytest.raises(ValidationError):
            SearchInput(query="test", search_recency_filter="century")

    def test_missing_query_raises(self):
        with pytest.raises(ValidationError):
            SearchInput()  # type: ignore[call-arg]

    def test_valid_search_modes(self):
        for mode in ("web", "academic", "sec"):
            m = SearchInput(query="q", search_mode=mode)
            assert m.search_mode == mode

    def test_valid_recency_values(self):
        for recency in ("hour", "day", "week", "month", "year"):
            m = SearchInput(query="q", search_recency_filter=recency)
            assert m.search_recency_filter == recency


# ---------------------------------------------------------------------------
# AskInput
# ---------------------------------------------------------------------------


class TestAskInput:
    def test_minimal(self):
        m = AskInput(question="What is Python?")
        assert m.question == "What is Python?"
        assert m.model == "sonar"
        assert m.return_related_questions is False
        assert m.return_images is False

    def test_all_fields(self):
        m = AskInput(
            question="Hello",
            model="sonar-pro",
            system_prompt="Be concise.",
            search_mode="web",
            search_recency_filter="day",
            search_domain_filter=["docs.python.org"],
            temperature=0.5,
            max_tokens=500,
            reasoning_effort="high",
            return_related_questions=True,
            return_images=True,
        )
        assert m.model == "sonar-pro"
        assert m.system_prompt == "Be concise."
        assert m.temperature == 0.5
        assert m.reasoning_effort == "high"
        assert m.return_related_questions is True
        assert m.return_images is True

    def test_temperature_boundary_zero(self):
        m = AskInput(question="q", temperature=0.0)
        assert m.temperature == 0.0

    def test_temperature_boundary_two(self):
        m = AskInput(question="q", temperature=2.0)
        assert m.temperature == 2.0

    def test_temperature_below_min_raises(self):
        with pytest.raises(ValidationError):
            AskInput(question="q", temperature=-0.1)

    def test_temperature_above_max_raises(self):
        with pytest.raises(ValidationError):
            AskInput(question="q", temperature=2.1)

    def test_invalid_reasoning_effort_raises(self):
        with pytest.raises(ValidationError):
            AskInput(question="q", reasoning_effort="extreme")

    def test_valid_reasoning_efforts(self):
        for effort in ("minimal", "low", "medium", "high"):
            m = AskInput(question="q", reasoning_effort=effort)
            assert m.reasoning_effort == effort

    def test_missing_question_raises(self):
        with pytest.raises(ValidationError):
            AskInput()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class TestSearchResultItem:
    def test_url_required(self):
        item = SearchResultItem(url="https://example.com")
        assert item.url == "https://example.com"
        assert item.name is None
        assert item.snippet is None
        assert item.date is None

    def test_all_fields(self):
        item = SearchResultItem(
            url="https://example.com",
            name="Example",
            snippet="A snippet.",
            date="2024-01-01",
        )
        assert item.name == "Example"
        assert item.snippet == "A snippet."
        assert item.date == "2024-01-01"


class TestSearchOutput:
    def test_string_query_empty_results(self):
        out = SearchOutput(query="python")
        assert out.query == "python"
        assert out.results == []

    def test_list_query_with_results(self):
        out = SearchOutput(
            query=["python", "rust"],
            results=[SearchResultItem(url="https://python.org", name="Python")],
        )
        assert out.query == ["python", "rust"]
        assert len(out.results) == 1


class TestUsageInfo:
    def test_defaults_to_zero(self):
        u = UsageInfo()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.total_tokens == 0

    def test_explicit_values(self):
        u = UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        assert u.total_tokens == 30


class TestAskOutput:
    def test_minimal(self):
        out = AskOutput(content="Answer", model="sonar")
        assert out.content == "Answer"
        assert out.citations == []
        assert out.usage is None
        assert out.related_questions == []

    def test_full(self):
        out = AskOutput(
            content="Answer",
            model="sonar-pro",
            citations=["https://a.com"],
            usage=UsageInfo(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            related_questions=["Follow-up?"],
        )
        assert out.citations == ["https://a.com"]
        assert out.usage.total_tokens == 15
        assert out.related_questions == ["Follow-up?"]


# ---------------------------------------------------------------------------
# merge_json_with_cli
# ---------------------------------------------------------------------------


class TestMergeJsonWithCli:
    def test_json_only(self):
        result = merge_json_with_cli(
            SearchInput,
            json_str='{"query": "python"}',
            cli_kwargs={},
        )
        assert result.query == "python"

    def test_cli_overrides_json(self):
        result = merge_json_with_cli(
            SearchInput,
            json_str='{"query": "python", "max_results": 5}',
            cli_kwargs={"max_results": 10},
        )
        assert result.max_results == 10

    def test_none_cli_values_do_not_override_json(self):
        result = merge_json_with_cli(
            SearchInput,
            json_str='{"query": "python", "max_results": 5}',
            cli_kwargs={"max_results": None},
        )
        assert result.max_results == 5

    def test_no_json_cli_only(self):
        result = merge_json_with_cli(
            SearchInput,
            json_str=None,
            cli_kwargs={"query": "rust"},
        )
        assert result.query == "rust"

    def test_invalid_json_raises_system_exit(self):
        with pytest.raises(SystemExit):
            merge_json_with_cli(SearchInput, json_str="{not json}", cli_kwargs={})

    def test_invalid_json_exit_code_message(self):
        with pytest.raises(SystemExit) as exc_info:
            merge_json_with_cli(SearchInput, json_str="{invalid json", cli_kwargs={})
        assert exc_info.value.code is not None

    def test_ask_input_merge(self):
        result = merge_json_with_cli(
            AskInput,
            json_str='{"question": "hello", "model": "sonar"}',
            cli_kwargs={"model": "sonar-pro"},
        )
        assert result.model == "sonar-pro"
        assert result.question == "hello"

    def test_empty_json_string_treated_as_no_json(self):
        result = merge_json_with_cli(
            SearchInput,
            json_str=None,
            cli_kwargs={"query": "test"},
        )
        assert result.query == "test"
