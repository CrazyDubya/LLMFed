"""Tests for the CLI management tool."""

import os

from typer.testing import CliRunner
from cli.main import app

# Rich (Typer's help renderer) wraps option names to fit the detected
# terminal width. Without a real TTY it falls back to whatever COLUMNS
# reports, which is narrow enough on some CI runners to wrap a long name
# like "narrative-retention" across two lines and break a plain substring
# check. Force a wide terminal so --help output is stable everywhere.
os.environ["COLUMNS"] = "200"

runner = CliRunner()


class TestCLIBasics:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "LLMFed" in result.stdout or "llmfed" in result.stdout

    def test_world_help(self):
        result = runner.invoke(app, ["world", "--help"])
        assert result.exit_code == 0
        assert "create" in result.stdout
        assert "list" in result.stdout

    def test_fed_help(self):
        result = runner.invoke(app, ["fed", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "roster" in result.stdout

    def test_sim_help(self):
        result = runner.invoke(app, ["sim", "--help"])
        assert result.exit_code == 0
        assert "run" in result.stdout
        assert "status" in result.stdout

    def test_init_command_exists(self):
        # Just verify the command is registered (don't actually run it)
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0

    def test_stats_command_exists(self):
        result = runner.invoke(app, ["stats", "--help"])
        assert result.exit_code == 0

    def test_maintenance_command_exists(self):
        result = runner.invoke(app, ["maintenance", "--help"])
        assert result.exit_code == 0
        assert "narrative-retention" in result.stdout

    def test_match_command_exists(self):
        result = runner.invoke(app, ["match", "--help"])
        assert result.exit_code == 0
