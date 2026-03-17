import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection


def load_mongo_uri() -> str:
    """
    Load environment variables and return the MongoDB URI.
    """
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("MONGO_URI is not set in .env")
    return mongo_uri


def get_mongo_collection() -> Collection:
    """
    Create a Mongo client and return the target collection.
    """
    mongo_uri = load_mongo_uri()
    client = MongoClient(mongo_uri)
    db = client["reddit_distress_db"]
    collection = db["posts"]
    return collection
