import json
from db import get_db, execute_pipeline

db = get_db()
pipeline = [
  {
    "$match": {
      "date": {
        "$gte": {
          "$dateFromString": {
            "dateString": "2026-05-26T00:00:00.000Z"
          }
        },
        "$lte": {
          "$dateFromString": {
            "dateString": "2026-05-26T23:59:59.999Z"
          }
        }
      }
    }
  }
]
results = execute_pipeline(db, "timelogs", pipeline)
print("Pipeline Results Count:", len(results))
