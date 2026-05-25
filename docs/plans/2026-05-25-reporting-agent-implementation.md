# MongoDB AI-Powered CLI Reporting Agent — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a CLI tool that accepts natural language queries, connects to MongoDB, and returns formatted reports using Ollama.

**Architecture:** 5-component Python app — CLI (click), Agent (orchestrator), DB (pymongo), LLM (ollama), Formatter (rich). Agent introspects schema → Ollama generates aggregation pipeline → MongoDB executes → Ollama interprets → CLI renders.

**Tech Stack:** Python 3.11+, pymongo, click, ollama, python-dotenv, rich, mongomock (tests)

---

### Task 1: Project Scaffolding & `.env`

**Files:**
- Create: `requirements.txt`
- Create: `.env`
- Create: `.env.example`
- Create: `main.py` (entry point)

**Step 1: Write `requirements.txt`**
```
pymongo>=4.6,<5.0
click>=8.1,<9.0
python-dotenv>=1.0,<2.0
rich>=13.0,<14.0
requests>=2.31,<3.0
pytest>=8.0,<9.0
mongomock>=4.1,<5.0
pytest-mock>=3.12,<4.0
```

**Step 2: Write `.env`**
```
DATABASE_URL="mongodb+srv://joeysabusido:genesis11@cluster0.bmdqy.mongodb.net/maam_jhoy_project?retryWrites=true&w=majority"
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

**Step 3: Write `.env.example`** (same but with placeholder credentials)

**Step 4: Write `main.py`**
```python
#!/usr/bin/env python3
import sys
import click
from dotenv import load_dotenv

load_dotenv()

@click.command()
@click.argument("query", required=False)
@click.option("--collection", "-c", help="Target collection (optional)")
@click.option("--raw", is_flag=True, help="Show raw data table")
def main(query, collection, raw):
    if not query:
        click.echo("Usage: python main.py \"<your question>\"")
        click.echo("Example: python main.py \"show me total sales by month\"")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**Step 5: Verify imports work**
```bash
pip install -r requirements.txt && python main.py --help
```
Expected: Shows help text.

---

### Task 2: Database Layer (`db.py`)

**Files:**
- Create: `db.py`
- Create: `tests/test_db.py`

**What it does:** MongoDB connection manager, schema introspection, pipeline execution.

**Step 1: Write the failing test** (`tests/test_db.py`)
```python
import pytest
from db import get_db, introspect_schema, execute_pipeline

def test_get_db_returns_client():
    from pymongo.database import Database
    db = get_db()
    assert isinstance(db, Database)
```

**Step 2: Run to verify failure**
```bash
pytest tests/test_db.py::test_get_db_returns_client -v
```
Expected: FAIL — `db` module not found.

**Step 3: Implement `db.py`**
```python
import os
from pymongo import MongoClient
from pymongo.database import Database

_client = None

def get_db() -> Database:
    global _client
    if _client is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL not set in .env")
        _client = MongoClient(url, serverSelectionTimeoutMS=5000)
    db_name = url.rsplit("/", 1)[-1].split("?")[0]
    return _client[db_name]

def introspect_schema(db: Database) -> dict:
    schema = {}
    collections = db.list_collection_names()
    for coll_name in collections:
        sample = db[coll_name].find_one()
        if sample:
            fields = {k: type(v).__name__ for k, v in sample.items() if k != "_id"}
        else:
            fields = {}
        schema[coll_name] = fields
    return {
        "database": db.name,
        "collections": schema,
        "collection_names": collections,
    }

def execute_pipeline(db: Database, collection: str, pipeline: list) -> list:
    results = list(db[collection].aggregate(pipeline, allowDiskUse=True))
    # Convert non-serializable types
    for doc in results:
        for k, v in doc.items():
            if hasattr(v, "isoformat"):
                doc[k] = v.isoformat()
    return results
```

**Step 4: Run test to verify pass**
```bash
pytest tests/test_db.py::test_get_db_returns_client -v
```
Expected: PASS (connects to real MongoDB).

**Step 5: Add schema introspection test**
```python
def test_introspect_schema_returns_structure():
    db = get_db()
    schema = introspect_schema(db)
    assert "database" in schema
    assert "collections" in schema
    assert isinstance(schema["collection_names"], list)
```

---

### Task 3: LLM Layer (`llm.py`)

**Files:**
- Create: `llm.py`
- Create: `tests/test_llm.py`

**What it does:** Client for Ollama API — sends prompts, receives responses, parses JSON.

**Step 1: Write failing tests**
```python
import pytest
from llm import generate_pipeline, interpret_results

def test_generate_pipeline_returns_list():
    schema = {"database": "test", "collections": {"users": {"name": "str"}}, "collection_names": ["users"]}
    result = generate_pipeline(schema, "show me all users")
    assert isinstance(result, list)
```

**Step 2: Implement `llm.py`**
```python
import os
import json
import requests

def _ollama_generate(prompt: str, model: str = None) -> str:
    url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    model = model or os.getenv("OLLAMA_MODEL", "llama3.2")
    resp = requests.post(
        f"{url}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["response"]

def generate_pipeline(schema: dict, query: str) -> list:
    prompt = f"""You are a MongoDB expert. Given this database schema:

Database: {schema['database']}
Collections: {json.dumps(schema['collections'], indent=2)}

User query: "{query}"

Generate a MongoDB aggregation pipeline that answers this query.
Return ONLY a valid JSON array of pipeline stages. No explanations, no markdown.
Example: [{{"$match": {{"status": "active"}}}}, {{"$group": {{"_id": "$category", "count": {{"$sum": 1}}}}}}]

Pipeline:"""

    response = _ollama_generate(prompt)
    # Strip markdown code fences if present
    response = response.strip()
    if response.startswith("```"):
        response = response.split("\n", 1)[1]
    if response.endswith("```"):
        response = response.rsplit("```", 1)[0]
    response = response.strip()

    pipeline = json.loads(response)
    if not isinstance(pipeline, list):
        raise ValueError("Pipeline must be a JSON array")
    return pipeline

def interpret_results(query: str, results: list, schema: dict) -> str:
    prompt = f"""User asked: "{query}"

Here are the raw results from MongoDB:
{json.dumps(results[:50], indent=2, default=str)}

Database schema context:
{json.dumps(schema.get('collections', {}), indent=2)}

Write a clear, concise summary of what this data means for a non-technical user.
Focus on insights, trends, and key numbers. Be specific — use actual values from the data.
If there are no results, explain what the user could try instead.

Summary:"""

    return _ollama_generate(prompt)
```

**Step 3: Run tests**
```bash
pytest tests/test_llm.py -v
```
Expected: PASS (requires Ollama running).

---

### Task 4: Agent Engine (`agent.py`)

**Files:**
- Create: `agent.py`
- Create: `tests/test_agent.py`

**What it does:** Orchestrates schema → pipeline → execute → interpret flow with retry logic.

**Step 1: Write failing tests**
```python
import pytest
from agent import run_query

def test_run_query_returns_report():
    result = run_query("list all collections")
    assert "report" in result
    assert "raw" in result
    assert isinstance(result["report"], str)
```

**Step 2: Implement `agent.py`**
```python
import json
import click
from db import get_db, introspect_schema, execute_pipeline
from llm import generate_pipeline, interpret_results

MAX_RETRIES = 2

def run_query(query: str, target_collection: str = None) -> dict:
    db = get_db()
    schema = introspect_schema(db)

    if target_collection:
        collections = [target_collection]
    else:
        collections = schema["collection_names"]

    if not collections:
        return {"report": "No collections found in database.", "raw": []}

    # Use first collection or targeted one
    coll = collections[0]

    # Generate pipeline with retries
    pipeline = None
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            pipeline = generate_pipeline(schema, query)
            break
        except (json.JSONDecodeError, ValueError) as e:
            last_error = str(e)
            continue

    if pipeline is None:
        # Fallback: simple find
        pipeline = [{"$limit": 10}]
        click.echo(f"Warning: Could not generate pipeline ({last_error}), using fallback.")

    # Execute pipeline
    results = execute_pipeline(db, coll, pipeline)

    # Interpret results
    report = interpret_results(query, results, schema)

    return {"report": report, "raw": results, "collection": coll, "pipeline": pipeline}

def run_query_raw(query: str, target_collection: str = None) -> dict:
    """Run query and return raw results only."""
    result = run_query(query, target_collection)
    return result
```

**Step 3: Add interpret test**
```python
def test_run_query_handles_empty_db():
    result = run_query("show me everything")
    assert isinstance(result["report"], str)
```

---

### Task 5: Formatter (`formatter.py`)

**Files:**
- Create: `formatter.py`
- Create: `tests/test_formatter.py`

**What it does:** Pretty-prints reports and tables to CLI using `rich`.

**Step 1: Implement `formatter.py`**
```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def print_report(report: str, raw_data: list = None, show_raw: bool = False):
    panel = Panel(report, title="Report", border_style="green")
    console.print(panel)

    if show_raw and raw_data:
        if raw_data:
            table = Table(title="Raw Data")
            keys = list(raw_data[0].keys()) if raw_data else []
            for key in keys:
                table.add_column(key, style="cyan")
            for row in raw_data:
                table.add_row(*[str(row.get(k, "")) for k in keys])
            console.print(table)
        else:
            console.print("[yellow]No raw data to display.[/yellow]")

def print_error(message: str):
    console.print(f"[red]Error:[/red] {message}")

def print_info(message: str):
    console.print(f"[blue]{message}[/blue]")
```

**Step 2: Write and run tests**
```python
from formatter import print_report, print_error
def test_print_report_no_error():
    # Smoke test — just ensure no exception
    print_report("Test report", [{"a": 1}], show_raw=True)
```

---

### Task 6: Wire CLI (`main.py`)

**Files:**
- Modify: `main.py`

**Step 1: Update `main.py` with full wiring**
```python
#!/usr/bin/env python3
import sys
import click
from dotenv import load_dotenv

load_dotenv()

@click.command()
@click.argument("query", required=False)
@click.option("--collection", "-c", help="Target collection")
@click.option("--raw", is_flag=True, help="Show raw data table")
def main(query, collection, raw):
    if not query:
        click.echo("Usage: python main.py \"<your question>\"")
        click.echo("  python main.py \"show total sales by month\"")
        click.echo("  python main.py --collection orders \"top 10 customers\"")
        click.echo("  python main.py --raw \"list all products\"")
        sys.exit(1)

    from agent import run_query
    from formatter import print_report, print_error

    try:
        result = run_query(query, target_collection=collection)
        print_report(result["report"], result.get("raw"), show_raw=raw)
    except Exception as e:
        print_error(str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**Step 2: Test end-to-end**
```bash
python main.py "show me all collections in the database"
```
Expected: Prints report based on real MongoDB data.

---

### Task 7: Integration Testing

**Files:**
- Create: `tests/test_integration.py`

**Test:**
```python
import pytest
from agent import run_query
from db import get_db, introspect_schema

def test_full_flow_integration():
    result = run_query("list all collections")
    assert "report" in result
    assert len(result["report"]) > 0

def test_schema_has_data():
    db = get_db()
    schema = introspect_schema(db)
    assert len(schema["collection_names"]) > 0
    print(f"Found collections: {schema['collection_names']}")
```

**Run:**
```bash
pytest tests/ -v
```
Expected: All pass.
