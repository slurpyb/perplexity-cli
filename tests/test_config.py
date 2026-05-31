from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from pydantic import ValidationError

from perplexity_cli.config import Config, config_path, load_config


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def test_config_path_honors_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_path() == tmp_path / "perplexity-cli" / "perplexity-cli.json"


def test_config_path_falls_back_to_home_dot_config(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert config_path() == tmp_path / ".config" / "perplexity-cli" / "perplexity-cli.json"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_missing_file_returns_empty_config(tmp_path):
    cfg = load_config(tmp_path / "nope.json")
    assert cfg == Config()
    assert cfg.perplexity_api_key is None
    assert cfg.model is None


def test_valid_file_parses(tmp_path):
    p = _write(
        tmp_path / "c.json",
        {
            "perplexity_api_key": "pplx-x",
            "openrouter_api_key": "sk-or-y",
            "model": "sonar-pro",
            "output": "text",
            "search_mode": "academic",
            "recency": "week",
            "reasoning_effort": "high",
            "temperature": 0.3,
        },
    )
    cfg = load_config(p)
    assert cfg.perplexity_api_key == "pplx-x"
    assert cfg.openrouter_api_key == "sk-or-y"
    assert cfg.model == "sonar-pro"
    assert cfg.output == "text"
    assert cfg.search_mode == "academic"
    assert cfg.recency == "week"
    assert cfg.reasoning_effort == "high"
    assert cfg.temperature == 0.3


def test_malformed_json_raises_jsondecodeerror(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_config(p)


def test_unknown_key_rejected(tmp_path):
    p = _write(tmp_path / "c.json", {"model": "sonar", "bogus": 1})
    with pytest.raises(ValidationError):
        load_config(p)


def test_invalid_enum_value_rejected(tmp_path):
    p = _write(tmp_path / "c.json", {"output": "yaml"})
    with pytest.raises(ValidationError):
        load_config(p)


def test_temperature_out_of_range_rejected(tmp_path):
    p = _write(tmp_path / "c.json", {"temperature": 9.0})
    with pytest.raises(ValidationError):
        load_config(p)


def test_world_readable_file_warns(tmp_path, capsys):
    p = _write(tmp_path / "c.json", {"model": "sonar"})
    p.chmod(0o644)  # group/world readable
    load_config(p)
    err = capsys.readouterr().err
    assert "chmod 600" in err
    assert str(p) in err


def test_private_file_does_not_warn(tmp_path, capsys):
    p = _write(tmp_path / "c.json", {"model": "sonar"})
    p.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600
    load_config(p)
    assert capsys.readouterr().err == ""


# ---------------------------------------------------------------------------
# Default mappers
# ---------------------------------------------------------------------------


def test_ask_defaults_maps_recency_to_filter_and_drops_none():
    cfg = Config(model="sonar-pro", recency="day", temperature=0.2)
    assert cfg.ask_defaults() == {
        "model": "sonar-pro",
        "search_recency_filter": "day",
        "temperature": 0.2,
    }


def test_search_defaults_only_search_fields():
    cfg = Config(model="sonar-pro", search_mode="sec", recency="month", temperature=0.2)
    assert cfg.search_defaults() == {
        "search_mode": "sec",
        "search_recency_filter": "month",
    }


def test_empty_config_yields_empty_defaults():
    cfg = Config()
    assert cfg.ask_defaults() == {}
    assert cfg.search_defaults() == {}
