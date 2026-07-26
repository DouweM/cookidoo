"""Offline CLI tests (no network/credentials): command wiring + error handling."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

import pytest
from typer.testing import CliRunner

from cookidoo.cli import app

runner = CliRunner()


def test_help_lists_all_tabs():
    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    for command in ['for-you', 'search', 'recipe', 'my-recipes', 'collections', 'week', 'shopping', 'notes', 'whoami']:
        assert command in result.output


def test_shopping_subcommands():
    result = runner.invoke(app, ['shopping', '--help'])
    assert result.exit_code == 0
    for sub in ['list', 'add-recipes', 'add', 'check', 'remove', 'clear']:
        assert sub in result.output


def test_week_subcommands():
    result = runner.invoke(app, ['week', '--help'])
    assert result.exit_code == 0
    for sub in ['show', 'add', 'remove']:
        assert sub in result.output


def test_missing_credentials_exits_nonzero(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv('COOKIDOO_USERNAME', raising=False)
    monkeypatch.delenv('COOKIDOO_PASSWORD', raising=False)
    result = runner.invoke(app, ['whoami'])
    assert result.exit_code != 0
