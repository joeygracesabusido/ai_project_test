import json
import os
import pytest
import requests
from unittest.mock import patch, MagicMock
from llm import _generate, generate_pipeline, interpret_results, list_ollama_models, list_opencode_models, pick_ollama_model, pick_opencode_model, pick_provider, prompt_openai_api_key


class TestLlmLayer:
    def test_generate_pipeline_returns_list(self):
        schema = {
            "database": "test_db",
            "collections": {"users": {"name": "str", "email": "str"}},
            "collection_names": ["users"],
        }
        with patch("llm._generate") as mock_gen:
            mock_gen.return_value = '[{"$match": {"name": "John"}}, {"$limit": 5}]'
            result = generate_pipeline(schema, "find John")
            assert isinstance(result, list)
            assert len(result) == 2
            assert "$match" in result[0]

    def test_generate_pipeline_strips_markdown(self):
        schema = {
            "database": "test_db",
            "collections": {"users": {"name": "str"}},
            "collection_names": ["users"],
        }
        with patch("llm._generate") as mock_gen:
            mock_gen.return_value = '```json\n[{"$match": {"name": "John"}}]\n```'
            result = generate_pipeline(schema, "find John")
            assert isinstance(result, list)

    def test_interpret_results_returns_string(self):
        with patch("llm._generate") as mock_gen:
            mock_gen.return_value = "Found 3 users."
            result = interpret_results(
                "how many users?",
                [{"name": "Alice"}, {"name": "Bob"}, {"name": "Charlie"}],
                {"collections": {"users": {"name": "str"}}},
            )
            assert isinstance(result, str)
            assert len(result) > 0

    def test_generate_raises_on_connection_error(self):
        with patch("llm.requests.post") as mock_post, \
             patch.dict("os.environ", {"LLM_PROVIDER": "ollama"}, clear=False):
            mock_post.side_effect = requests.ConnectionError("Connection refused")
            with pytest.raises(requests.ConnectionError):
                _generate("test prompt")

    def test_generate_pipeline_raises_on_invalid_json(self):
        schema = {
            "database": "test_db",
            "collections": {"users": {"name": "str"}},
            "collection_names": ["users"],
        }
        with patch("llm._generate") as mock_gen:
            mock_gen.return_value = "not json at all"
            with pytest.raises(json.JSONDecodeError):
                generate_pipeline(schema, "test")

    def test_list_ollama_models_returns_list(self):
        with patch("llm.requests.get") as mock_get:
            mock_get.return_value.json.return_value = {
                "models": [{"name": "llama3.2"}, {"name": "mistral"}]
            }
            result = list_ollama_models()
            assert isinstance(result, list)
            assert result == ["llama3.2", "mistral"]

    def test_list_ollama_models_raises_on_error(self):
        with patch("llm.requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError("Ollama not running")
            with pytest.raises(requests.ConnectionError):
                list_ollama_models()

    def test_pick_ollama_model_raises_on_empty(self):
        with patch("llm.list_ollama_models", return_value=[]):
            with pytest.raises(RuntimeError, match="No Ollama models found"):
                pick_ollama_model()

    def test_pick_ollama_model_returns_selected(self):
        with patch("llm.list_ollama_models", return_value=["llama3.2", "mistral"]), \
             patch("builtins.input", return_value="2"):
            result = pick_ollama_model()
            assert result == "mistral"

    def test_pick_ollama_model_defaults_to_first_on_empty_input(self):
        with patch("llm.list_ollama_models", return_value=["llama3.2", "mistral"]), \
             patch("builtins.input", return_value=""):
            result = pick_ollama_model()
            assert result == "llama3.2"

    def test_pick_provider_returns_ollama(self):
        with patch("builtins.input", return_value="1"):
            result = pick_provider()
            assert result == "ollama"

    def test_pick_provider_returns_opencode(self):
        with patch("builtins.input", return_value="2"):
            result = pick_provider()
            assert result == "opencode"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-existing"}, clear=True)
    def test_prompt_openai_api_key_skips_when_set(self):
        prompt_openai_api_key()

    @patch.dict("os.environ", {}, clear=True)
    def test_prompt_openai_api_key_prompts_when_missing(self):
        with patch("getpass.getpass", return_value="sk-new-key"):
            prompt_openai_api_key()
            assert os.environ.get("OPENAI_API_KEY") == "sk-new-key"

    def test_list_opencode_models_returns_list(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = (
                "opencode/big-pickle\nopencode/deepseek-v4-flash-free\nollama/minimax-m2.5:cloud\n"
            )
            result = list_opencode_models()
            assert result == [
                "opencode/big-pickle",
                "opencode/deepseek-v4-flash-free",
                "ollama/minimax-m2.5:cloud",
            ]

    def test_list_opencode_models_raises_on_error(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "opencode not found"
            with pytest.raises(RuntimeError, match="Failed to list opencode models"):
                list_opencode_models()

    def test_pick_opencode_model_raises_on_empty(self):
        with patch("llm.list_opencode_models", return_value=[]):
            with pytest.raises(RuntimeError, match="No opencode models found"):
                pick_opencode_model()

    def test_pick_opencode_model_returns_selected(self):
        models = ["opencode/deepseek-v4-flash-free", "opencode/big-pickle", "ollama/minimax-m2.5:cloud"]
        with patch("llm.list_opencode_models", return_value=models), \
             patch("builtins.input", return_value="2"):
            result = pick_opencode_model()
            assert result == "opencode/big-pickle"

    def test_pick_opencode_model_defaults_to_first_on_empty_input(self):
        models = ["opencode/deepseek-v4-flash-free", "opencode/big-pickle"]
        with patch("llm.list_opencode_models", return_value=models), \
             patch("builtins.input", return_value=""):
            result = pick_opencode_model()
            assert result == "opencode/deepseek-v4-flash-free"

    def test_generate_opencode_calls_subprocess(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Hello from opencode"
            with patch.dict("os.environ", {"LLM_PROVIDER": "opencode", "OPENCODE_MODEL": "opencode/deepseek-v4-flash-free"}):
                result = _generate("say hi")
            assert result == "Hello from opencode"
            mock_run.assert_called_once_with(
                ["opencode", "run", "-m", "opencode/deepseek-v4-flash-free", "say hi"],
                capture_output=True, text=True, timeout=120,
            )

    def test_generate_opencode_raises_on_error(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "model not found"
            with patch.dict("os.environ", {"LLM_PROVIDER": "opencode"}):
                with pytest.raises(RuntimeError, match="opencode run failed: model not found"):
                    _generate("test")
