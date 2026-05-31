from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import perplexity_cli.main as main
from perplexity_cli.models import AskOutput, SearchOutput

runner = CliRunner()

SECRET = "pplx-super-secret-key"


class FakeProvider:
    """Records the params it receives and returns canned output."""

    last_params = None

    def ask(self, params):
        FakeProvider.last_params = params
        return AskOutput(content="answer", model=params.model, citations=[])

    def search(self, params):
        FakeProvider.last_params = params
        return SearchOutput(query=params.query, results=[])

    def chat_stream(self, params):  # pragma: no cover - unused here
        FakeProvider.last_params = params
        return iter(())


@pytest.fixture
def fake_provider(monkeypatch):
    """Replace get_provider so no network call happens, but still exercise it
    enough to confirm a provider was resolvable from config."""
    FakeProvider.last_params = None
    captured = {}

    def _fake_get_provider(api_key=None, config=None):
        captured["api_key"] = api_key
        captured["config"] = config
        # Exercise real resolution so a missing key would still exit 2.
        from perplexity_cli.client import resolve_keys

        pkey, okey = resolve_keys(api_key, config)
        if not pkey and not okey:
            raise SystemExit(2)
        return FakeProvider()

    monkeypatch.setattr(main, "get_provider", _fake_get_provider)
    return captured


@pytest.fixture
def config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    def _write(payload: dict) -> None:
        d = tmp_path / "perplexity-cli"
        d.mkdir(parents=True, exist_ok=True)
        (d / "perplexity-cli.json").write_text(json.dumps(payload), encoding="utf-8")

    return _write


def test_config_only_keys_let_ask_run(config_home, fake_provider):
    config_home({"perplexity_api_key": SECRET, "model": "sonar-pro"})
    result = runner.invoke(main.app, ["ask", "what is rust"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["content"] == "answer"
    # config default model flowed through the merge
    assert payload["model"] == "sonar-pro"
    assert FakeProvider.last_params.model == "sonar-pro"


def test_secret_never_appears_in_output(config_home, fake_provider):
    config_home({"perplexity_api_key": SECRET, "model": "sonar-pro"})
    result = runner.invoke(main.app, ["ask", "hello"])
    assert result.exit_code == 0
    assert SECRET not in result.stdout
    assert SECRET not in result.stderr


def test_cli_flag_overrides_config_model(config_home, fake_provider):
    config_home({"perplexity_api_key": SECRET, "model": "sonar-pro"})
    result = runner.invoke(main.app, ["ask", "hi", "--model", "sonar-reasoning"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["model"] == "sonar-reasoning"


def test_config_output_format_applied(config_home, fake_provider):
    config_home({"perplexity_api_key": SECRET, "output": "text"})
    result = runner.invoke(main.app, ["ask", "hi"])
    assert result.exit_code == 0
    # text mode prints the raw answer, not JSON
    assert result.stdout.strip() == "answer"


def test_text_flag_overrides_config_output(config_home, fake_provider):
    config_home({"perplexity_api_key": SECRET, "output": "json"})
    result = runner.invoke(main.app, ["--text", "ask", "hi"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "answer"


def test_search_uses_config_search_defaults(config_home, fake_provider):
    config_home({"perplexity_api_key": SECRET, "search_mode": "academic", "recency": "year"})
    result = runner.invoke(main.app, ["search", "papers"])
    assert result.exit_code == 0
    assert FakeProvider.last_params.search_mode == "academic"
    assert FakeProvider.last_params.search_recency_filter == "year"


def test_malformed_config_exits_4(config_home, fake_provider, tmp_path):
    d = tmp_path / "perplexity-cli"
    d.mkdir(parents=True, exist_ok=True)
    (d / "perplexity-cli.json").write_text("{broken", encoding="utf-8")
    result = runner.invoke(main.app, ["ask", "hi"])
    assert result.exit_code == 4
    assert SECRET not in result.stderr


def test_unknown_config_key_exits_4(config_home, fake_provider):
    config_home({"perplexity_api_key": SECRET, "bogus": True})
    result = runner.invoke(main.app, ["ask", "hi"])
    assert result.exit_code == 4


def test_env_only_still_works(monkeypatch, tmp_path, fake_provider):
    # No config file present; env key drives resolution (legacy path).
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-env")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = runner.invoke(main.app, ["ask", "hi"])
    assert result.exit_code == 0
    # no config model → built-in default
    assert json.loads(result.stdout)["model"] == "sonar"


def test_no_key_anywhere_exits_2(monkeypatch, tmp_path, fake_provider):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = runner.invoke(main.app, ["ask", "hi"])
    assert result.exit_code == 2
