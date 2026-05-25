import os
import json
import requests


def pick_provider() -> str:
    from rich.console import Console
    from rich.table import Table
    console = Console()

    table = Table(title="Select LLM Provider")
    table.add_column("#", style="bold")
    table.add_column("Provider")
    table.add_row("1", "Ollama (local)")
    table.add_row("2", "OpenCode")
    console.print(table)

    while True:
        choice = input("Select provider (1-2): ").strip()
        if choice == "1":
            return "ollama"
        if choice == "2":
            return "opencode"
        console.print("[red]Invalid choice. Enter 1 or 2.[/red]")


def prompt_openai_api_key():
    import getpass
    key = os.getenv("OPENAI_API_KEY", "")
    if key:
        return
    key = getpass.getpass("Enter your OpenAI / DeepSeek API key: ")
    os.environ["OPENAI_API_KEY"] = key


def list_ollama_models() -> list[str]:
    url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    resp = requests.get(f"{url.rstrip('/')}/api/tags", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return [m["name"] for m in data.get("models", [])]


def pick_ollama_model() -> str:
    from rich.console import Console
    from rich.table import Table
    console = Console()

    models = list_ollama_models()
    if not models:
        raise RuntimeError("No Ollama models found. Pull one first: ollama pull <model>")

    table = Table(title="Available Ollama Models")
    table.add_column("#", style="bold")
    table.add_column("Model")

    for i, model in enumerate(models, 1):
        table.add_row(str(i), model)

    console.print(table)

    while True:
        try:
            choice = input(f"Select model (1-{len(models)}): ").strip()
            if not choice:
                return models[0]
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                return models[idx]
        except (ValueError, IndexError):
            pass
        console.print(f"[red]Invalid choice. Enter 1-{len(models)}[/red]")


def _generate(prompt: str) -> str:
    provider = os.getenv("LLM_PROVIDER", "ollama")

    if provider == "openai":
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
        api_key = os.getenv("OPENAI_API_KEY", "")
        model = os.getenv("OPENAI_MODEL", "deepseek-chat")
        resp = requests.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    resp = requests.post(
        f"{url}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def _clean_json_response(response: str) -> str:
    response = response.strip()
    if response.startswith("```"):
        response = response.split("\n", 1)[1] if "\n" in response else response[3:]
    if response.endswith("```"):
        response = response.rsplit("```", 1)[0]
    return response.strip()


def select_collection(query: str, schema: dict) -> str:
    prompt = f"""Given these MongoDB collections and their fields:

{json.dumps(schema['collections'], indent=2)}

User query: "{query}"

Which single collection is most relevant to answer this query?
Return ONLY the collection name, nothing else."""

    response = _generate(prompt).strip().strip('"').strip("'")
    if response in schema["collection_names"]:
        return response
    return schema["collection_names"][0] if schema["collection_names"] else ""


def generate_pipeline(schema: dict, query: str) -> list:
    prompt = f"""You are a MongoDB expert. Given this database schema:

Database: {schema['database']}
Collections: {json.dumps(schema['collections'], indent=2)}

User query: "{query}"

Generate a MongoDB aggregation pipeline that answers this query.
Return ONLY a valid JSON array of pipeline stages. No explanations, no markdown.
Example: [{{"$match": {{"status": "active"}}}}, {{"$group": {{"_id": "$category", "count": {{"$sum": 1}}}}}}]

Pipeline:"""

    response = _generate(prompt)
    response = _clean_json_response(response)
    pipeline = json.loads(response)
    if not isinstance(pipeline, list):
        raise ValueError("Pipeline must be a JSON array")
    return pipeline


def interpret_results(query: str, results: list, schema: dict) -> str:
    prompt = f"""User asked: "{query}"

Here are the raw results from MongoDB:
{json.dumps(results[:50], indent=2, default=str)}
{"(results truncated to 50 items)" if len(results) > 50 else ""}

Database schema context:
{json.dumps(schema.get('collections', {}), indent=2)}

Write a clear, concise summary of what this data means for a non-technical user.
Focus on insights, trends, and key numbers. Be specific — use actual values from the data.
If there are no results, explain what the user could try instead.

Summary:"""

    return _generate(prompt)
