import json
from db import get_db, introspect_schema, execute_pipeline
from llm import generate_pipeline, interpret_results, select_collection
from attendance_agent import get_attendance_report, get_attendance_summary
from funds_agent import get_funds_overview, get_petty_cash_status, get_advance_summary
from balance_sheet_agent import check_balance, check_debits_equal_credits, check_assets_equals_liabilities_equity, find_unbalanced_entries

MAX_RETRIES = 2


def _parse_command(query: str) -> dict:
    q = query.strip().lower()
    parts = q.split(maxsplit=2)
    cmd = parts[0] if parts else ""
    args = parts[1:] if len(parts) > 1 else []
    return {"command": cmd, "args": args, "raw": query}


def run_query(query: str, target_collection: str = None) -> dict:
    """Run a natural language query against MongoDB and return interpreted results.
    
    Args:
        query: Natural language query from user
        target_collection: Optional collection name to target
        
    Returns:
        dict with keys: report (str), raw (list), collection (str), pipeline (list)
    """
    cmd = _parse_command(query)

    # Automation command routing
    if cmd["command"] == "/attendance":
        period = cmd["args"][0] if cmd["args"] else "today"
        employee = cmd["args"][1] if len(cmd["args"]) > 1 else None
        if period == "summary":
            return get_attendance_summary(cmd["args"][1] if len(cmd["args"]) > 1 else "month")
        return get_attendance_report(period, employee)

    if cmd["command"] == "/funds":
        sub = cmd["args"][0] if cmd["args"] else "all"
        if sub == "petty":
            return get_petty_cash_status(" ".join(cmd["args"][1:]) if len(cmd["args"]) > 1 else None)
        if sub == "advances":
            return get_advance_summary()
        return get_funds_overview()

    if cmd["command"] == "/balance":
        sub = cmd["args"][0] if cmd["args"] else "all"
        if sub == "debits":
            return check_debits_equal_credits()
        if sub == "entries":
            return find_unbalanced_entries()
        if sub == "equation":
            return check_assets_equals_liabilities_equity()
        return check_balance()

    db = get_db()
    schema = introspect_schema(db)

    if not schema["collection_names"]:
        return {"report": "No collections found in database.", "raw": [], "collection": None, "pipeline": []}

    if target_collection:
        if target_collection not in schema["collection_names"]:
            available = ", ".join(schema["collection_names"])
            return {
                "report": f"Collection '{target_collection}' not found. Available: {available}",
                "raw": [],
                "collection": None,
                "pipeline": [],
            }
        coll = target_collection
    else:
        coll = select_collection(query, schema)

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
        pipeline = [{"$limit": 10}]

    # Execute pipeline
    results = execute_pipeline(db, coll, pipeline)

    # Interpret results
    report = interpret_results(query, results, schema)

    return {"report": report, "raw": results, "collection": coll, "pipeline": pipeline}
