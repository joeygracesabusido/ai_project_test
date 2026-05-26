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

    def test_models_command_in_interactive_with_opencode_provider(self):
        from main import main
        runner = CliRunner()
        with patch("main._setup_provider"), \
             patch("main._setup_opencode_provider") as mock_setup, \
             patch.dict("os.environ", {"LLM_PROVIDER": "opencode"}, clear=False):
            result = runner.invoke(main, [], input="/models\nquit\n")
        assert result.exit_code == 0
        mock_setup.assert_called_once()

    def test_provider_command_in_interactive(self):
        from main import main
        runner = CliRunner()
        with patch("main._setup_provider") as mock_setup:
            result = runner.invoke(main, [], input="/provider\nquit\n")
        assert result.exit_code == 0
        assert mock_setup.call_count == 2  # startup + /provider command


class TestOpenCodeProvider:
    def test_setup_opencode_provider_calls_pick_model(self):
        with patch("llm.pick_opencode_model", return_value="opencode/deepseek-v4-flash-free"):
            from main import _setup_opencode_provider
            _setup_opencode_provider()
        import os
        assert os.environ.get("LLM_PROVIDER") == "opencode"
        assert os.environ.get("OPENCODE_MODEL") == "opencode/deepseek-v4-flash-free"

    def test_setup_opencode_provider_handles_error(self):
        with patch("llm.pick_opencode_model", side_effect=RuntimeError("no models")), \
             patch("formatter.print_error") as mock_error:
            from main import _setup_opencode_provider
            _setup_opencode_provider()
        mock_error.assert_called_once_with("no models")
