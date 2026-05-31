from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterator, Protocol

import httpx
from perplexity import Perplexity
from perplexity._exceptions import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    PermissionDeniedError,
    RateLimitError,
)

from .models import (
    AskInput,
    AskOutput,
    SearchInput,
    SearchOutput,
    SearchResultItem,
    UsageInfo,
)

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_DEFAULT_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
_OPENROUTER_SEARCH_MODEL = "perplexity/sonar-pro"
# OpenRouter's web-search plugin attaches url_citation annotations that include a
# `content` field (snippet text). A model's native citations expose only
# url+title, so `search` opts into the plugin to recover snippets.
_OPENROUTER_WEB_PLUGIN_MAX_RESULTS = 10
# `search` discards the model's prose answer (it only wants the citations), so the
# completion is capped to keep that throwaway generation cheap.
_OPENROUTER_SEARCH_TOKEN_CAP = 64
_OPENROUTER_SNIPPET_MAX_CHARS = 320
_FALLBACK_STATUS_CODES = frozenset({401, 402, 403, 408, 429, 500, 502, 503, 504})


class OpenRouterError(Exception):
    """HTTP-level error from the OpenRouter API."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"OpenRouter API error ({status_code}): {message}")
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class StreamEvent:
    """Normalized streaming chunk emitted by a Provider.

    `citations` is the full cumulative list when it changes during the stream
    (empty tuple when unchanged). `usage` is set only on the chunk that carries
    it.
    """

    content_delta: str = ""
    citations: tuple[str, ...] = ()
    usage: UsageInfo | None = None


class Provider(Protocol):
    def search(self, params: SearchInput) -> SearchOutput: ...
    def ask(self, params: AskInput) -> AskOutput: ...
    def chat_stream(self, params: AskInput) -> Iterator[StreamEvent]: ...


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _drop_none(**kwargs: Any) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


def _build_messages(params: AskInput) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if params.system_prompt:
        messages.append({"role": "system", "content": params.system_prompt})
    messages.append({"role": "user", "content": params.question})
    return messages


def _usage_from_dict(usage: dict[str, Any] | None) -> UsageInfo | None:
    if not usage:
        return None
    return UsageInfo(
        prompt_tokens=usage.get("prompt_tokens", 0) or 0,
        completion_tokens=usage.get("completion_tokens", 0) or 0,
        total_tokens=usage.get("total_tokens", 0) or 0,
    )


def _usage_from_obj(usage: Any) -> UsageInfo | None:
    if not usage:
        return None
    return UsageInfo(
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        total_tokens=getattr(usage, "total_tokens", 0) or 0,
    )


def _snippet_from_content(content: str | None) -> str | None:
    """Condense OpenRouter web-plugin `content` into a short search snippet.

    The plugin returns long, newline-and-`[...]`-laden page extracts; collapse
    whitespace and truncate so the result reads like a search snippet.
    """
    text = " ".join((content or "").split())
    if not text:
        return None
    if len(text) <= _OPENROUTER_SNIPPET_MAX_CHARS:
        return text
    return text[:_OPENROUTER_SNIPPET_MAX_CHARS].rstrip() + "…"


# ---------------------------------------------------------------------------
# Perplexity provider (native SDK)
# ---------------------------------------------------------------------------


class PerplexityProvider:
    def __init__(self, api_key: str) -> None:
        self._client = Perplexity(api_key=api_key)

    def search(self, params: SearchInput) -> SearchOutput:
        response = self._client.search.create(**_drop_none(
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
        results: list[SearchResultItem] = []
        for r in getattr(response, "results", None) or []:
            results.append(SearchResultItem(
                url=getattr(r, "url", ""),
                name=getattr(r, "name", None) or getattr(r, "title", None),
                snippet=getattr(r, "snippet", None) or getattr(r, "text", None),
                date=getattr(r, "date", None),
            ))
        return SearchOutput(query=params.query, results=results)

    def ask(self, params: AskInput) -> AskOutput:
        response = self._client.chat.completions.create(**_drop_none(
            messages=_build_messages(params),
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
        msg = response.choices[0].message if response.choices else None
        content = msg.content if msg and msg.content else ""
        citations = (
            list(response.citations)
            if getattr(response, "citations", None)
            else []
        )
        related = (
            list(response.related_questions)
            if getattr(response, "related_questions", None)
            else []
        )
        return AskOutput(
            content=content,
            model=params.model,
            citations=citations,
            usage=_usage_from_obj(getattr(response, "usage", None)),
            related_questions=related,
        )

    def chat_stream(self, params: AskInput) -> Iterator[StreamEvent]:
        stream = self._client.chat.completions.create(**_drop_none(
            messages=_build_messages(params),
            model=params.model,
            stream=True,
            search_mode=params.search_mode,
            search_recency_filter=params.search_recency_filter,
            search_domain_filter=params.search_domain_filter,
            temperature=params.temperature,
            max_tokens=params.max_tokens,
            reasoning_effort=params.reasoning_effort,
        ))
        last_citations: tuple[str, ...] = ()
        for chunk in stream:
            delta_content = ""
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    delta_content = delta.content

            new_citations: tuple[str, ...] = ()
            chunk_cit = getattr(chunk, "citations", None)
            if chunk_cit:
                cit_tuple = tuple(chunk_cit)
                if cit_tuple != last_citations:
                    new_citations = cit_tuple
                    last_citations = cit_tuple

            new_usage = _usage_from_obj(getattr(chunk, "usage", None))

            if delta_content or new_citations or new_usage is not None:
                yield StreamEvent(
                    content_delta=delta_content,
                    citations=new_citations,
                    usage=new_usage,
                )


# ---------------------------------------------------------------------------
# OpenRouter provider (raw HTTP, routed to Perplexity Sonar models)
# ---------------------------------------------------------------------------


class OpenRouterProvider:
    def __init__(self, api_key: str) -> None:
        self._client = httpx.Client(
            base_url=_OPENROUTER_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=_OPENROUTER_DEFAULT_TIMEOUT,
        )

    @staticmethod
    def _route_model(model: str | None) -> str:
        m = model or "sonar"
        return m if "/" in m else f"perplexity/{m}"

    @staticmethod
    def _build_chat_body(
        params: AskInput,
        *,
        stream: bool,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        model = OpenRouterProvider._route_model(model_override or params.model)
        body: dict[str, Any] = {
            "model": model,
            "messages": _build_messages(params),
            "stream": stream,
        }
        if params.temperature is not None:
            body["temperature"] = params.temperature
        if params.max_tokens is not None:
            body["max_tokens"] = params.max_tokens
        # Perplexity-specific knobs forwarded upstream by OpenRouter for
        # `perplexity/*` models.
        if params.search_mode is not None:
            body["search_mode"] = params.search_mode
        if params.search_recency_filter is not None:
            body["search_recency_filter"] = params.search_recency_filter
        if params.search_domain_filter is not None:
            body["search_domain_filter"] = params.search_domain_filter
        if params.reasoning_effort is not None:
            body["reasoning_effort"] = params.reasoning_effort
        if params.return_related_questions:
            body["return_related_questions"] = True
        if params.return_images:
            body["return_images"] = True
        return body

    @staticmethod
    def _short_message(response: httpx.Response) -> str:
        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError):
            text = response.text or ""
            return text[:500]
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            return str(err.get("message") or err)
        return str(err or data)[:500]

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=body)
        except httpx.HTTPError as exc:
            raise OpenRouterError(0, f"network error: {exc}") from exc
        if response.status_code >= 400:
            raise OpenRouterError(response.status_code, self._short_message(response))
        return response.json()

    @staticmethod
    def _extract_citations(
        message: dict[str, Any],
    ) -> list[tuple[str, str | None, str | None]]:
        """Return deduped (url, title, content) from message annotations.

        `content` is present only when the request used the web-search plugin;
        the native citation path leaves it None.
        """
        out: list[tuple[str, str | None, str | None]] = []
        seen: set[str] = set()
        for ann in message.get("annotations") or []:
            uc = ann.get("url_citation") or {}
            url = uc.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            out.append((url, uc.get("title"), uc.get("content")))
        return out

    def search(self, params: SearchInput) -> SearchOutput:
        query_text = (
            params.query if isinstance(params.query, str) else " ".join(params.query)
        )
        ask_params = AskInput(
            question=query_text,
            model="sonar-pro",
            search_mode=params.search_mode,
            search_recency_filter=params.search_recency_filter,
            search_domain_filter=params.search_domain_filter,
        )
        body = self._build_chat_body(
            ask_params, stream=False, model_override=_OPENROUTER_SEARCH_MODEL
        )
        # Opt into OpenRouter's web-search plugin so each citation carries
        # `content` (snippet text). The model's prose answer is unused here.
        body["plugins"] = [
            {
                "id": "web",
                "max_results": params.max_results or _OPENROUTER_WEB_PLUGIN_MAX_RESULTS,
            }
        ]
        body.setdefault("max_tokens", _OPENROUTER_SEARCH_TOKEN_CAP)
        data = self._post_json("/chat/completions", body)
        choices = data.get("choices") or []
        message = (choices[0].get("message") if choices else None) or {}
        # date is not exposed by the web plugin -> stays None on this backend.
        items = [
            SearchResultItem(
                url=url, name=title, snippet=_snippet_from_content(content), date=None
            )
            for url, title, content in self._extract_citations(message)
        ]
        if params.max_results is not None:
            items = items[: params.max_results]
        return SearchOutput(query=params.query, results=items)

    def ask(self, params: AskInput) -> AskOutput:
        body = self._build_chat_body(params, stream=False)
        data = self._post_json("/chat/completions", body)
        choices = data.get("choices") or []
        message = (choices[0].get("message") if choices else None) or {}
        content = message.get("content") or ""
        citations = [url for url, _, _ in self._extract_citations(message)]
        return AskOutput(
            content=content,
            model=params.model,
            citations=citations,
            usage=_usage_from_dict(data.get("usage")),
            related_questions=[],
        )

    def chat_stream(self, params: AskInput) -> Iterator[StreamEvent]:
        body = self._build_chat_body(params, stream=True)
        try:
            stream_ctx = self._client.stream("POST", "/chat/completions", json=body)
        except httpx.HTTPError as exc:
            raise OpenRouterError(0, f"network error: {exc}") from exc

        with stream_ctx as response:
            if response.status_code >= 400:
                response.read()
                raise OpenRouterError(response.status_code, self._short_message(response))

            citations: list[str] = []
            seen: set[str] = set()
            try:
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    delta_content = ""
                    new_citation = False
                    for choice in chunk.get("choices") or []:
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            delta_content = delta["content"]
                        for ann in delta.get("annotations") or []:
                            uc = ann.get("url_citation") or {}
                            url = uc.get("url")
                            if url and url not in seen:
                                seen.add(url)
                                citations.append(url)
                                new_citation = True

                    new_usage = _usage_from_dict(chunk.get("usage"))

                    if delta_content or new_citation or new_usage is not None:
                        yield StreamEvent(
                            content_delta=delta_content,
                            citations=tuple(citations) if new_citation else (),
                            usage=new_usage,
                        )
            except httpx.HTTPError as exc:
                raise OpenRouterError(0, f"network error: {exc}") from exc


# ---------------------------------------------------------------------------
# Fallback provider
# ---------------------------------------------------------------------------


_FALLBACK_PERPLEXITY_EXCEPTIONS = (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
    InternalServerError,
)


def _should_fallback(exc: BaseException) -> bool:
    if isinstance(exc, APIStatusError):
        return getattr(exc, "status_code", 0) in _FALLBACK_STATUS_CODES
    if isinstance(exc, _FALLBACK_PERPLEXITY_EXCEPTIONS):
        return True
    if isinstance(exc, httpx.HTTPError):
        return True
    return False


class FallbackProvider:
    """Try `primary`. On retriable errors, retry against `fallback`.

    For streaming, fallback is only attempted before the first chunk emits.
    Errors mid-stream propagate to the caller.
    """

    def __init__(self, primary: Provider, fallback: Provider) -> None:
        self._primary = primary
        self._fallback = fallback

    def search(self, params: SearchInput) -> SearchOutput:
        try:
            return self._primary.search(params)
        except Exception as exc:
            if _should_fallback(exc):
                return self._fallback.search(params)
            raise

    def ask(self, params: AskInput) -> AskOutput:
        try:
            return self._primary.ask(params)
        except Exception as exc:
            if _should_fallback(exc):
                return self._fallback.ask(params)
            raise

    def chat_stream(self, params: AskInput) -> Iterator[StreamEvent]:
        try:
            iterator = iter(self._primary.chat_stream(params))
            first = next(iterator)
        except StopIteration:
            return
        except Exception as exc:
            if not _should_fallback(exc):
                raise
            yield from self._fallback.chat_stream(params)
            return
        yield first
        yield from iterator
