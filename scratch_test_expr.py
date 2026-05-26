import json
from db import get_db, execute_pipeline

db = get_db()
pipeline = [
  {
    "$match": {
      "$expr": {
        "$and": [
          {"$gte": ["$date", {"$dateFromString": {"dateString": "2026-05-26T00:00:00.000Z"}}]},
          {"$lte": ["$date", {"$dateFromString": {"dateString": "2026-05-26T23:59:59.999Z"}}]}
        ]
      }
    }
  }
]
results = execute_pipeline(db, "timelogs", pipeline)
print("Pipeline Results Count with $expr:", len(results))
