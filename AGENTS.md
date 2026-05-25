# aiProject AGENTS.md

## Entrypoints
- `main.py` — CLI entrypoint (Click). `python3 main.py` starts interactive REPL; `python3 main.py "query"` runs one-shot.
- Interactive mode always prompts for provider (Ollama or OpenAI) at startup. Ollama then prompts for model selection. Supports `/provider` and `/models` to switch mid-session.

## Architecture
- `agent.py:run_query(query, target_collection=None)` is the orchestrator: schema → select_collection → generate_pipeline → execute_pipeline → interpret_results.
- `llm.py` abstracts LLM calls. Two providers via `LLM_PROVIDER` env var (`ollama` or `openai`). OpenAI-compatible API used for DeepSeek.
- `db.py` handles MongoDB connection (`get_db()`), schema introspection (`introspect_schema(db)`), and pipeline execution (`execute_pipeline(db, coll, pipeline)`).
- `formatter.py` renders Rich output (Panel for report, Table for raw data).
- Multi-provider `_generate(prompt)` in llm.py routes based on `LLM_PROVIDER`.

## Commands
```bash
# Run (Ollama provider — default)
python3 main.py

# One-shot query
python3 main.py "show me all employees"

# With flags
python3 main.py --collection employees --raw "list active employees"

# Run all unit tests (integration tests skipped — require live DB)
python3 -m pytest tests/ -v --ignore=tests/test_integration.py

# Run single test file
python3 -m pytest tests/test_llm.py -v

# Run single test
python3 -m pytest tests/test_llm.py::TestLlmLayer::test_list_ollama_models_returns_list -v
```

## Config (`.env` — gitignored)
| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | Switch to `openai` for DeepSeek |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | Any OpenAI-compatible API |
| `OPENAI_API_KEY` | — | Required for `openai` provider |
| `OPENAI_MODEL` | `deepseek-chat` | |
| `OLLAMA_URL` | `http://localhost:11434` | |
| `OLLAMA_MODEL` | `llama3.2` | Overridden at runtime by interactive picker |

## Testing quirks
- Agent tests must mock `select_collection` (not just `generate_pipeline`) because `run_query` calls it first and it hits the LLM.
- Integration tests (`test_integration.py`) require a live MongoDB — skipped by default.
- `mongomock` is available for DB unit tests but not used in integration tests.
- Prefer `pytest` over `unittest`; fixtures are not used yet — all mocking via `unittest.mock.patch`.

## Notable conventions
- All LLM responses parsed through `_clean_json_response()` to strip markdown fences before `json.loads`.
- `_generate(prompt)` is the single internal LLM call function — always mock this for unit tests.
- `select_collection()` falls back to first collection alphabetically if LLM returns an invalid name.
- Pipeline generation retries up to 2 times on `JSONDecodeError`/`ValueError`, then falls back to `[{"$limit": 10}]`.
