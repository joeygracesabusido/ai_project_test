# MongoDB AI-Powered CLI Reporting Agent

## Overview
A CLI tool that accepts natural language queries, connects to any MongoDB database, and returns formatted reports using a local LLM (Ollama) to generate aggregation pipelines and interpret results.

## Architecture

```
User Query → Schema Introspection → LLM Pipeline Gen → MongoDB Execute → LLM Interpret → CLI Output
```

## Components

### 1. CLI Layer (`cli.py` / `main.py`)
- Entry point: `python main.py "<natural language query>"`
- Optional flags: `--collection`, `--format`, `--raw`
- Uses `click` for argument parsing

### 2. Database Layer (`db.py`)
- `MongoClient` wrapper from `pymongo`
- Schema introspection: list collections, sample documents, infer field types
- Execute aggregation pipelines
- Thread-safe connection pooling

### 3. LLM Layer (`llm.py`)
- Ollama HTTP client (default: `http://localhost:11434`)
- Two modes: **generate** (pipeline creation) and **chat** (interpretation)
- Configurable model via `.env` (default: `llama3.2`)
- Structured prompting with JSON output parsing

### 4. Agent Engine (`agent.py`)
- Orchestrates the 5-step flow
- Handles retries (max 2) on invalid pipeline JSON
- Caches schema per session to minimize LLM calls

### 5. Formatter (`formatter.py`)
- Pretty table output using `rich` or `tabulate`
- Supports: plain text, markdown, CSV
- Chunked output for large result sets

## Data Flow

1. **Schema Introspection**
   - `db.list_collections()` → get all collection names
   - For each collection: `find_one()` → sample document → infer fields + types
   - Package into structured schema context

2. **Pipeline Generation**
   - Prompt: "Given this schema, write a MongoDB aggregation pipeline for: {query}. Return ONLY valid JSON."
   - Parse response as JSON pipeline
   - Validate structure (must be a list of stages)

3. **Pipeline Execution**
   - `collection.aggregate(pipeline)` → cursor of results
   - Handle timeout (30s default)
   - Convert ObjectId/Date to serializable types

4. **Result Interpretation**
   - Send raw results + original query to Ollama
   - Prompt: "Summarize these results for a non-technical user"
   - Return natural language report

5. **Output**
   - Print interpretation
   - Optionally print raw data table
   - Handle empty results gracefully

## Configuration (`.env`)
```
DATABASE_URL=mongodb+srv://<user>:<pass>@<host>/<db>?retryWrites=true&w=majority
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

## Error Handling
| Error | Response |
|-------|----------|
| MongoDB connection failure | Print diagnostics, check URL |
| Ollama not available | Check `ollama serve`, model pulled |
| Invalid pipeline JSON | Retry with stricter prompt (2x) |
| Pipeline execution error | Print MongoDB error message |
| Empty results | Show schema suggestions |

## Testing
- Unit tests for each module
- Mock MongoDB with `mongomock`
- Mock Ollama with `unittest.mock`
- Integration test with local Ollama (optional)
