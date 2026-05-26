import json
from db import get_db, introspect_schema
from llm import generate_pipeline

db = get_db()
schema = introspect_schema(db)
pipeline = generate_pipeline(schema, "who is present for today")
print(json.dumps(pipeline, indent=2))
