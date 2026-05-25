import json
from db import get_db, introspect_schema, execute_pipeline
from llm import generate_pipeline, interpret_results, select_collection

MAX_RETRIES = 2

def run_query(query: str, target_collection: str = None) -> dict:
    """Run a natural language query against MongoDB and return interpreted results.
    
    Args:
        query: Natural language query from user
        target_collection: Optional collection name to target
        
    Returns:
        dict with keys: report (str), raw (list), collection (str), pipeline (list)
    """
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
