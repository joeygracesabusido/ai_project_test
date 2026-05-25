#!/usr/bin/env python3
import sys
import click
from dotenv import load_dotenv

load_dotenv()


def _setup_provider():
    import os
    from llm import pick_provider, prompt_openai_api_key
    from formatter import console

    provider = pick_provider()
    os.environ["LLM_PROVIDER"] = provider

    if provider == "ollama":
        _pick_ollama_model()
    elif provider == "opencode":
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_BASE_URL"] = os.getenv("OPENCODE_URL", "http://localhost:11434")
        os.environ["OPENAI_API_KEY"] = "sk-no-key-required"
        _pick_ollama_model()
        os.environ["OPENAI_MODEL"] = os.getenv("OLLAMA_MODEL", "llama3.2")
    else:
        prompt_openai_api_key()
        model = os.getenv("OPENAI_MODEL", "deepseek-chat")
        console.print(f"[green]Using provider:[/green] OpenAI ({model})\n")


def _pick_ollama_model():
    import os
    from llm import pick_ollama_model as _picker
    from formatter import console

    try:
        model = _picker()
        os.environ["OLLAMA_MODEL"] = model
        console.print(f"[green]Using model:[/green] {model}\n")
    except RuntimeError as e:
        from formatter import print_error
        print_error(str(e))


def interactive_mode():
    import os
    from formatter import print_report, print_error, console
    from agent import run_query

    _setup_provider()

    console.print("[bold green]MongoDB AI Assistant[/bold green]")
    console.print("Ask questions about your data. Type [bold]exit[/bold] or [bold]quit[/bold] to stop.\n")

    while True:
        try:
            raw = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue
        if raw.lower() in ("exit", "quit", "q"):
            console.print("[blue]Goodbye![/blue]")
            break
        if raw == "/provider":
            _setup_provider()
            continue
        if raw == "/models":
            _pick_ollama_model()
            if os.getenv("LLM_PROVIDER", "ollama") == "openai":
                os.environ["OPENAI_MODEL"] = os.getenv("OLLAMA_MODEL", "llama3.2")
            continue

        try:
            result = run_query(raw)
            print_report(result["report"], result.get("raw"), show_raw=False, collection=result.get("collection"))
            print()
        except Exception as e:
            print_error(str(e))
            print()


@click.command()
@click.argument("query", required=False)
@click.option("--collection", "-c", help="Target collection")
@click.option("--raw", is_flag=True, help="Show raw data table")
def main(query, collection, raw):
    if not query:
        interactive_mode()
        return

    from agent import run_query
    from formatter import print_report, print_error

    try:
        result = run_query(query, target_collection=collection)
        print_report(result["report"], result.get("raw"), show_raw=raw, collection=result.get("collection"))
    except Exception as e:
        print_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
