import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

load_dotenv()

_client = None

def get_db() -> Database:
    global _client
    if _client is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL not set in .env")
        _client = MongoClient(url, serverSelectionTimeoutMS=5000)
    # Extract db name from URL: mongodb+srv://.../DB_NAME?...
    db_name = os.getenv("DATABASE_URL").rsplit("/", 1)[-1].split("?")[0]
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
    # Convert non-serializable types (ObjectId, datetime, etc.)
    for doc in results:
        for k, v in doc.items():
            if hasattr(v, "isoformat"):
                doc[k] = v.isoformat()
            elif hasattr(v, "__str__") and not isinstance(v, (str, int, float, bool, list, dict)):
                doc[k] = str(v)
    return results
