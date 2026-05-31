from __future__ import annotations

from perplexity_cli.models import SearchInput
from perplexity_cli.providers import (
    _OPENROUTER_SNIPPET_MAX_CHARS,
    OpenRouterProvider,
    PerplexityProvider,
)


# ---------------------------------------------------------------------------
# Fakes that mimic the shapes each backend actually returns.
# ---------------------------------------------------------------------------


class _SdkResult:
    """Mimics perplexity.types.search_create_response.Result (attribute access).

    The native /search endpoint returns objects with `title`, `url`, `snippet`,
    `date`, `last_updated` -- note `title`, not `name`.
    """

    def __init__(self, url, title, snippet, date=None):
        self.url = url
        self.title = title
        self.snippet = snippet
        self.date = date


class _SdkSearchResponse:
    def __init__(self, results):
        self.results = results


class _FakeSearchResource:
    def __init__(self, response):
        self._response = response
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


class _FakeSdkClient:
    def __init__(self, response):
        self.search = _FakeSearchResource(response)


def _perplexity_with(response) -> PerplexityProvider:
    provider = PerplexityProvider("pplx-test")
    provider._client = _FakeSdkClient(response)  # type: ignore[assignment]
    return provider


# ---------------------------------------------------------------------------
# Native Perplexity path: snippet + date + name(title) must map through.
# This is the path enabled by adding a PERPLEXITY_API_KEY.
# ---------------------------------------------------------------------------


def test_perplexity_search_maps_title_snippet_and_date():
    response = _SdkSearchResponse(
        [
            _SdkResult(
                url="https://docs.python.org/3/whatsnew/3.13.html",
                title="What's New In Python 3.13",
                snippet="Python 3.13 adds an improved interactive interpreter...",
                date="2024-10-07",
            ),
            _SdkResult(
                url="https://realpython.com/python313-new-features/",
                title="Python 3.13: Cool New Features",
                snippet="A tour of the headline features.",
            ),
        ]
    )
    provider = _perplexity_with(response)

    out = provider.search(SearchInput(query="Python 3.13 new features"))

    assert [r.url for r in out.results] == [
        "https://docs.python.org/3/whatsnew/3.13.html",
        "https://realpython.com/python313-new-features/",
    ]
    first = out.results[0]
    assert first.name == "What's New In Python 3.13"  # mapped from `title`
    assert first.snippet == "Python 3.13 adds an improved interactive interpreter..."
    assert first.date == "2024-10-07"
    # date is optional on the SDK side -> stays None, never crashes
    assert out.results[1].date is None


def test_perplexity_search_empty_results_is_empty_not_error():
    provider = _perplexity_with(_SdkSearchResponse([]))
    out = provider.search(SearchInput(query="anything"))
    assert out.results == []


# ---------------------------------------------------------------------------
# OpenRouter path: `search` opts into the web-search plugin, whose
# url_citation annotations include `content` -> recoverable snippets.
# `date` is not exposed by the plugin, so it stays None on this backend.
# ---------------------------------------------------------------------------


def _openrouter_capturing(data: dict):
    provider = OpenRouterProvider("sk-or-test")
    captured: dict = {}

    def _fake_post(path, body):
        captured["path"] = path
        captured["body"] = body
        return data

    provider._post_json = _fake_post  # type: ignore[assignment]
    return provider, captured


def test_openrouter_search_requests_web_plugin():
    provider, captured = _openrouter_capturing({"choices": []})
    provider.search(SearchInput(query="q", max_results=5))
    plugins = captured["body"]["plugins"]
    assert plugins == [{"id": "web", "max_results": 5}]
    # the throwaway answer is capped
    assert captured["body"]["max_tokens"] == 64


def test_openrouter_search_extracts_snippet_from_annotation_content():
    data = {
        "choices": [
            {
                "message": {
                    "content": "...",
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url_citation": {
                                "url": "https://example.com/a",
                                "title": "Result A",
                                "content": "Line one.\n[...]\nLine two.",
                            },
                        }
                    ],
                }
            }
        ]
    }
    provider, _ = _openrouter_capturing(data)
    out = provider.search(SearchInput(query="q"))

    first = out.results[0]
    assert first.url == "https://example.com/a"
    assert first.name == "Result A"
    assert first.snippet == "Line one. [...] Line two."  # whitespace collapsed
    assert first.date is None  # plugin exposes no date


def test_openrouter_search_long_content_is_truncated():
    long_content = "word " * 500
    data = {
        "choices": [
            {
                "message": {
                    "annotations": [
                        {"url_citation": {"url": "https://x/1", "content": long_content}}
                    ]
                }
            }
        ]
    }
    provider, _ = _openrouter_capturing(data)
    out = provider.search(SearchInput(query="q"))
    snippet = out.results[0].snippet
    assert snippet is not None and snippet.endswith("…")
    assert len(snippet) <= _OPENROUTER_SNIPPET_MAX_CHARS + len("…")


def test_openrouter_search_missing_content_leaves_snippet_none():
    data = {
        "choices": [
            {"message": {"annotations": [{"url_citation": {"url": "https://x/1", "title": "1"}}]}}
        ]
    }
    provider, _ = _openrouter_capturing(data)
    out = provider.search(SearchInput(query="q"))
    assert out.results[0].snippet is None


def test_openrouter_search_dedupes_and_respects_max_results():
    data = {
        "choices": [
            {
                "message": {
                    "annotations": [
                        {"url_citation": {"url": "https://x/1", "title": "1"}},
                        {"url_citation": {"url": "https://x/1", "title": "dup"}},
                        {"url_citation": {"url": "https://x/2", "title": "2"}},
                        {"url_citation": {"url": "https://x/3", "title": "3"}},
                    ]
                }
            }
        ]
    }
    provider, _ = _openrouter_capturing(data)
    out = provider.search(SearchInput(query="q", max_results=2))
    assert [r.url for r in out.results] == ["https://x/1", "https://x/2"]


def test_openrouter_search_no_annotations_is_empty():
    provider, _ = _openrouter_capturing(
        {"choices": [{"message": {"content": "answer with no citations"}}]}
    )
    out = provider.search(SearchInput(query="q"))
    assert out.results == []
