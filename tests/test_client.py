from __future__ import annotations

import pytest

from perplexity_cli.client import get_provider, resolve_keys
from perplexity_cli.config import Config
from perplexity_cli.providers import (
    FallbackProvider,
    OpenRouterProvider,
    PerplexityProvider,
)


@pytest.fixture(autouse=True)
def _clear_key_env(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


# ---------------------------------------------------------------------------
# resolve_keys precedence:  flag > env > config
# ---------------------------------------------------------------------------


def test_perplexity_flag_beats_env_and_config(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "env")
    cfg = Config(perplexity_api_key="cfg")
    pkey, _ = resolve_keys("flag", cfg)
    assert pkey == "flag"


def test_perplexity_env_beats_config(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "env")
    cfg = Config(perplexity_api_key="cfg")
    pkey, _ = resolve_keys(None, cfg)
    assert pkey == "env"


def test_perplexity_config_is_fallback():
    cfg = Config(perplexity_api_key="cfg")
    pkey, _ = resolve_keys(None, cfg)
    assert pkey == "cfg"


def test_openrouter_env_beats_config(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-or")
    cfg = Config(openrouter_api_key="cfg-or")
    _, okey = resolve_keys(None, cfg)
    assert okey == "env-or"


def test_openrouter_config_is_fallback():
    cfg = Config(openrouter_api_key="cfg-or")
    _, okey = resolve_keys(None, cfg)
    assert okey == "cfg-or"


def test_no_keys_anywhere_resolves_to_none():
    assert resolve_keys(None, Config()) == (None, None)
    assert resolve_keys(None, None) == (None, None)


# ---------------------------------------------------------------------------
# get_provider selection
# ---------------------------------------------------------------------------


def test_config_only_perplexity_key_builds_perplexity_provider():
    provider = get_provider(None, config=Config(perplexity_api_key="pplx-x"))
    assert isinstance(provider, PerplexityProvider)


def test_config_only_openrouter_key_builds_openrouter_provider():
    provider = get_provider(None, config=Config(openrouter_api_key="sk-or-y"))
    assert isinstance(provider, OpenRouterProvider)


def test_both_keys_from_config_builds_fallback():
    provider = get_provider(
        None, config=Config(perplexity_api_key="pplx-x", openrouter_api_key="sk-or-y")
    )
    assert isinstance(provider, FallbackProvider)


def test_env_key_still_works_without_config(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-env")
    assert isinstance(get_provider(None), PerplexityProvider)


def test_no_keys_exits_2():
    with pytest.raises(SystemExit) as exc:
        get_provider(None, config=Config())
    assert exc.value.code == 2


def test_empty_api_key_flag_exits_2():
    with pytest.raises(SystemExit) as exc:
        get_provider("", config=Config(perplexity_api_key="cfg"))
    assert exc.value.code == 2
