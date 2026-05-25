# AI Project

MongoDB natural language query assistant. Ask questions about your data in plain English.

## Usage

```bash
python3 main.py            # Interactive REPL
python3 main.py "query"    # One-shot
python3 main.py --collection employees --raw "list active employees"
```

Supports Ollama and OpenAI-compatible providers (DeepSeek, etc.).
