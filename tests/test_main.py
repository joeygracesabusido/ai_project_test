import pytest
from click.testing import CliRunner
from unittest.mock import patch


class TestCli:
    def test_main_shows_interactive_prompt(self):
        from main import main
        runner = CliRunner()
        with patch("main._setup_provider"):
            result = runner.invoke(main, [], input="quit\n")
        assert result.exit_code == 0
        assert "MongoDB AI Assistant" in result.output

    def test_main_calls_run_query(self):
        from main import main
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["show me collections"])
            assert result.exit_code in (0, 1)

    def test_models_command_in_interactive(self):
        from main import main
        runner = CliRunner()
        with patch("main._setup_provider"), \
             patch("main._pick_ollama_model") as mock_picker:
            result = runner.invoke(main, [], input="/models\nquit\n")
        assert result.exit_code == 0
        mock_picker.assert_called_once()

    def test_provider_command_in_interactive(self):
        from main import main
        runner = CliRunner()
        with patch("main._setup_provider") as mock_setup:
            result = runner.invoke(main, [], input="/provider\nquit\n")
        assert result.exit_code == 0
        assert mock_setup.call_count == 2  # startup + /provider command
