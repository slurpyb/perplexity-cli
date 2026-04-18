"""Tests for perplexity_cli.client."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from perplexity._exceptions import PerplexityError

from perplexity_cli.client import get_client


class TestGetClient:
    def test_returns_client_with_explicit_api_key(self):
        mock_client = MagicMock()
        with patch("perplexity_cli.client.Perplexity", return_value=mock_client) as mock_cls:
            result = get_client(api_key="test-key")
        mock_cls.assert_called_once_with(api_key="test-key")
        assert result is mock_client

    def test_returns_client_without_api_key_uses_env(self):
        mock_client = MagicMock()
        with patch("perplexity_cli.client.Perplexity", return_value=mock_client) as mock_cls:
            result = get_client()
        mock_cls.assert_called_once_with()
        assert result is mock_client

    def test_none_api_key_uses_env(self):
        mock_client = MagicMock()
        with patch("perplexity_cli.client.Perplexity", return_value=mock_client) as mock_cls:
            result = get_client(api_key=None)
        mock_cls.assert_called_once_with()
        assert result is mock_client

    def test_perplexity_error_exits_with_code_2(self):
        with patch(
            "perplexity_cli.client.Perplexity",
            side_effect=PerplexityError("no key"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                get_client()
        assert exc_info.value.code == 2

    def test_perplexity_error_writes_to_stderr(self, capsys):
        with patch(
            "perplexity_cli.client.Perplexity",
            side_effect=PerplexityError("no key"),
        ):
            with pytest.raises(SystemExit):
                get_client()
        captured = capsys.readouterr()
        assert "PERPLEXITY_API_KEY" in captured.err
        assert "No API key" in captured.err
