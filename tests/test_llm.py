import json
import os
import pytest
import requests
from unittest.mock import patch, MagicMock
from llm import _generate, generate_pipeline, interpret_results, list_ollama_models, pick_ollama_model, pick_provider, prompt_openai_api_key


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
        with patch("llm.requests.post") as mock_post:
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
