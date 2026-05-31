from __future__ import annotations

from perplexity_cli.models import AskInput, merge_json_with_cli
from perplexity_cli.output import OutputFormat, resolve_output_format


# ---------------------------------------------------------------------------
# merge_json_with_cli layering:  config < json < cli
# ---------------------------------------------------------------------------


def test_config_defaults_fill_when_absent():
    params = merge_json_with_cli(
        AskInput,
        None,
        {"question": "q"},
        config_defaults={"model": "sonar-pro", "temperature": 0.2},
    )
    assert params.model == "sonar-pro"
    assert params.temperature == 0.2


def test_json_overrides_config():
    params = merge_json_with_cli(
        AskInput,
        '{"question": "q", "model": "sonar-reasoning"}',
        {},
        config_defaults={"model": "sonar-pro"},
    )
    assert params.model == "sonar-reasoning"


def test_cli_overrides_json_and_config():
    params = merge_json_with_cli(
        AskInput,
        '{"question": "q", "temperature": 0.5}',
        {"temperature": 0.9},
        config_defaults={"temperature": 0.1},
    )
    assert params.temperature == 0.9


def test_none_cli_values_do_not_override_config():
    params = merge_json_with_cli(
        AskInput,
        None,
        {"question": "q", "model": None},
        config_defaults={"model": "sonar-pro"},
    )
    assert params.model == "sonar-pro"


def test_no_config_defaults_is_backward_compatible():
    params = merge_json_with_cli(AskInput, None, {"question": "q"})
    assert params.model == "sonar"  # built-in default


# ---------------------------------------------------------------------------
# output format resolution:  flag > config > default
# ---------------------------------------------------------------------------


def test_text_flag_wins():
    assert resolve_output_format(True, False, "pretty") == OutputFormat.TEXT


def test_pretty_flag_wins_over_config():
    assert resolve_output_format(False, True, "text") == OutputFormat.PRETTY


def test_config_output_used_when_no_flag():
    assert resolve_output_format(False, False, "text") == OutputFormat.TEXT
    assert resolve_output_format(False, False, "pretty") == OutputFormat.PRETTY


def test_defaults_to_json():
    assert resolve_output_format(False, False, None) == OutputFormat.JSON
